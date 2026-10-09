# SPDX-License-Identifier: Apache-2.0
import json
import sys
import threading
import time
import tempfile
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent import Agent, Bridge, make_handler, validate_tool
from providers import ProviderStore


def await_run(agent, run_id):
    for _ in range(200):
        run = agent.view(run_id)
        if run['status'] != 'running':
            return run
        time.sleep(.005)
    raise AssertionError('Task did not finish')


class AgentTests(unittest.TestCase):
    def test_interrupted_build_retains_request_and_actual_partial_results(self):
        class Simulator:
            def execute(self, name, args, cancel):
                return {'ok': True, 'device': {'name': args['name'], 'model': args['model']}}
        class Client:
            def __init__(self):
                self.calls = 0
            def create(self, history, tools):
                self.calls += 1
                if self.calls == 1:
                    return {'output': [{'type': 'function_call', 'call_id': 'create-router', 'name': 'add_device',
                        'arguments': json.dumps({'type': 0, 'model': '2911', 'name': 'R2', 'x': 300, 'y': 100})}]}
                raise RuntimeError('Provider quota reached')
        agent = Agent(Simulator(), client=Client())
        run = await_run(agent, agent.start('Add two routers with four PCs each; exactly two PCs in VLAN 30.', 'execute'))
        self.assertEqual(run['status'], 'error')
        self.assertTrue(agent.history)
        summary = agent.history[-1]['content']
        self.assertIn('exactly two PCs in VLAN 30', summary)
        self.assertIn('"name": "R2"', summary)
        self.assertIn('Provider quota reached', summary)
        self.assertFalse(any(item.get('type') == 'function_call' for item in agent.history))

    def test_background_heartbeat_gap_does_not_report_disconnected(self):
        bridge = Bridge()
        bridge.last_seen = time.monotonic() - 8
        cancelled = threading.Event()
        cancelled.set()
        with self.assertRaisesRegex(RuntimeError, 'Stopped'):
            bridge.execute('inspect_topology', {}, cancelled)

    def test_missing_native_privilege_stops_build_without_reporting_completion(self):
        attempts = []
        class Simulator:
            def execute(self, name, args, cancel):
                attempts.append(name)
                return {'ok': False, 'error': 'IPC Call ERROR: Workspace - ExApp or Script Module does not have the necessary privilege for IPC call "getLogicalWorkspace"'}
        class Client:
            def create(self, history, tools):
                if attempts:
                    raise AssertionError('A denied permission must stop before another model request')
                return {'output': [{'type': 'function_call', 'call_id': 'router', 'name': 'add_device',
                    'arguments': json.dumps({'type': 0, 'model': '2911', 'name': 'Router0', 'x': 300, 'y': 100})}]}
        agent = Agent(Simulator(), client=Client())
        run = await_run(agent, agent.start('Build an inter-VLAN lab.', 'execute'))
        self.assertEqual(run['status'], 'error')
        self.assertEqual(attempts, ['add_device'])
        self.assertIn('required security permission', run['answer'])
        self.assertFalse(any(e['kind'] == 'assistant' for e in run['events']))

    def test_empty_topology_build_keeps_request_last_and_dispatches_creation(self):
        message = 'Build a new lab with one PC.'
        calls, histories = [], []

        class Simulator:
            def execute(self, name, args, cancel):
                calls.append(name)
                if name == 'inspect_topology':
                    return {'ok': True, 'device_count': int('add_device' in calls), 'link_count': 0, 'devices': []}
                return {'ok': True, 'device': {'name': args['name'], 'model': args['model']}}

        class Store:
            def read(self):
                return {'provider': 'gemini', 'models': {'gemini': 'test'}, 'max_steps': 5}
            def key(self, provider):
                return 'unit-test-key'

        class Client:
            def create(self, history, tools):
                histories.append(list(history))
                if len(histories) == 1:
                    self.first_tools = {t['name'] for t in tools}
                    return {'output': [{'type': 'function_call', 'call_id': 'create-pc', 'name': 'add_device',
                        'arguments': json.dumps({'type': 8, 'model': 'PC-PT', 'name': 'PC1', 'x': 100, 'y': 100})}]}
                if len(histories) == 2:
                    return {'output': [{'type': 'function_call', 'call_id': 'verify', 'name': 'inspect_topology', 'arguments': '{}'}]}
                return {'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': 'One PC created and observed.'}]}]}

        client = Client()
        agent = Agent(Simulator(), client=client)
        agent.config_store = Store()
        with patch('agent.ProviderClient', return_value=client):
            run = await_run(agent, agent.start(message, 'execute'))
        self.assertEqual(histories[0][-1], {'role': 'user', 'content': message})
        self.assertTrue(any('"device_count": 0' in item.get('content', '') for item in histories[0][:-1]))
        self.assertIn('add_device', client.first_tools)
        self.assertEqual(calls, ['inspect_topology', 'add_device', 'inspect_topology'])
        self.assertEqual(run['status'], 'done')

    def test_non_agent_modes_do_not_offer_creation_tools(self):
        for mode in ['ask', 'inspect', 'plan']:
            captured = []
            class Client:
                def create(self, history, tools):
                    captured.append((list(history), tools))
                    return {'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': 'Select Agent to build.'}]}]}
            agent = Agent(Bridge(), client=Client())
            run = await_run(agent, agent.start('Build an inter-VLAN lab.', mode))
            self.assertEqual(run['status'], 'done')
            self.assertEqual(captured[0][0][-1]['content'], 'Build an inter-VLAN lab.')
            self.assertFalse({'add_device', 'connect_devices', 'configure_host'} & {t['name'] for t in captured[0][1]})

    def test_incremental_run_reads_are_bounded_and_preserve_completion(self):
        agent = Agent(Bridge())
        events = [{'kind': 'assistant', 'text': str(i)} for i in range(121)]
        agent.runs['cursor-test'] = {'id': 'cursor-test', 'status': 'done', 'answer': 'Finished',
                                    'events': events, 'cancel': threading.Event()}
        received, cursor = [], 0
        while True:
            result = agent.view('cursor-test', cursor)
            self.assertLessEqual(len(result['events']), 50)
            self.assertNotIn('cancel', result)
            received.extend(result['events'])
            cursor = result['next_event']
            if not result['has_more']:
                break
        self.assertEqual(received, events)
        self.assertTrue(result['has_assistant'])
        self.assertEqual(result['answer'], 'Finished')
        self.assertEqual(agent.view('cursor-test', cursor)['events'], [])
        self.assertEqual(agent.view('cursor-test')['events'], events)
        for invalid in [-1, 122, '0']:
            with self.assertRaises(ValueError):
                agent.view('cursor-test', invalid)

    def test_discovery_uses_unsaved_key_without_changing_settings(self):
        with tempfile.TemporaryDirectory() as folder:
            agent = Agent(Bridge())
            agent.config_store = ProviderStore(folder)
            before = agent.config_store.public()
            server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(agent, 'test-token'))
            threading.Thread(target=server.serve_forever, daemon=True).start()
            try:
                request = urllib.request.Request(f'http://127.0.0.1:{server.server_port}/models',
                    headers={'Authorization': 'Bearer test-token', 'Content-Type': 'application/json'},
                    data=json.dumps({'provider': 'gemini', 'api_key': 'unsaved-test-key'}).encode())
                with patch('agent.discover_models', return_value=[{'id': 'gemini-test'}]) as discover:
                    with urllib.request.urlopen(request, timeout=2) as response:
                        self.assertEqual(json.load(response)['models'][0]['id'], 'gemini-test')
                discover.assert_called_once_with('gemini', 'unsaved-test-key')
                self.assertEqual(agent.config_store.public(), before)
                self.assertFalse(agent.config_store.keys_path.exists())
            finally:
                server.shutdown()
                server.server_close()

    def test_network_snapshot_does_not_use_the_model(self):
        class Client:
            def create(self, *_):
                raise AssertionError('Snapshot must not call OpenAI')

        bridge = Bridge()
        bridge.poll('window')
        agent = Agent(bridge, client=Client())
        run_id = agent.diagnose()
        for _ in range(100):
            job = bridge.poll('window')
            if job:
                break
            time.sleep(.005)
        self.assertEqual(job['tool'], 'inspect_topology')
        bridge.complete(job['id'], {'ok': True, 'device_count': 3, 'link_count': 2}, 'window')
        run = await_run(agent, run_id)
        self.assertEqual(run['status'], 'done')
        self.assertIn('3 devices, 2 links', run['answer'])
        self.assertEqual(agent.history, [])

    def test_incomplete_model_response_does_not_dispatch_actions(self):
        class Client:
            def create(self, *_):
                return {'status': 'incomplete', 'output': [{'type': 'function_call',
                    'call_id': 'bad', 'name': 'inspect_topology', 'arguments': '{}'}]}

        bridge = Bridge()
        agent = Agent(bridge, client=Client())
        run_id = agent.start('Inspect', 'inspect')
        self.assertEqual(await_run(agent, run_id)['status'], 'error')
        self.assertFalse(bridge.jobs)

    def test_tool_loop_preserves_reasoning_and_returns_actual_output(self):
        histories = []

        class Client:
            def create(self, history, tools):
                histories.append(list(history))
                if len(histories) == 1:
                    return {'status': 'completed', 'output': [
                        {'type': 'reasoning', 'id': 'reason', 'summary': []},
                        {'type': 'function_call', 'call_id': 'inspect', 'name': 'inspect_topology', 'arguments': '{}'}]}
                return {'status': 'completed', 'output': [{'type': 'message', 'role': 'assistant',
                        'content': [{'type': 'output_text', 'text': 'There are two devices.'}]}]}

        bridge = Bridge()
        bridge.poll('test-window')
        agent = Agent(bridge, client=Client())
        run_id = agent.start('Inspect the lab', 'inspect')
        for _ in range(100):
            job = bridge.poll('test-window')
            if job:
                break
            time.sleep(.005)
        self.assertEqual(job['tool'], 'inspect_topology')
        bridge.complete(job['id'], {'ok': True, 'device_count': 2}, 'test-window')
        run = await_run(agent, run_id)
        self.assertEqual(run['status'], 'done')
        self.assertEqual(run['answer'], 'There are two devices.')
        self.assertTrue(any(item.get('type') == 'reasoning' for item in histories[1]))
        self.assertEqual(json.loads(histories[1][-1]['output'])['device_count'], 2)

    def test_inspect_mode_rejects_configuration(self):
        with self.assertRaises(ValueError):
            validate_tool('run_cli', {'device': 'R1', 'command': 'configure terminal'}, 'inspect')
        validate_tool('run_cli', {'device': 'R1', 'command': 'show ip route'}, 'inspect')
        with self.assertRaises(ValueError):
            validate_tool('configure_host', {'device': 'PC1', 'port': 'FastEthernet0', 'address': '10.0.0.2', 'mask': '255.255.255.0', 'gateway': '10.0.0.1'}, 'inspect')

    def test_validation_rejects_bad_addresses_and_multiline_commands(self):
        for command in ['show ip route\nerase startup-config', 'reload', 'show ip route; reload']:
            with self.assertRaises(ValueError):
                validate_tool('run_cli', {'device': 'R1', 'command': command}, 'execute')
        with self.assertRaises(ValueError):
            validate_tool('test_ping', {'device': 'PC1', 'address': '10.0.0.999'}, 'execute')

    def test_cancelled_queued_job_cannot_execute(self):
        bridge = Bridge()
        bridge.poll('window')
        cancel = threading.Event()
        errors = []

        def work():
            try:
                bridge.execute('run_cli', {}, cancel)
            except RuntimeError as e:
                errors.append(str(e))

        thread = threading.Thread(target=work)
        thread.start()
        for _ in range(100):
            if bridge.jobs:
                break
            time.sleep(.005)
        cancel.set()
        thread.join(1)
        self.assertIsNone(bridge.poll('window'))
        self.assertTrue(errors)

    def test_bridge_rejects_second_window_and_wrong_results(self):
        bridge = Bridge()
        bridge.poll('first')
        with self.assertRaises(ValueError):
            bridge.poll('second')
        with self.assertRaises(ValueError):
            bridge.complete('id', {}, 'second')

    def test_disconnected_bridge_has_clear_failure(self):
        bridge = Bridge()
        with self.assertRaisesRegex(RuntimeError, 'disconnected'):
            bridge.execute('inspect_topology', {}, threading.Event())

    def test_http_authentication_host_and_custom_origin(self):
        agent = Agent(Bridge())
        agent.runs['incremental'] = {'id': 'incremental', 'status': 'done', 'answer': 'Done',
                                     'events': [{'kind': 'assistant', 'text': 'Done'}], 'cancel': threading.Event()}
        server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(agent, 'private-token'))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f'http://127.0.0.1:{server.server_port}'
        try:
            with self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(base + '/status')
            self.assertEqual(caught.exception.code, 403)
            request = urllib.request.Request(base + '/status', headers={'Authorization': 'Bearer private-token', 'Origin': 'null'})
            with urllib.request.urlopen(request) as response:
                self.assertEqual(response.headers['Access-Control-Allow-Origin'], '*')
                self.assertIn('model', json.load(response))
            request = urllib.request.Request(base + '/status', method='OPTIONS', headers={'Origin': 'pt-sm:', 'Access-Control-Request-Headers': 'authorization', 'Access-Control-Request-Private-Network': 'true'})
            with urllib.request.urlopen(request) as response:
                self.assertEqual(response.headers['Access-Control-Allow-Origin'], '*')
                self.assertEqual(response.headers['Access-Control-Allow-Private-Network'], 'true')
                self.assertEqual(response.headers['Access-Control-Max-Age'], '600')
            request = urllib.request.Request(base + '/runs/incremental?after=1', headers={'Authorization': 'Bearer private-token'})
            with urllib.request.urlopen(request) as response:
                result = json.load(response)
                self.assertEqual(result['events'], [])
                self.assertEqual(result['next_event'], 1)
                self.assertTrue(result['has_assistant'])
            request = urllib.request.Request(base + '/runs/previous-service-run', headers={'Authorization': 'Bearer private-token'})
            with self.assertRaises(urllib.error.HTTPError) as missing:
                urllib.request.urlopen(request)
            self.assertEqual(missing.exception.code, 404)
            with missing.exception:
                self.assertIn('history is unavailable', json.load(missing.exception)['error'])
            request = urllib.request.Request(base + '/bridge/poll', headers={'Authorization': 'Bearer private-token'},
                data=json.dumps({'instance': 'test-window', 'include_status': True}).encode())
            with urllib.request.urlopen(request) as response:
                result = json.load(response)
                self.assertIsNone(result['job'])
                self.assertTrue(result['status']['connected'])
            request = urllib.request.Request(base + '/status', headers={'Authorization': 'Bearer private-token', 'Host': 'attacker.example'})
            with self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(request)
            self.assertEqual(caught.exception.code, 403)
        finally:
            server.shutdown()
            server.server_close()


if __name__ == '__main__':
    unittest.main()
