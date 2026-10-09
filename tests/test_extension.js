// SPDX-License-Identifier: Apache-2.0
/* Integration tests with an explicit Packet Tracer API double, not a live simulator. */
const fs = require('fs'), vm = require('vm'), assert = require('assert');
let delivered = [], cli = null;
const device = {getName:()=> 'PC0', getModel:()=> 'PC-PT', getType:()=>8, getPower:()=>true,
 getXCoordinate:()=>100, getYCoordinate:()=>200, getPortCount:()=>0, getCommandLine:()=>cli};
const context = {JSON,Number,String,Boolean,Date,Error,setInterval,clearInterval,setTimeout,dprint:()=>{},
 ipc:{network:()=>({getDevice:n=>n==='PC0'?device:null,getDeviceCount:()=>1,getDeviceAt:()=>device,getLinkCount:()=>0}),appWindow:()=>({getVersion:()=> '9.0'})},
 _ScriptModule:{unregisterIpcEventByID:()=>{}}};
vm.createContext(context);
vm.runInContext(fs.readFileSync('extension/main.js','utf8'),context);
context.agentWindow={evaluateJavaScriptAsync:code=>{
 const callback={window:{agentResult:(id,result)=>delivered.push({id,result})}};
 vm.runInNewContext(code,callback);
}};
function dispatch(id,tool,args){context.dispatchAgentJob(JSON.stringify({id,tool,args}));}
async function waitFor(id){for(let i=0;i<50;i++){const r=delivered.find(x=>x.id===id);if(r)return r.result;await new Promise(r=>setTimeout(r,50));}throw Error('No result for '+id);}
(async()=>{
 dispatch('topology','inspect_topology',{});
 assert.equal((await waitFor('topology')).devices[0].name,'PC0');
 dispatch('missing','inspect_device',{device:'Missing'});
 assert.equal((await waitFor('missing')).ok,false);
 dispatch('bad','execute_arbitrary_js',{code:'process.exit()'});
 assert.equal((await waitFor('bad')).ok,false);
 let output='', events={};
 cli={getOutput:()=>output,getPrompt:()=> 'C:\\>',getMode:()=> 'exec',registerEvent:(name,obj,fn)=>events[name]=fn,
 enterCommand:command=>{
  output=command+'\nPackets: Sent = 4, Received = 4, Lost = 0 (0% loss),\nC:\\>';
  events.commandEnded({objectUuid:'terminal-id'},{inputCommand:command,status:0});
 }};
 dispatch('ping','test_ping',{device:'PC0',address:'192.168.1.2'});
 assert.equal((await waitFor('ping')).test.passed,true);
 cli.enterCommand=command=>{
  output=command+'\nPinging 192.168.1.2...';
  events.commandEnded({objectUuid:'terminal-id'},{inputCommand:command,status:0});
  setTimeout(()=>{output+='\nPackets: Sent = 4, Received = 4, Lost = 0 (0% loss),\nC:\\>';},650);
 };
 dispatch('late-ping','test_ping',{device:'PC0',address:'192.168.1.2'});
 await new Promise(r=>setTimeout(r,400));
 assert.equal(delivered.some(x=>x.id==='late-ping'),false,'Do not end ping before its summary arrives');
 assert.equal((await waitFor('late-ping')).test.passed,true);
 assert.equal(context.parsePing('Success rate is 75 percent (3/4)',false).passed,false);
 assert.equal(context.parsePing('Reply from 10.0.0.1',false).passed,null);
 assert.equal(context.parsePing('Success rate is 100 percent (5/5)',true).passed,null);
 assert.equal(context.parsePing('Packets: Sent = 4, Received = 0, Lost = 4',false).passed,false);
 let sent = false;
 cli = {getPrompt:()=> 'Would you like to enter the initial configuration dialog? [yes/no]: ',
  getMode:()=> '', enterCommand:()=>{sent=true;}};
 dispatch('startup-block','run_cli',{device:'PC0',command:'configure terminal'});
 assert.equal((await waitFor('startup-block')).ok,false);
 assert.equal(sent,false,'Never feed configuration commands into the startup wizard');
 cli={getOutput:()=>output,getPrompt:()=> 'Router>',getMode:()=> 'user',registerEvent:(name,obj,fn)=>events[name]=fn,
  enterCommand:command=>{output += '\n% Please answer yes or no.\nRouter>';
   events.commandEnded({objectUuid:'terminal-id'},{inputCommand:command,status:0});}};
 dispatch('wizard-error','run_cli',{device:'PC0',command:'configure terminal'});
 assert.equal((await waitFor('wizard-error')).ok,false,'A native status of zero does not override a CLI error');
 let pageNumber=0, reads=0;output='';events={};
 cli={getOutput:()=>{reads++;return output;},getPrompt:()=> 'Router#',getMode:()=> 'enable',
  registerEvent:(name,obj,fn)=>events[name]=fn,enterCommand:command=>{
   if(command==='show running-config')output='show running-config\nPage one\n --More-- ';
   else if(command===' '){pageNumber++;output+='\nPage '+pageNumber+(pageNumber<2?'\n --More-- ':'\nRouter#');
    if(pageNumber===2)events.commandEnded({objectUuid:'terminal-id'},{inputCommand:'show running-config',status:0});}
   else throw Error('Unexpected pager input');
  }};
 dispatch('pagination','run_cli',{device:'PC0',command:'show running-config'});
 const paged=await waitFor('pagination');assert.equal(paged.ok,true);assert.equal(paged.output_pages_advanced,2);
 assert(paged.output.includes('Page 2'));assert(reads<=8,'Avoid continuously reading full CLI history');
 output='old terminal snapshot';events={};
 cli={getOutput:()=>output,getPrompt:()=> 'Router#',getMode:()=> 'enable',
  registerEvent:(name,obj,fn)=>events[name]=fn,enterCommand:command=>{
   output='Older history: % Invalid input\nPackets: Sent = 4, Received = 4\nRouter#'+command+'\nFresh interface output\nRouter#';
   events.outputWritten({objectUuid:'terminal-id'},{newOutput:command+'\nFresh interface output\nRouter#'});
   events.commandEnded({objectUuid:'terminal-id'},{inputCommand:command,status:0});
  }};
 dispatch('rotated-history','run_cli',{device:'PC0',command:'show ip interface brief'});
 const rotated=await waitFor('rotated-history');assert.equal(rotated.ok,true);
 assert(!rotated.output.includes('Older history'),'Only fresh output is command evidence');
 assert(rotated.output.includes('Fresh interface output'));
 const windowBefore=context.agentWindow,windowCalls=[];context.agentWindow={
  undockFromMainViewArea:()=>windowCalls.push('undock'),showMaximized:()=>windowCalls.push('maximize'),
  showNormal:()=>windowCalls.push('normal'),setPreferredSize:(w,h)=>windowCalls.push([w,h]),
  dockToMainViewArea:()=>windowCalls.push('dock'),show:()=>{},evaluateJavaScriptAsync:code=>windowCalls.push(code)};
 context.expandAgent();assert.equal(context.agentExpanded,true);context.expandAgent();assert.equal(context.agentExpanded,false);
 assert(windowCalls.includes('dock'));assert(windowCalls.includes('normal'));
 assert(windowCalls.includes('window.agentWindowState(true)'));assert(windowCalls.includes('window.agentWindowState(false)'));
 context.agentWindow=windowBefore;
 console.log('Extension API-double tests passed: topology, missing devices, tool allowlist, CLI output, ping success/failure/unknown.');
})().catch(e=>{console.error(e);process.exitCode=1;});
