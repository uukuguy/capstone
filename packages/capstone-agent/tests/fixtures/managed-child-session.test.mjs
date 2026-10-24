import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createManagedChildSession,runSettledPrompt} from '../../src/capstone_agent/resources/general-sdk.mjs';

test('host continuation keeps one session and all model usage, but only final answer',async()=>{
  let listener,round=0;
  const events=[];
  const session={subscribe:fn=>{listener=fn;return ()=>{};},async prompt(){
    round++;
    listener({type:'agent_end',messages:[{role:'assistant',stopReason:'stop',usage:{input:10,output:2},
      content:[{type:'text',text:round===1?'Draft':'Checked result'}]}]});
  }};
  await runSettledPrompt(session,{kind:'text',text:'Research'},null,event=>events.push(event),
    async()=>round===1?'Repair the observed discrepancy':null);
  assert.equal(round,2);
  assert.equal(events.length,1);
  assert.equal(events[0].messages.reduce((sum,item)=>sum+item.usage.input,0),20);
  assert.deepEqual(events[0].messages[0].content,[]);
  assert.equal(events[0].messages[1].content[0].text,'Checked result');
});

test('unchanged pending action without tools or checkpoint progress stops instead of issuing another prompt',async()=>{
  let listener,round=0;const events=[];
  const session={subscribe:fn=>{listener=fn;return()=>{};},async prompt(){round++;
    if(round>3)throw new Error('Fixture detected an unbounded continuation loop');
    listener({type:'agent_end',messages:[{role:'assistant',stopReason:'stop',usage:{input:10,output:2},content:[{type:'text',text:'Still thinking'}]}]});}};
  await assert.rejects(runSettledPrompt(session,{kind:'text',text:'private input'},null,event=>events.push(event),
    async()=>({prompt:round===1?'Please execute the pending action':'Same request, different wording',actionId:'action-1',checkpoint:'committed-4'})),
    error=>error.code==='continuation_no_progress'&&/saved outputs were retained/.test(error.message));
  assert.equal(round,2,'Only the initial response and its pending-action opportunity are executed');
  const failed=events.filter(event=>event.type==='agent_end');
  assert.equal(failed.length,1);assert.equal(failed[0].success,false);
  assert.equal(failed[0].code,'continuation_no_progress');
  assert.equal(failed[0].messages.length,2,'Only actual model responses are counted');
  assert.equal(failed[0].messages.reduce((sum,message)=>sum+message.usage.input,0),20);
  assert.ok(failed[0].messages.every(message=>message.stopReason==='stop'&&message.content.length===0),
    'Host failure preserves actual model stop status and tokens without presenting prose as a delivered answer');
  assert.ok(!JSON.stringify(events).includes('private input'));
});

test('actual tools including failed repair and unknown receipt recovery prevent a false stall',async()=>{
  let listener,round=0;
  const names=['read','write','agent_research_cycle'];
  const session={subscribe:fn=>{listener=fn;return()=>{};},async prompt(){round++;
    listener({type:'tool_execution_end',toolName:names[(round-1)%names.length],toolCallId:'call-'+round,isError:round===2});
    listener({type:'agent_end',messages:[{role:'assistant',stopReason:'stop',content:[{type:'text',text:'Observed actual work'}]}]});}};
  await runSettledPrompt(session,{kind:'text',text:'Work'},null,()=>{},
    async()=>round<4?{prompt:'Continue actual repair',actionId:'same-action',checkpoint:'same-committed-state'}:null);
  assert.equal(round,4);
});

test('a committed checkpoint or changed pending action is host progress without another tool',async()=>{
  let listener,round=0;
  const session={subscribe:fn=>{listener=fn;return()=>{};},async prompt(){round++;
    listener({type:'agent_end',messages:[{role:'assistant',stopReason:'stop',content:[{type:'text',text:'Waiting on host'}]}]});}};
  await runSettledPrompt(session,{kind:'text',text:'Work'},null,()=>{},
    async()=>round<4?{prompt:'Continue',actionId:round===3?'new-action':'same-action',checkpoint:round===1?'rev1':'rev2'}:null);
  assert.equal(round,4);
});

test('children use only admitted resources and preserve execution guards',async()=>{
  let loaderOptions,sessionOptions,active,disposed=false;
  const sdk={SettingsManager:{inMemory:settings=>({settings})},
    DefaultResourceLoader:class {constructor(options){loaderOptions=options;}
      async reload(){} getExtensions(){return {errors:[]};} getSkills(){return {diagnostics:[]};}},
    createCodingTools:()=>['read','bash'].map(name=>({name,execute:async()=>({content:[]})})),
    SessionManager:{inMemory:()=>({})},
    createAgentSession:async options=>{sessionOptions=options;return {session:{
      bindExtensions:async()=>{},setActiveToolsByName:names=>{active=names;},dispose:()=>{disposed=true;}}};}};
  const runtime={getModel:()=>({id:'fixed'})};
  const config={model:'fixed',settings:{},extensions:[],allowedSkills:['selected'],
    contextFiles:[],applicationPolicy:{allowed_tools:['read','bash']},appendSystemPrompt:['ORDINARY_CHILD_POLICY_SENTINEL']};
  const child=await createManagedChildSession(config,sdk,runtime,{toolNames:['read'],skills:[]});
  assert.equal(sessionOptions.modelRuntime,runtime);
  assert.deepEqual(active,['read']);
  assert.equal(loaderOptions.noExtensions,true);
  assert.equal(loaderOptions.noSkills,true);
  assert.equal(loaderOptions.noPromptTemplates,true);
  assert.deepEqual(loaderOptions.additionalSkillPaths,[]);
  assert.match(loaderOptions.appendSystemPromptOverride().join('\n'),/ORDINARY_CHILD_POLICY_SENTINEL/);
  assert.match(loaderOptions.appendSystemPromptOverride().join('\n'),/pipefail/);
  await assert.rejects(sessionOptions.customTools.find(tool=>tool.name==='bash').execute('denied',{},new AbortController().signal),/did not authorize/);
  await child.close();assert.equal(disposed,true);
  await assert.rejects(createManagedChildSession(config,sdk,runtime,{toolNames:['web_search'],skills:[]}),/not authorized/);
});
