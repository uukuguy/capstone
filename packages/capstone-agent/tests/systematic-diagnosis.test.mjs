import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,mkdir,rm,writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import * as adapter from '../src/capstone_agent/resources/general-sdk.mjs';
import {createDiagnosisTools,diagnosisDigest} from '../src/capstone_agent/resources/systematic-diagnosis.mjs';

test('diagnostic host port recovers exact calls without probe execution or model state',async()=>{
  const root=await mkdtemp(resolve(tmpdir(),'diagnosis-port-'));
  const emitted=[];
  try{
    await mkdir(resolve(root,'responses'));
    const config={diagnosisContextPath:root,deadlineAt:Date.now()+1000,
      applicationPolicy:{allowed_tools:['agent_diagnosis_record','agent_diagnosis_guide']}};
    const tools=createDiagnosisTools(config,{emit:async frame=>{
      emitted.push(frame);
      await writeFile(resolve(root,'responses',frame.request_id+'.json'),JSON.stringify({
        schema:frame.schema,request_id:frame.request_id,
        request_sha256:diagnosisDigest(frame),
        ok:true,result:{status:'probe_reserved',reported_only:true}}));
    }});
    const tool=tools.find(item=>item.name==='agent_diagnosis_record');
    const record={operation:'read'};
    assert.equal((await tool.execute('same-call',record)).details.diagnosis.status,'probe_reserved');
    await tool.execute('same-call',record);
    assert.equal(emitted.length,1);
    await assert.rejects(tool.execute('same-call',{operation:'begin',record:{issue:'changed'}}),/identity/);
    assert.match((await tools.find(item=>item.name==='agent_diagnosis_guide').execute('guide',{})).content[0].text,/advisory/i);
    assert.deepEqual(createDiagnosisTools({...config,applicationPolicy:{allowed_tools:[]}}),[]);
  }finally{await rm(root,{recursive:true,force:true});}
});

test('pinned SDK publishes diagnostic tools to parent and explicitly authorized child',async()=>{
  const sdk=await import(pathToFileURL(resolve(import.meta.dirname,'../../../.grid-agent/runtime/pi/source/packages/coding-agent/dist/index.js')).href);
  const root=await mkdtemp(resolve(tmpdir(),'diagnosis-sdk-'));
  const cwd=process.cwd(),agent=process.env.PI_CODING_AGENT_DIR;
  const model={id:'fixed',name:'Offline',provider:'capstone-general',api:'openai-completions',baseUrl:'http://127.0.0.1:1',
    reasoning:false,input:['text'],contextWindow:32000,maxTokens:1024,cost:{input:0,output:0,cacheRead:0,cacheWrite:0}};
  const runtime={getModel:()=>model,hasConfiguredAuth:()=>true};
  const names=['agent_diagnosis_record','agent_diagnosis_guide'];
  let child;
  const output=[],write=process.stdout.write;
  try{
    process.chdir(root);process.env.PI_CODING_AGENT_DIR=resolve(root,'agent');await mkdir(process.env.PI_CODING_AGENT_DIR);
    const config={model:'fixed',settings:{},extensions:[],allowedSkills:[],contextFiles:[],inventoryOnly:true,
      diagnosisContextPath:root,applicationPolicy:{allowed_tools:names}};
    process.stdout.write=function(chunk,...args){output.push(String(chunk));return true;};
    await adapter.runManagedSession(config,sdk,runtime);
    process.stdout.write=write;
    assert.deepEqual(JSON.parse(output.find(line=>line.includes('general_pi_inventory'))).tools.sort(),names.sort());
    child=await adapter.createManagedChildSession(config,sdk,runtime,{cwd:root,toolNames:names});
    assert.deepEqual(child.session.getActiveToolNames().sort(),names.sort());
    await child.close();child=undefined;
    await assert.rejects(adapter.createManagedChildSession({...config,applicationPolicy:{allowed_tools:[]}},sdk,runtime,
      {cwd:root,toolNames:names}),/not authorized/);
  }finally{process.stdout.write=write;await child?.close();process.chdir(cwd);
    if(agent===undefined)delete process.env.PI_CODING_AGENT_DIR;else process.env.PI_CODING_AGENT_DIR=agent;
    await rm(root,{recursive:true,force:true});}
});

