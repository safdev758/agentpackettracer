# SPDX-License-Identifier: Apache-2.0
import json
import sys
import threading
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from codex_worker import CodexClient, trigger_message, worker_command
from agent import Agent, INSTRUCTIONS, validate_tool
from test_agent import await_run


class CodexTests(unittest.TestCase):
    def test_worker_disables_existing_connectors_without_editing_config(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'config.toml'
            source = '[mcp_servers.example]\nenabled=true\n[plugins."example@store"]\nenabled=true\n'
            path.write_text(source)
            with patch.dict('os.environ', {'CODEX_HOME': folder}):
                command = worker_command('/usr/bin/codex')
            self.assertIn('mcp_servers={"example"={enabled=false}}', command)
            self.assertIn('plugins={"example@store"={enabled=false}}', command)
            self.assertEqual(path.read_text(), source)
    def test_inspection_can_wake_or_cancel_terminal_without_configuration(self):
        for command in ['', '\x03', 'enable', 'show ip interface brief']:
            validate_tool('run_cli', {'device': 'R2', 'command': command}, 'inspect')
        with self.assertRaisesRegex(ValueError, 'Execute mode'):
            validate_tool('run_cli', {'device': 'R2', 'command': 'configure terminal'}, 'inspect')
    def test_explicit_trigger_only(self):
        self.assertEqual(trigger_message('  @CODEX inspect this lab'), 'inspect this lab')
        self.assertEqual(trigger_message('@codex'), '')
        self.assertIsNone(trigger_message('explain @codex'))
        self.assertIsNone(trigger_message('@codex-other inspect'))

    def test_native_tool_roundtrip_and_failed_completion(self):
        client = CodexClient(INSTRUCTIONS, threading.Event())
        client.process = object()
        sent = []
        client.send = sent.append
        client.messages.put({'id': 90, 'method': 'item/tool/call', 'params': {
            'callId': 'native-call', 'tool': 'inspect_topology', 'arguments': {}}})
        first = client.create([], [])
        self.assertEqual(first['output'][0]['name'], 'inspect_topology')
        client.messages.put({'method': 'item/completed', 'params': {
            'item': {'type': 'agentMessage', 'text': 'Actual inspection completed.'}}})
        client.messages.put({'method': 'turn/completed', 'params': {'turn': {'status': 'completed'}}})
        answer = client.create([{'type': 'function_call_output', 'call_id': 'native-call',
            'output': json.dumps({'ok': True, 'device_count': 15})}], [])
        self.assertEqual(sent[0]['id'], 90)
        self.assertIn('15', sent[0]['result']['contentItems'][0]['text'])
        self.assertEqual(answer['output'][0]['content'][0]['text'], 'Actual inspection completed.')
        client.messages.put({'method': 'turn/completed', 'params': {
            'turn': {'status': 'failed', 'error': {'message': 'Quota reached'}}}})
        with self.assertRaisesRegex(RuntimeError, 'failed.*Quota'):
            client.create([], [])

    def test_cancel_interrupts_wait_without_pending_model_response(self):
        cancel = threading.Event()
        client = CodexClient(INSTRUCTIONS, cancel)
        client.process = object()
        cancel.set()
        with self.assertRaisesRegex(RuntimeError, 'Stopped'):
            client.create([], [])

    def test_trigger_preserves_provider_settings_and_inspect_permissions(self):
        clients, dispatched = [], []
        class Store:
            def read(self):
                return {'provider': 'openrouter', 'models': {'openrouter': 'saved-free'}, 'max_steps': 4}
            def key(self, provider):
                raise AssertionError('Codex must not request provider API keys')
        class Simulator:
            def execute(self, name, args, cancel):
                dispatched.append(name)
                return {'ok': True, 'device_count': 15, 'devices': []}
        class FakeCodex(CodexClient):
            def __init__(self, instructions, cancel):
                super().__init__(instructions, cancel)
                clients.append(self)
                self.calls = 0
                self.closed = False
            def create(self, history, tools):
                self.calls += 1
                if self.calls == 1:
                    self.asserted_request = history[-1]['content']
                    self.asserted_tools = {t['name'] for t in tools}
                    return {'output': [{'type': 'function_call', 'call_id': 'bad',
                        'name': 'add_device', 'arguments': json.dumps({
                            'type': 0, 'model': '2911', 'name': 'Bad', 'x': 1, 'y': 1})}]}
                assert json.loads(history[-1]['output'])['ok'] is False
                return {'output': [self.text_item('Inspect mode cannot add devices.')]}
            def close(self):
                self.closed = True
        agent = Agent(Simulator())
        agent.config_store = Store()
        with patch('agent.CodexClient', FakeCodex):
            run = await_run(agent, agent.start('@codex inspect this lab', 'inspect'))
        self.assertEqual(run['provider'], 'codex')
        self.assertEqual(run['status'], 'done')
        self.assertEqual(dispatched, ['inspect_topology'])
        self.assertNotIn('add_device', clients[0].asserted_tools)
        self.assertEqual(clients[0].asserted_request, 'inspect this lab')
        self.assertTrue(clients[0].closed)
        self.assertEqual(agent.config_store.read()['provider'], 'openrouter')
        with self.assertRaisesRegex(ValueError, 'Add a request'):
            agent.start('@codex', 'execute')


if __name__ == '__main__':
    unittest.main()
