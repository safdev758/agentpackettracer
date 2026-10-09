# SPDX-License-Identifier: Apache-2.0
"""Headless browser UI checks with a mocked service; no provider calls or real keys."""
import json
import os
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PREVIEW = ROOT / 'dist' / 'preview'
PREVIEW.mkdir(parents=True, exist_ok=True)
for filename in ['index.html', 'styles.css', 'ui.js']:
    (PREVIEW / filename).write_text((ROOT / 'extension' / filename).read_text().replace('__BRIDGE_TOKEN__', '"ui-test-token"'))

config = {'provider': 'openai', 'models': {'openai': 'gpt-test', 'gemini': '', 'openrouter': ''}, 'max_steps': 40,
          'providers': {p: {'label': p, 'key_configured': False, 'environment_key': False} for p in ['openai', 'gemini', 'openrouter']}}
submitted = []
model_requests = []
models_error = False
snapshot = {'ok': True, 'device_count': 1, 'link_count': 0, 'devices': [{'name': 'PC1', 'model': 'PC-PT', 'ports': [{'name': 'FastEthernet0', 'up': True, 'address': '192.168.1.2'}]}]}


def route_service(route):
    request = route.request
    parsed = urlsplit(request.url)
    path = parsed.path
    data = json.loads(request.post_data or '{}')
    if path == '/status':
        answer = {'connected': False, 'key_configured': config['providers'][config['provider']]['key_configured'], 'provider': config['provider'], 'model': config['models'][config['provider']], 'active_run': None, 'service_version': '0.2.0'}
    elif path == '/config':
        if request.method == 'POST':
            config['provider'] = data['provider']
            config['models'][data['provider']] = data['model']
            config['max_steps'] = data['max_steps']
            if data['api_key']:
                config['providers'][data['provider']]['key_configured'] = True
        answer = config
    elif path == '/models':
        model_requests.append(data)
        if models_error:
            route.fulfill(status=400, content_type='application/json', body=json.dumps({'error': 'Gemini HTTP 429: Rate limit or quota reached.'}))
            return
        answer = {'provider': data['provider'], 'models': [{'id': data['provider'] + '-test', 'name': 'Test model', 'tools': True}]}
    elif path == '/diagnose':
        answer = {'id': 'diagnostic'}
    elif path == '/chat':
        submitted.append(data)
        answer = {'id': 'chat'}
    elif path == '/runs/diagnostic':
        answer = {'id': 'diagnostic', 'status': 'done', 'answer': 'Snapshot read.', 'events': [{'kind': 'tool_result', 'name': 'inspect_topology', 'result': snapshot}]}
    elif path == '/runs/chat':
        answer = {'id': 'chat', 'status': 'done', 'answer': 'UI test response', 'plan': [{'title': 'Check context', 'status': 'done'}], 'events': [{'kind': 'assistant', 'text': 'UI test response'}]}
    elif path == '/runs/expired':
        route.fulfill(status=404, content_type='application/json', body=json.dumps({'error': 'Task history is unavailable.'}))
        return
    else:
        answer = {'ok': True, 'job': None}
    if path.startswith('/runs/') and 'events' in answer:
        after = int(parse_qs(parsed.query).get('after', ['0'])[0])
        events = answer['events']
        answer.update(events=events[after:after + 50], next_event=min(after + 50, len(events)),
                      has_more=after + 50 < len(events), has_assistant=any(e['kind'] == 'assistant' for e in events))
    route.fulfill(status=200, content_type='application/json', body=json.dumps(answer), headers={'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': 'Authorization, Content-Type', 'Access-Control-Allow-Methods': 'GET, POST, OPTIONS'})


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=os.environ.get('CHROME_EXECUTABLE') or None, headless=True)
    page = browser.new_page(viewport={'width': 520, 'height': 900})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.route('http://127.0.0.1:54123/**', route_service)
    page.goto((PREVIEW / 'index.html').as_uri())
    page.wait_for_function('document.getElementById("status").textContent.includes("Service connected")')
    page.evaluate('window.agentWindowState(true)')
    assert page.locator('#expand-chat').inner_text() == 'Resize'
    assert page.locator('#expand-chat').get_attribute('aria-pressed') == 'true'
    page.evaluate('window.agentWindowState(false)')
    assert page.locator('#expand-chat').inner_text() == 'Expand'
    page.screenshot(path=str(ROOT / 'dist' / 'chat-preview.png'))
    page.locator('[data-tab=settings]').click()
    page.locator('#provider').select_option('gemini')
    page.locator('#api-key').fill('fake-ui-test-key')
    page.locator('#model').fill('invalid model with spaces')
    page.locator('#load-models').click()
    page.wait_for_function('document.getElementById("model-list").options.length === 2')
    assert config['provider'] == 'openai', 'Discovery must not save or activate unfinished settings'
    assert model_requests[-1]['api_key'] == 'fake-ui-test-key'
    assert page.locator('#api-key').input_value() == 'fake-ui-test-key'
    assert page.locator('#model').input_value() == 'gemini-test'
    page.locator('#model-list').select_option('gemini-test')
    page.locator('#save-settings').click()
    page.wait_for_function('document.getElementById("settings-status").textContent.startsWith("Saved")')
    assert page.locator('#api-key').input_value() == ''
    assert config['models']['gemini'] == 'gemini-test'
    # A manual check must run even while the periodic poll is occupied.
    page.evaluate('polling = true')
    page.locator('#test-service').click()
    page.wait_for_function('document.getElementById("connection-result").textContent.includes("key accepted")')
    assert not page.locator('#test-service').is_disabled()
    page.evaluate('polling = false')
    models_error = True
    page.locator('#test-service').click()
    page.wait_for_function('document.getElementById("connection-result").textContent.includes("429")')
    assert not page.locator('#test-service').is_disabled()
    models_error = False
    page.screenshot(path=str(ROOT / 'dist' / 'settings-preview.png'))
    page.locator('[data-tab=network]').click()
    page.locator('#snapshot').click()
    page.wait_for_selector('.device-card')
    page.locator('.device-card button').click()
    assert page.locator('#context-device').input_value() == 'PC1'
    page.locator('#prompt').fill('Use this device context')
    page.locator('#send').click()
    page.wait_for_function('document.getElementById("messages").textContent.includes("UI test response")')
    assert submitted[0]['context_device'] == 'PC1'
    assert submitted[0]['mode'] == 'execute'
    assert page.locator('#plan-steps').inner_text().endswith('Check context')
    page.evaluate('''async () => {
        runId='expired';seen=500;await tick();
    }''')
    page.wait_for_function('runId === null')
    assert page.locator('#status').inner_text().startswith('Service connected')
    assert page.locator('#taskstate').inner_text() == 'Previous task history unavailable'
    previous_rows=page.locator('.tool-row').count()
    page.evaluate('''() => {
        toolEvent({kind:'tool_start',name:'run_cli',args:{command:'show ip route'}});
        toolEvent({kind:'tool_result',name:'run_cli',result:{ok:true,output:'Routes verified'}});
    }''')
    assert page.locator('.tool-row').count() == previous_rows + 1, 'Update the existing tool row instead of adding a second one'
    assert 'running' not in page.locator('.tool-row summary').last.inner_text()
    for width, height in [(680, 720), (520, 540), (320, 420)]:
        page.set_viewport_size({'width': width, 'height': height})
        assert page.locator('#messages').bounding_box()['height'] >= 180
        assert page.locator('.bubble').first.evaluate('e => parseFloat(getComputedStyle(e).fontSize)') >= 15
        page.locator('#prompt').scroll_into_view_if_needed()
        assert page.locator('#prompt').is_visible()
        assert page.evaluate('document.body.scrollWidth <= innerWidth')
    page.set_viewport_size({'width': 680, 'height': 720})
    page.evaluate('document.getElementById("messages").scrollTop = document.getElementById("messages").scrollHeight')
    page.screenshot(path=str(ROOT / 'dist' / 'conversation-preview.png'))
    assert not errors, errors
    browser.close()
    print('Browser UI checks passed: independent connection checks, provider errors, discovery before save, key clearing, device context, responses, plans, and readable layouts at three sizes. Mocked service only.')
