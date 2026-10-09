# SPDX-License-Identifier: Apache-2.0
import json
import io
import os
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from providers import ProviderStore, ProviderClient, discover_models, request_json
from agent import TOOLS, INSTRUCTIONS, validate_tool


class ProviderTests(unittest.TestCase):
    def test_temporary_provider_outage_retries_then_succeeds(self):
        outage = lambda: urllib.error.HTTPError('https://provider.test', 503, 'Unavailable', {}, io.BytesIO())
        with patch('providers.urllib.request.urlopen', side_effect=[outage(), outage(), io.BytesIO(b'{"ok":true}')]) as transport, patch('providers.time.sleep') as sleep:
            self.assertTrue(request_json('https://provider.test', {'x-goog-api-key': 'private-test-key'}, label='Gemini')['ok'])
        self.assertEqual(transport.call_count, 3)
        self.assertEqual(sleep.call_count, 2)

    def test_persistent_outage_is_bounded_and_auth_errors_are_not_retried(self):
        for code, attempts, headers in [(503, 3, {}), (401, 1, {}), (429, 1, {}), (503, 1, {'Retry-After': '60'})]:
            errors = [urllib.error.HTTPError('https://provider.test', code, 'Failure', headers, io.BytesIO()) for _ in range(attempts)]
            with patch('providers.urllib.request.urlopen', side_effect=errors) as transport, patch('providers.time.sleep'):
                with self.assertRaises(RuntimeError) as caught:
                    request_json('https://provider.test', {'x-goog-api-key': 'private-test-key'}, label='Gemini')
            self.assertEqual(transport.call_count, attempts)
            self.assertNotIn('private-test-key', str(caught.exception))
            if code == 503:
                self.assertIn('temporarily unavailable', str(caught.exception))

    def test_provider_settings_keep_keys_private_and_preserve_blank_key(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {}, clear=True):
            store = ProviderStore(folder)
            state = store.save({'provider': 'gemini', 'model': 'gemini-test', 'api_key': 'unit-test-key', 'max_steps': 20})
            self.assertNotIn('unit-test-key', json.dumps(state))
            self.assertTrue(state['providers']['gemini']['key_configured'])
            self.assertEqual(store.keys_path.stat().st_mode & 0o777, 0o600)
            store.save({'provider': 'gemini', 'model': 'gemini-other', 'api_key': '', 'max_steps': 20})
            self.assertEqual(store.key('gemini'), 'unit-test-key')
            self.assertEqual(store.read()['models']['gemini'], 'gemini-other')
            with self.assertRaises(ValueError):
                store.save({'provider': 'evil', 'model': 'model', 'api_key': '', 'max_steps': 20})

    def test_openrouter_routing_errors_explain_parameters_and_privacy(self):
        for detail, expected in [
            ('No endpoints found that can handle the requested parameters.', 'tool-calling parameters'),
            ('No endpoints found matching your data policy.', 'account privacy'),
            ('No endpoints found for vendor/model.', 'No usable endpoint'),
        ]:
            error = urllib.error.HTTPError('https://provider.test', 404, 'Not found', {},
                io.BytesIO(json.dumps({'error': {'message': detail + ' secret-provider-data'}}).encode()))
            with patch('providers.urllib.request.urlopen', side_effect=error) as transport:
                with self.assertRaises(RuntimeError) as caught:
                    request_json('https://provider.test', {}, label='OpenRouter')
            self.assertEqual(transport.call_count, 1)
            self.assertIn(expected, str(caught.exception))
            self.assertNotIn('secret-provider-data', str(caught.exception))

    def test_legacy_openai_key_and_model_migration(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {}, clear=True):
            path = Path(folder)
            (path / 'settings.json').write_text(json.dumps({'token': 'never-public', 'model': 'gpt-test'}))
            (path / 'openai-key').write_text('legacy-unit-key')
            store = ProviderStore(path)
            self.assertEqual(store.read()['models']['openai'], 'gpt-test')
            self.assertEqual(store.key('openai'), 'legacy-unit-key')
            self.assertNotIn('never-public', json.dumps(store.public()))
            self.assertNotIn('legacy-unit-key', json.dumps(store.public()))

    def test_gemini_tool_roundtrip_preserves_thought_signature(self):
        native = {'role': 'model', 'parts': [{'functionCall': {'id': 'native-id', 'name': 'inspect_topology', 'args': {}}, 'thoughtSignature': 'opaque-test-signature'}]}
        responses = [
            {'candidates': [{'finishReason': 'STOP', 'content': native}]},
            {'candidates': [{'finishReason': 'STOP', 'content': {'role': 'model', 'parts': [{'text': 'Two devices.'}]}}]},
        ]
        captured = []
        def transport(url, headers, body=None, *args, **kwargs):
            captured.append((url, headers, body))
            return responses.pop(0)
        with patch('providers.request_json', side_effect=transport):
            client = ProviderClient('gemini', 'gemini-test', 'unit-key', INSTRUCTIONS)
            history = [{'role': 'user', 'content': 'Inspect'}]
            first = client.create(history, TOOLS)
            history.extend(first['output'])
            history.append({'type': 'function_call_output', 'call_id': 'native-id', 'output': '{"ok":true,"device_count":2}'})
            second = client.create(history, TOOLS)
        self.assertEqual(captured[1][2]['contents'][1]['parts'][0]['thoughtSignature'], 'opaque-test-signature')
        response = captured[1][2]['contents'][2]['parts'][0]['functionResponse']
        self.assertEqual(response['id'], 'native-id')
        self.assertEqual(response['name'], 'inspect_topology')
        self.assertEqual(response['response']['result']['device_count'], 2)
        self.assertNotIn('additionalProperties', json.dumps(captured[0][2]['tools']))
        self.assertEqual(second['output'][1]['content'][0]['text'], 'Two devices.')

    def test_openrouter_tool_roundtrip_preserves_provider_reasoning(self):
        raw = {'role': 'assistant', 'content': None, 'reasoning_details': [{'type': 'reasoning.encrypted', 'data': 'opaque'}],
               'tool_calls': [{'id': 'call1', 'type': 'function', 'function': {'name': 'inspect_topology', 'arguments': '{}'}}]}
        responses = [{'choices': [{'message': raw, 'finish_reason': 'tool_calls'}]},
                     {'choices': [{'message': {'role': 'assistant', 'content': 'Verified.'}, 'finish_reason': 'stop'}]}]
        captured = []
        def transport(url, headers, body=None, *args, **kwargs):
            captured.append(body)
            return responses.pop(0)
        with patch('providers.request_json', side_effect=transport):
            client = ProviderClient('openrouter', 'vendor/model', 'unit-key', INSTRUCTIONS)
            history = [{'role': 'user', 'content': 'Inspect'}]
            first = client.create(history, TOOLS)
            history.extend(first['output'])
            history.append({'type': 'function_call_output', 'call_id': 'call1', 'output': '{"ok":true}'})
            second = client.create(history, TOOLS)
        self.assertEqual(captured[1]['messages'][2]['reasoning_details'], raw['reasoning_details'])
        self.assertEqual(captured[1]['messages'][3]['tool_call_id'], 'call1')
        self.assertNotIn('parallel_tool_calls', captured[0])
        self.assertTrue(captured[0]['provider']['require_parameters'])
        self.assertEqual(captured[0]['tools'][0]['type'], 'function')
        self.assertEqual(second['output'][1]['content'][0]['text'], 'Verified.')

    def test_openai_uses_responses_and_stateless_reasoning(self):
        with patch('providers.request_json', return_value={'status': 'completed', 'output': []}) as transport:
            ProviderClient('openai', 'gpt-test', 'unit-key', INSTRUCTIONS).create([], TOOLS)
        args = transport.call_args.args
        self.assertEqual(args[0], 'https://api.openai.com/v1/responses')
        self.assertFalse(args[2]['store'])
        self.assertIn('reasoning.encrypted_content', args[2]['include'])

    def test_model_discovery_filters_generation_and_marks_tool_support(self):
        with patch('providers.request_json', return_value={'models': [
            {'name': 'models/gemini-test', 'supportedGenerationMethods': ['generateContent']},
            {'name': 'models/embed-test', 'supportedGenerationMethods': ['embedContent']}]}):
            models = discover_models('gemini', 'unit-key')
        self.assertEqual([m['id'] for m in models], ['gemini-test'])
        with patch('providers.request_json', return_value={'data': [
            {'id': 'chat/model', 'supported_parameters': []},
            {'id': 'agent/model', 'supported_parameters': ['tools']}]}):
            models = discover_models('openrouter', 'unit-key')
        self.assertTrue(models[0]['tools'])
        self.assertFalse(models[1]['tools'])

    def test_plan_mode_cannot_configure_but_can_update_plan(self):
        with self.assertRaises(ValueError):
            validate_tool('run_cli', {'device': 'R1', 'command': 'configure terminal'}, 'plan')
        validate_tool('set_plan', {'steps': [{'title': 'Inspect the network', 'status': 'pending'}]}, 'plan')
        with self.assertRaises(ValueError):
            validate_tool('set_plan', {'steps': [{'title': 'Bad status', 'status': 'invented'}]}, 'execute')


if __name__ == '__main__':
    unittest.main()
