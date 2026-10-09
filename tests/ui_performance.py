# SPDX-License-Identifier: Apache-2.0
"""UI workload regression check in Chrome; optional comparison with an older UI script."""
import argparse
import json
import os
import tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--baseline', type=Path)
args = parser.parse_args()
status = {'connected': True, 'key_configured': True, 'provider': 'gemini', 'model': 'test', 'active_run': None, 'service_version': '0.2.2'}
config = {'provider': 'gemini', 'models': {'gemini': 'test'}, 'max_steps': 40,
          'providers': {'gemini': {'key_configured': True, 'environment_key': False}}}


def run(browser, script, verify=False):
    with tempfile.TemporaryDirectory() as folder:
        folder = Path(folder)
        for name in ['index.html', 'styles.css']:
            (folder / name).write_text((ROOT / 'extension' / name).read_text())
        (folder / 'ui.js').write_text(script.replace('__BRIDGE_TOKEN__', '"performance-test-token"'))
        page = browser.new_page(viewport={'width': 680, 'height': 720})
        page.add_init_script('window.$se = function() {};')
        calls = []

        def service(route):
            path = route.request.url.split('54123', 1)[1]
            calls.append(path)
            result = {'job': None, 'status': status} if path == '/bridge/poll' else config if path == '/config' else status
            route.fulfill(status=200, content_type='application/json', body=json.dumps(result))

        page.route('http://127.0.0.1:54123/**', service)
        page.goto((folder / 'index.html').as_uri())
        page.wait_for_function('document.getElementById("model-chip").textContent.includes("test")')
        page.wait_for_function('configuration !== null')
        page.context.new_cdp_session(page).send('Emulation.setCPUThrottlingRate', {'rate': 4})
        result = page.evaluate('''() => {
            const snapshot = {ok:true, device_count:200, link_count:0, devices:Array.from({length:200}, (_,i) => ({
                name:'PC'+i, model:'PC-PT', ports:Array.from({length:16}, (_,j) => ({name:'Port'+j, up:true, address:'192.168.1.2'}))
            }))};
            const plan = [{title:'Inspect the lab',status:'in_progress'}];
            const start = performance.now();
            for(let i=0;i<30;i++)toolEvent({kind:'tool_result',name:'inspect_topology',result:snapshot});
            for(let i=0;i<5;i++)renderNetwork(snapshot);
            for(let i=0;i<80;i++)renderPlan(plan);
            return {work_ms:performance.now()-start, closed_details:document.querySelectorAll('details').length,
                    formatted_logs:document.querySelectorAll('details pre').length, hidden_cards:document.querySelectorAll('.device-card').length};
        }''')
        if verify:
            assert result['formatted_logs'] == 0, result
            assert result['hidden_cards'] == 0, result
            assert result['work_ms'] < 200, result
            assert '/status' not in calls, 'Native bridge responses already contain status'
            page.locator('details').first.locator('summary').click()
            page.wait_for_selector('details pre')
            assert 'preview truncated' in page.locator('details pre').inner_text()
            scroll_top = page.evaluate('''async () => {
                document.getElementById('messages').scrollTop=0;followMessages=false;
                bubble('Assistant','A background update while reading older messages');
                await new Promise(requestAnimationFrame);return document.getElementById('messages').scrollTop;
            }''')
            assert scroll_top == 0, scroll_top
            mutations = page.evaluate('''async () => {
                let count=0;const observer=new MutationObserver(records=>count+=records.length);
                observer.observe(document.getElementById('plan'),{subtree:true,childList:true,attributes:true});
                for(let i=0;i<20;i++)renderPlan([{title:'Inspect the lab',status:'in_progress'}]);
                await Promise.resolve();observer.disconnect();return count;
            }''')
            assert mutations == 0, mutations
            bounded = page.evaluate('''() => {
                for(let i=0;i<500;i++){
                    toolEvent({kind:'tool_start',name:'run_cli',args:{command:'show ip route'}});
                    toolEvent({kind:'tool_result',name:'run_cli',result:{ok:true,output:'Route '+i}});
                }
                return {rows:document.querySelectorAll('.tool-row').length,
                    note:!!document.getElementById('tool-log-note')};
            }''')
            assert bounded['rows'] <= 121, bounded  # One intentionally opened row stays visible.
            assert bounded['note'], bounded
            page.set_viewport_size({'width': 1600, 'height': 1000})
            page.locator('#prompt').fill('Typing still works with a large tool log')
            page.locator('[data-tab=settings]').click()
            assert page.locator('#settings-tab').is_visible()
            page.locator('[data-tab=network]').click()
            page.wait_for_function('document.querySelectorAll(".device-card").length === 200')
            page.locator('[data-tab=chat]').click()
            assert page.locator('#prompt').input_value() == 'Typing still works with a large tool log'
        page.close()
        return result


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=os.environ.get('CHROME_EXECUTABLE') or None, headless=True)
    if args.baseline:
        print('Before:', json.dumps(run(browser, args.baseline.read_text())))
    print('After:', json.dumps(run(browser, (ROOT / 'extension' / 'ui.js').read_text(), verify=True)))
    browser.close()