test('exhausted selection allows a limited answer and independent work, but bounds ignored rejections',async()=>{
  const root=await mkdtemp(resolve(tmpdir(),'diagnosis-guard-'));
  const write=process.stdout.write;
  try{
    await mkdir(resolve(root,'responses'));
    let observed=0;
    const pending=[];
    process.stdout.write=function(chunk){
      const frame=JSON.parse(chunk);if(frame.operation==='observe_rejection')observed++;
      pending.push(writeFile(resolve(root,'responses',frame.request_id+'.json'),JSON.stringify({
        schema:frame.schema,request_id:frame.request_id,
        request_sha256:diagnosisDigest(frame),ok:true,
        result:{scope_ref:'scope-observed',scopes:[],status:observed<6?'investigating':'exhausted',reason:'Use diagnosis and retain the gap.'}})));
      return true;
    };
    const handlers=new Map(),controller={readParentInputs:async()=>null,progressKey:async()=> 'same'};
    const config={researchRuntime:{graphSchema:'capstone-enterprise-graph/2'},diagnosisContextPath:root,
      applicationPolicy:{allowed_tools:['agent_diagnosis_record']}};
    const guard=adapter.configureGraphParentContext({on:(name,fn)=>handlers.set(name,fn)},config,controller);
    assert.ok(guard);
    for(let index=0;index<6;index++){
      await handlers.get('tool_result')({toolCallId:'call-'+index,toolName:'agent_research_record',input:{same:true},isError:true,
        content:[],details:{ok:false,error:{category:'rejected',code:'graph_context_rejected'}}},{});
      await handlers.get('context')({messages:[]},{});
      const next=()=>handlers.get('before_model_request')({context:{messages:[]}},{});
      await next(); // A final answer remains permitted after the failed action is exhausted.
    }
    assert.equal(observed,6);
    const blocked=await handlers.get('tool_call')({toolCallId:'ignored',toolName:'agent_research_record',input:{same:true}},{});
    assert.equal(blocked.block,true);
    assert.equal(await handlers.get('tool_call')({toolCallId:'independent',toolName:'agent_research_record',input:{other:true}},{}),undefined);
    await handlers.get('tool_result')({toolCallId:'independent',toolName:'agent_research_record',input:{other:true},details:{ok:true}},{});
    await handlers.get('context')({messages:[]},{});
    await handlers.get('before_model_request')({context:{messages:[]}},{});
    await handlers.get('tool_call')({toolCallId:'ignored-again',toolName:'agent_research_record',input:{same:true}},{});
    await handlers.get('tool_call')({toolCallId:'ignored-third',toolName:'agent_research_record',input:{same:true}},{});
    await handlers.get('context')({messages:[]},{});
    await assert.rejects(handlers.get('before_model_request')({context:{messages:[]}},{}),/settle/);
    await Promise.all(pending);
  }finally{process.stdout.write=write;await rm(root,{recursive:true,force:true});}
});

test('foundation diagnosis works for organizer without opening native business execution',async()=>{
  const config={diagnosisContextPath:'/host-owned/diagnosis',researchChannelPath:'/host-owned/research',
    applicationPolicy:{allowed_tools:['agent_diagnosis_guide']},researchRuntime:{isolatedTaskExecution:true}};
  const tools=adapter.applicationToolOptions(config,[],()=>({beginTool:()=>{throw new Error('Native business execution is forbidden');}}));
  const guide=tools.customTools.find(item=>item.name==='agent_diagnosis_guide');
  assert.match((await guide.execute('guide',{})).content[0].text,/Research checks are advisory/);
});
