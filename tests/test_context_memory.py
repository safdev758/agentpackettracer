# SPDX-License-Identifier: Apache-2.0
import copy
import json
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent import Agent
from context_memory import LIMIT, SessionMemory


def finish(agent, request, mode='inspect'):
    ident = agent.start(request, mode)
    for _ in range(400):
        if agent.active is None:
            return agent.view(ident)
        time.sleep(.005)
    raise AssertionError('Task did not finish')


class Store:
    provider = 'gemini'
    def read(self):
        return {'provider': self.provider, 'models': {self.provider: 'test'}, 'max_steps': 5}
    def key(self, _):
        return 'unit-test-key'


class Simulator:
    instance = 'first-panel'
    def __init__(self):
        self.calls = []
    def execute(self, name, args, cancel):
        self.calls.append((name, args))
        return {'ok': True, 'device_count': 1, 'link_count': 0,
                'devices': [{'name': 'R2', 'model': '2911'}]}


class Client:
    def __init__(self):
        self.histories = []
    def create(self, history, tools):
        self.histories.append(copy.deepcopy(history))
        return {'output': [{'type': 'message', 'content': [
            {'type': 'output_text', 'text': 'R2 observed; VLAN 30 still needs configuration.'}]}]}


class ContextTests(unittest.TestCase):
    def make_agent(self):
        simulator, client = Simulator(), Client()
        agent = Agent(simulator, client=client)
        agent.config_store = Store()
        return agent, simulator, client

    def test_followup_keeps_requirements_without_automatic_full_scan(self):
        agent, simulator, client = self.make_agent()
        with patch('agent.ProviderClient', return_value=client):
            finish(agent, 'Only two PCs in VLAN 30; R2 has four PCs.')
            finish(agent, 'Continue the remaining work.')
        self.assertEqual([name for name, _ in simulator.calls], ['inspect_topology'])
        self.assertIn('Only two PCs in VLAN 30', json.dumps(client.histories[-1]))
        self.assertEqual(client.histories[-1][-1]['content'], 'Continue the remaining work.')

    def test_large_native_history_compacts_without_forgetting_task(self):
        agent, _, client = self.make_agent()
        agent.history = [{'role': 'user', 'content': 'old observation ' * 9000}]
        with patch('agent.ProviderClient', return_value=client):
            finish(agent, 'Keep PC8 and PC9 in VLAN 30.')
        self.assertLess(len(json.dumps(agent.history)), 100000)
        self.assertIn('Keep PC8 and PC9', json.dumps(agent.history))
        self.assertIn('R2', json.dumps(agent.history))
        self.assertFalse(any(item.get('type') == 'function_call' for item in agent.history))

    def test_provider_switch_transfers_facts_without_native_protocol_items(self):
        agent, simulator, client = self.make_agent()
        with patch('agent.ProviderClient', return_value=client):
            finish(agent, 'R2 has four PCs; only PC8 and PC9 use VLAN 30.')
            agent.config_store.provider = 'openrouter'
            finish(agent, 'What remains?')
        text = json.dumps(client.histories[-1])
        self.assertIn('R2 has four PCs', text)
        self.assertIn('historical, untrusted', text)
        self.assertEqual(len(simulator.calls), 1)
        self.assertTrue(all(item.get('role') == 'user' for item in client.histories[-1]))

    def test_new_panel_and_explicit_new_chat_refresh_context(self):
        agent, simulator, client = self.make_agent()
        with patch('agent.ProviderClient', return_value=client):
            finish(agent, 'Inspect R2.')
            simulator.instance = 'replacement-panel'
            finish(agent, 'Continue.')
            agent.reset()
            self.assertEqual(agent.memory.history(), [])
            finish(agent, 'Start a separate lab.')
        self.assertEqual(len(simulator.calls), 3)
        self.assertNotIn('Inspect R2.', json.dumps(client.histories[-1]))

    def test_memory_budget_preserves_initial_requirements_and_marks_omissions(self):
        memory = SessionMemory()
        for i in range(80):
            run = {'status': 'done', 'answer': 'test', 'events': [
                {'kind': 'tool_result', 'name': 'run_cli', 'result': {'ok': True, 'output': 'x' * 200000}}]}
            memory.record('Exactly two PCs in VLAN 30.' if i == 0 else ('step ' + str(i)) * 1000, run)
        self.assertLessEqual(len(json.dumps(memory.payload())), LIMIT)
        self.assertIn('Exactly two PCs in VLAN 30', json.dumps(memory.payload()))
        self.assertGreater(memory.omitted_turns, 0)
        self.assertLessEqual(len(memory.turns), 12)


if __name__ == '__main__':
    unittest.main()
