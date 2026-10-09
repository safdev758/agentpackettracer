# SPDX-License-Identifier: Apache-2.0
"""Provider credentials, model discovery, and native tool-calling adapters."""
from __future__ import annotations
import copy
import json
import math
import os
import re
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from email.utils import parsedate_to_datetime
from pathlib import Path

PROVIDERS = {
    'openai': {'label': 'OpenAI', 'default_model': 'gpt-6.1-sol', 'env': 'OPENAI_API_KEY'},
    'gemini': {'label': 'Google Gemini', 'default_model': '', 'env': 'GEMINI_API_KEY'},
    'openrouter': {'label': 'OpenRouter', 'default_model': '', 'env': 'OPENROUTER_API_KEY'},
}


def private_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temp = path.with_name(path.name + '.' + secrets.token_hex(5) + '.tmp')
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(data, f)
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


class ProviderStore:
    def __init__(self, folder):
        self.folder = Path(folder)
        self.lock = threading.RLock()
        self.path = self.folder / 'providers.json'
        self.keys_path = self.folder / 'provider-keys.json'

    def read(self):
        with self.lock:
            if self.path.exists():
                return json.loads(self.path.read_text())
            previous = self.folder / 'settings.json'
            old = json.loads(previous.read_text()) if previous.exists() else {}
            return {'provider': 'openai', 'models': {'openai': old.get('model', 'gpt-6.1-sol'), 'gemini': '', 'openrouter': ''}, 'max_steps': 40}

    def key(self, provider):
        if provider not in PROVIDERS:
            raise ValueError('Unsupported provider')
        with self.lock:
            if os.environ.get(PROVIDERS[provider]['env']):
                return os.environ[PROVIDERS[provider]['env']]
            saved = json.loads(self.keys_path.read_text()) if self.keys_path.exists() else {}
            if saved.get(provider):
                return saved[provider]
            legacy = self.folder / 'openai-key'
            if provider == 'openai' and legacy.exists():
                return legacy.read_text().strip()
            return ''

    def public(self):
        config = self.read()
        return {**config, 'providers': {p: {'label': meta['label'], 'key_configured': bool(self.key(p)),
                'environment_key': bool(os.environ.get(meta['env']))} for p, meta in PROVIDERS.items()}}

    def save(self, data):
        provider = data.get('provider')
        model = data.get('model', '')
        if not isinstance(model, str):
            raise ValueError('Invalid model ID')
        model = model.strip()
        key = data.get('api_key', '')
        max_steps = data.get('max_steps', 40)
        if provider not in PROVIDERS or not isinstance(key, str) or len(key) > 4096:
            raise ValueError('Invalid provider or API key')
        if model and not re.fullmatch(r'[A-Za-z0-9_./:@+\-]{1,200}', model):
            raise ValueError('Enter a valid model ID')
        if type(max_steps) is not int or not 4 <= max_steps <= 80:
            raise ValueError('Task step limit must be between 4 and 80')
        with self.lock:
            config = self.read()
            config['provider'] = provider
            config['models'][provider] = model
            config['max_steps'] = max_steps
            if key.strip():
                keys = json.loads(self.keys_path.read_text()) if self.keys_path.exists() else {}
                keys[provider] = key.strip()
                private_json(self.keys_path, keys)
            private_json(self.path, config)
        return self.public()


def request_json(url, headers, body=None, label='Provider', timeout=90):
    request = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None,
                                    headers={'Content-Type': 'application/json', **headers})
    deadline = time.monotonic() + timeout
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=max(.1, deadline - time.monotonic())) as response:
                return json.load(response)
        except urllib.error.HTTPError as e:
            code = e.code
            retry_after = e.headers.get('Retry-After', '') if e.headers else ''
            routing_message = ''
            if label == 'OpenRouter' and code == 404:
                try:
                    detail = json.loads(e.read(65536)).get('error', {}).get('message', '').lower()
                    if 'data policy' in detail or 'privacy' in detail or 'guardrail' in detail:
                        routing_message = 'No endpoint matches your account privacy or guardrail settings. Review https://openrouter.ai/settings/privacy.'
                    elif 'parameter' in detail or 'tool' in detail:
                        routing_message = 'No endpoint supports the requested tool-calling parameters. Try openrouter/free or another tool-capable model.'
                    elif 'no endpoints' in detail or 'no allowed providers' in detail:
                        routing_message = 'No usable endpoint is available for this model. Try openrouter/free or check your provider restrictions.'
                except (ValueError, AttributeError, TypeError, OSError):
                    pass
            e.close()
            if code in {500, 502, 503, 504} and attempt < 2:
                delay = 2 ** attempt + secrets.randbelow(251) / 1000
                if retry_after:
                    try:
                        requested = float(retry_after)
                    except ValueError:
                        try:
                            requested = parsedate_to_datetime(retry_after).timestamp() - time.time()
                        except (ValueError, TypeError, OverflowError):
                            requested = 0
                    if math.isfinite(requested):
                        delay = max(delay, requested)
                # Never shorten a provider cooldown or let retries hold a task indefinitely.
                if delay <= 8 and delay < deadline - time.monotonic():
                    time.sleep(delay)
                    continue
            message = {400: 'The provider rejected the request or this model does not support tools.',
                       401: 'The API key is invalid.', 402: 'API credits or billing are required.',
                       403: 'Access to this model or API is denied.', 404: 'This model or API endpoint was not found.',
                       429: 'Rate limit or quota reached. Wait or check your API quota.',
                       500: 'The provider has a temporary server error. Retry in a moment.',
                       502: 'The provider gateway is temporarily unavailable. Retry in a moment.',
                       503: 'The provider is temporarily unavailable or overloaded. Retry in a moment or choose another model.',
                       504: 'The provider gateway timed out. Retry in a moment.'}.get(code, 'The provider could not complete the request.')
            suffix = f' ({attempt + 1} attempts.)' if attempt else ''
            raise RuntimeError(f'{label} HTTP {code}: {routing_message or message}{suffix}') from None
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            raise RuntimeError(f'{label} could not be reached or returned an invalid response. Check internet access and retry.') from None


def discover_models(provider, key):
    if provider not in PROVIDERS:
        raise ValueError('Unsupported provider')
    label = PROVIDERS[provider]['label']
    if not key:
        raise ValueError('Enter and save an API key first')
    if provider == 'gemini':
        models, next_page = [], ''
        for _ in range(10):
            url = 'https://generativelanguage.googleapis.com/v1beta/models?pageSize=1000'
            if next_page:
                url += '&pageToken=' + urllib.parse.quote(next_page, safe='')
            result = request_json(url, {'x-goog-api-key': key}, label=label, timeout=30)
            models.extend({'id': m['name'].removeprefix('models/'), 'name': m.get('displayName', m['name']), 'tools': None}
                          for m in result.get('models', []) if 'generateContent' in m.get('supportedGenerationMethods', []))
            next_page = result.get('nextPageToken', '')
            if not next_page:
                break
    else:
        base = 'https://api.openai.com/v1/models' if provider == 'openai' else 'https://openrouter.ai/api/v1/models'
        result = request_json(base, {'Authorization': 'Bearer ' + key}, label=label, timeout=30)
        models = []
        for m in result.get('data', []):
            ident = m['id']
            if provider == 'openai' and not ident.startswith(('gpt-', 'o1', 'o3', 'o4', 'chatgpt-')):
                continue
            supported = m.get('supported_parameters', [])
            models.append({'id': ident, 'name': m.get('name', ident), 'tools': ('tools' in supported) if provider == 'openrouter' else None})
    return sorted(models, key=lambda m: (m.get('tools') is False, m['id']))


class ProviderClient:
    def __init__(self, provider, model, key, instructions):
        self.provider, self.model, self.key, self.instructions = provider, model, key, instructions

    def create(self, history, tools):
        if not self.key:
            raise RuntimeError('API key is missing. Open Settings in the Agent panel and save a provider key.')
        if not self.model:
            raise RuntimeError('No model is selected. Open Settings, fetch the models, and select one.')
        if self.provider == 'openai':
            return request_json('https://api.openai.com/v1/responses', {'Authorization': 'Bearer ' + self.key},
                {'model': self.model, 'input': history, 'instructions': self.instructions, 'tools': tools,
                 'parallel_tool_calls': False, 'store': False, 'include': ['reasoning.encrypted_content'], 'max_output_tokens': 7000}, 'OpenAI')
        if self.provider == 'gemini':
            return self.gemini(history, tools)
        return self.openrouter(history, tools)

    def openrouter(self, history, tools):
        messages = [{'role': 'system', 'content': self.instructions}]
        for item in history:
            if item.get('role') == 'user':
                messages.append({'role': 'user', 'content': item['content']})
            elif item.get('type') == 'provider_message':
                messages.append(item['message'])
            elif item.get('type') == 'function_call_output':
                messages.append({'role': 'tool', 'tool_call_id': item['call_id'], 'content': item['output']})
        body = {'model': self.model, 'messages': messages, 'max_tokens': 7000}
        if tools:
            body['tools'] = [{'type': 'function', 'function': {k: t[k] for k in ('name', 'description', 'parameters')}} for t in tools]
            # Most free endpoints support tools but do not advertise this optional
            # parameter. Requiring it filters them all out with HTTP 404. The
            # Agent executes returned calls sequentially in its own tool loop.
            body['provider'] = {'require_parameters': True}
        result = request_json('https://openrouter.ai/api/v1/chat/completions', {'Authorization': 'Bearer ' + self.key, 'X-Title': 'Packet Tracer Agent'}, body, 'OpenRouter')
        if result.get('error') or not result.get('choices'):
            raise RuntimeError('OpenRouter returned no usable response. Check model availability.')
        choice = result['choices'][0]
        if choice.get('finish_reason') in ('length', 'error', 'content_filter'):
            return {'status': 'incomplete', 'output': []}
        raw = choice['message']
        output = [{'type': 'provider_message', 'message': raw}]
        if raw.get('content'):
            output.append({'type': 'message', 'content': [{'type': 'output_text', 'text': raw['content']}]})
        for call in raw.get('tool_calls', []):
            output.append({'type': 'function_call', 'call_id': call['id'], 'name': call['function']['name'], 'arguments': call['function']['arguments']})
        return {'status': 'completed', 'output': output, 'usage': result.get('usage', {})}

    def gemini(self, history, tools):
        contents, names = [], {}
        for item in history:
            if item.get('role') == 'user':
                contents.append({'role': 'user', 'parts': [{'text': item['content']}]})
            elif item.get('type') == 'provider_message':
                # Keep thought signatures and the original parts intact across tool turns.
                contents.append(copy.deepcopy(item['content']))
            elif item.get('type') == 'function_call':
                names[item['call_id']] = (item['name'], item.get('native_call_id'))
            elif item.get('type') == 'function_call_output':
                name, native_id = names[item['call_id']]
                response = {'name': name, 'response': {'result': json.loads(item['output'])}}
                if native_id:
                    response['id'] = native_id
                part = {'functionResponse': response}
                if contents and contents[-1]['role'] == 'user' and all('functionResponse' in p for p in contents[-1]['parts']):
                    contents[-1]['parts'].append(part)
                else:
                    contents.append({'role': 'user', 'parts': [part]})
        body = {'contents': contents, 'systemInstruction': {'parts': [{'text': self.instructions}]},
                'generationConfig': {'maxOutputTokens': 7000}}
        if tools:
            declarations = []
            for t in tools:
                params = copy.deepcopy(t['parameters'])
                def clean_schema(value):
                    if isinstance(value, dict):
                        return {k: clean_schema(v) for k, v in value.items() if k != 'additionalProperties'}
                    if isinstance(value, list):
                        return [clean_schema(v) for v in value]
                    return value
                params = clean_schema(params)
                declarations.append({'name': t['name'], 'description': t['description'], 'parameters': params})
            body['tools'] = [{'functionDeclarations': declarations}]
        model = self.model.removeprefix('models/')
        result = request_json('https://generativelanguage.googleapis.com/v1beta/models/' + urllib.parse.quote(model, safe='') + ':generateContent',
                              {'x-goog-api-key': self.key}, body, 'Gemini')
        if not result.get('candidates'):
            raise RuntimeError('Gemini returned no usable response. Check the prompt and model access.')
        candidate = result['candidates'][0]
        if candidate.get('finishReason') not in (None, 'STOP'):
            return {'status': 'incomplete', 'output': []}
        content = candidate.get('content', {'role': 'model', 'parts': []})
        output = [{'type': 'provider_message', 'content': content}]
        for index, part in enumerate(content.get('parts', [])):
            if part.get('text') and not part.get('thought'):
                output.append({'type': 'message', 'content': [{'type': 'output_text', 'text': part['text']}]})
            if part.get('functionCall'):
                call = part['functionCall']
                output.append({'type': 'function_call', 'call_id': call.get('id') or secrets.token_hex(10),
                    'native_call_id': call.get('id'), 'name': call['name'], 'arguments': json.dumps(call.get('args', {}))})
        return {'status': 'completed', 'output': output, 'usage': result.get('usageMetadata', {})}
