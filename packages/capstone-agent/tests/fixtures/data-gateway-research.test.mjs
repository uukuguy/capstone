import test,{after} from 'node:test';
import assert from 'node:assert/strict';
import {createDataGatewayTools,validateGatewayBatch} from '../../src/capstone_agent/resources/general-data-gateway.mjs';
import {applicationToolOptions} from '../../src/capstone_agent/resources/general-sdk.mjs';
import {compositionPolicy} from '../../src/capstone_agent/resources/tool-composition.mjs';
import {savedToolObservation} from '../../src/capstone_agent/resources/tool-result-context.mjs';
import {mkdtemp,rm,writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {createHash} from 'node:crypto';
const suiteCwd=await mkdtemp(join(tmpdir(),'gateway-research-'));
after(()=>rm(suiteCwd,{recursive:true,force:true}));

test('batch capacity preflight exposes exact bounds and permits correction',async()=>{
 const c=config();let attempts=0;
 c.deadlineAt=Date.now()+10000;
 const fetchImpl=async()=>({ok:++attempts>1,json:async()=>attempts===1?
  {error:'capacity_exceeded',executed:false,capacity:{dimension:'rpc_batch_requests',actual:129,limit:128}}:
  {schema:'capstone-gateway-preflight/1',catalog_revision:c.dataGateway.catalog.revision,executed:false,valid:true,errors:[]}});
 await assert.rejects(validateGatewayBatch(c,Array(129).fill({}),{fetchImpl}),/actual=129, limit=128; split/);
 await validateGatewayBatch(c,[{}],{fetchImpl});
 assert.equal(attempts,2);
});

for(const padding of [0,10000])test(`direct task observation references support read inspect save without another call (padding=${padding})`,async()=>{
 const cwd=await mkdtemp(join(tmpdir(),'direct-observation-')),previous=globalThis.fetch;let calls=0;
 try{
  const c=config();c.toolResultCwd=cwd;c.toolComposition=compositionPolicy;c.researchTaskId='task-1';
  c.applicationPolicy.allowed_tools.push('bash','write','agent_tools_execute');
  globalThis.fetch=async(_url,options)=>{
   calls++;const body=JSON.parse(options.body);
   return {ok:true,json:async()=>({result_json:JSON.stringify({structuredContent:{status:body.call_id==='direct-error'?'error':'ok',data:{n:4,rows:[{n:4}],padding:'x'.repeat(padding),
    next_action:{tool:'discover_data_capabilities',arguments:{}}}}}),observation:{
    kind:'external_gateway_observation',tool_call_id:body.call_id,task_id:'task-1',tool:body.name,
    catalog_revision:c.dataGateway.catalog.revision,tool_schema_sha256:'b'.repeat(64)}})};
  };
  const options=applicationToolOptions(c,[]),source=options.customTools.find(t=>t.name==='data_gateway_discover_data_capabilities');
  const direct=await source.execute('direct-1',{});
  const ref='native-observation:task-1:'+createHash('sha256').update('direct-1').digest('hex');
  const composed=options.customTools.find(t=>t.name==='agent_tools_execute');
  const program=`const ref=${JSON.stringify(ref)};const n=await tools.read(ref,'/data/n');const legacy=await tools.read(ref,'/structuredContent/data/n');const root=await tools.read(ref,'');const index=await tools.inspect(ref,'/data');const saved=await saveContext('direct',{bindings:{n:{call:ref,pointer:'/data/n'}},datasets:[{name:'rows',call:ref,pointer:'/structuredContent/data/rows'}]});return {n,legacy,status:root.status,index,loaded:await loadContext(saved.path)};`;
  const result=await composed.execute('reuse',{tools:[],program},new AbortController().signal);
  assert.equal(result.isError,false,JSON.stringify(result));
  const output=JSON.parse(result.content[0].text);assert.equal(output.calls,0);assert.equal(output.result.n,4);
  assert.equal(output.result.legacy,4);assert.equal(output.result.status,'ok');
  assert.deepEqual(output.result.loaded.datasets.rows.data,[{n:4}]);assert.equal(calls,1);
  const followed=await composed.execute('follow',{tools:['discover_data_capabilities'],program:`return tools.follow('direct-1','/structuredContent/data/next_action');`},new AbortController().signal);
  assert.equal(followed.isError,false,JSON.stringify(followed));assert.equal(calls,2);
  const foreign={...c};
  const denied=await applicationToolOptions(foreign,[]).customTools.find(t=>t.name==='agent_tools_execute').execute('foreign',{tools:[],program:`return tools.read(${JSON.stringify(ref)},'');`},new AbortController().signal);
  assert.equal(denied.isError,true);assert.equal(calls,2);
  await writeFile(savedToolObservation(direct).reference.path,'tampered');
  const changed=await composed.execute('changed',{tools:[],program:`return tools.read(${JSON.stringify(ref)},'');`},new AbortController().signal);
  assert.equal(changed.isError,true);assert.match(changed.content[0].text,/Saved observation identity changed/);
  assert.equal(calls,2);
  await source.execute('direct-error',{});
  const failedSource=await composed.execute('failed-source',{tools:['discover_data_capabilities'],program:`return tools.follow('direct-error','/structuredContent/data/next_action');`},new AbortController().signal);
  assert.equal(failedSource.isError,true);assert.match(failedSource.content[0].text,/not a successful observation/);assert.equal(calls,3);
 }finally{globalThis.fetch=previous;await rm(cwd,{recursive:true,force:true});}
});

test('registered composition reaches actual application wrapper and calls admitted gateway without active menu load',async()=>{
 const cwd=await mkdtemp(join(tmpdir(),'composition-sdk-')),previous=globalThis.fetch,requests=[];
 try{
  const c=config();c.toolResultCwd=cwd;c.toolComposition=compositionPolicy;
  c.applicationPolicy.allowed_tools.push('bash','write','agent_tools_execute','agent_tool_search','agent_tool_load');c.dataGateway.onDemandTools=true;
  globalThis.fetch=async(url,options)=>{
   const body=JSON.parse(options.body);requests.push(body);
   if(body.operation==='validate_batch')return {ok:true,json:async()=>({schema:'capstone-gateway-preflight/1',catalog_revision:c.dataGateway.catalog.revision,valid:true,errors:[],executed:false})};
   return {ok:true,json:async()=>({result_json:JSON.stringify({structuredContent:{status:'ok',data:{n:4}}}),observation:{
    kind:'external_gateway_observation',tool_call_id:body.call_id,task_id:'task-1',tool:body.name,
    catalog_revision:c.dataGateway.catalog.revision,tool_schema_sha256:'b'.repeat(64)}})};
  };
  const composed=applicationToolOptions(c,[]).customTools.find(t=>t.name==='agent_tools_execute');
  assert.ok(composed);
  const result=await composed.execute('program',{tools:['data_gateway_discover_data_capabilities'],program:`const [a]=await tools.batch([{tool:'data_gateway_discover_data_capabilities',arguments:{}}]);return a.data.n;`},new AbortController().signal);
  assert.equal(result.isError,false,JSON.stringify(result));assert.match(result.content[0].text,/"result":4/);assert.equal(requests.length,2);
  assert.equal(requests[0].operation,'validate_batch');assert.equal(requests[1].name,'data_gateway_discover_data_capabilities');
  delete c.toolComposition;assert.equal(applicationToolOptions(c,[]).customTools.some(t=>t.name==='agent_tools_execute'),false);
  c.toolComposition=compositionPolicy;c.applicationPolicy.allowed_tools=c.applicationPolicy.allowed_tools.filter(n=>n!=='bash');
  assert.equal(applicationToolOptions(c,[]).customTools.some(t=>t.name==='agent_tools_execute'),false);
 }finally{globalThis.fetch=previous;await rm(cwd,{recursive:true,force:true});}
});

function config(){return {toolResultCwd:suiteCwd,deadlineAt:Date.now()+10000,applicationPolicy:{allowed_tools:['data_gateway_discover_data_capabilities']},
  dataGateway:{url:'http://127.0.0.1:8790/data-gateway/task-1',grant:'task-grant',taskId:'task-1',
    catalog:{revision:'a'.repeat(64),tool_hashes:{data_gateway_discover_data_capabilities:'b'.repeat(64)},
      tools:{data_gateway_discover_data_capabilities:{name:'discover_data_capabilities',description:'Discover data',inputSchema:{type:'object',properties:{}}}}}}};}

test('local validation failures identify schema paths without exposing other response fields',async()=>{
 const tool=createDataGatewayTools(config(),{fetchImpl:async()=>({ok:false,status:400,json:async()=>({
  error:'gateway_arguments_invalid',executed:false,private:'secret-canary',validation_errors:[
   {path:'/selection/nested',rule:'type',expected:'string',actual_type:'object',private:'secret-canary'}]})})})[0];
 await assert.rejects(tool.execute('bad',{}),error=>{
  assert.match(error.message,/\/selection\/nested/);assert.match(error.message,/expected.*string/);
  assert.match(error.message,/not executed/);assert.doesNotMatch(error.message,/secret-canary/);return true;
 });
});

test('gateway tools transmit fixed task grants and preserve the full partial result',async()=>{
 const c=config(),requests=[];
 const tools=createDataGatewayTools(c,{fetchImpl:async(url,options)=>{
   requests.push({url,options});return {ok:true,json:async()=>({result_json:'{"structuredContent":{"status":"partial","gaps":["missing"]}}',
    observation:{kind:'external_gateway_observation',tool_call_id:'call-1',task_id:'task-1',tool:'data_gateway_discover_data_capabilities',
      catalog_revision:c.dataGateway.catalog.revision,tool_schema_sha256:'b'.repeat(64)}})};
 }});
 assert.equal(tools.length,1);
 const result=await tools[0].execute('call-1',{});
 assert.equal(JSON.parse(result.content[0].text).structuredContent.status,'partial');
 assert.equal(requests[0].options.headers.Authorization,'Bearer task-grant');
 assert.deepEqual(JSON.parse(requests[0].options.body),{call_id:'call-1',name:tools[0].name,arguments:{}});
 assert.equal(result.details.tool_call_id,'call-1');
 assert.equal(requests.length,1);
});

test('gateway tools reject another task receipt and do not retry failed requests',async()=>{
 let calls=0;
 const [tool]=createDataGatewayTools(config(),{fetchImpl:async()=>{calls++;return {ok:false};}});
 await assert.rejects(tool.execute('call',{}),/gateway/);
 assert.equal(calls,1);
 const [forged]=createDataGatewayTools(config(),{fetchImpl:async()=>({ok:true,json:async()=>({result_json:'{}',
   observation:{task_id:'other-task'}})})});
 await assert.rejects(forged.execute('call',{}),/receipt/);
 const abort=new AbortController();abort.abort();
 await assert.rejects(tool.execute('cancelled',{},abort.signal));
 assert.equal(calls,1);
});

test('application and child tool options include the admitted gateway tools',()=>{
 const c=config();
 assert.equal(applicationToolOptions(c,[]).customTools[0].name,'data_gateway_discover_data_capabilities');
 assert.deepEqual(createDataGatewayTools({}),[]);
});

test('connection failure retains a safe code and stops other probes in this task',async()=>{
 let calls=0;
 const c=config();
 c.dataGateway.catalog.tools.data_gateway_other=c.dataGateway.catalog.tools.data_gateway_discover_data_capabilities;
 const tools=createDataGatewayTools(c,{fetchImpl:async()=>{
  calls++;return {ok:false,status:400,json:async()=>({error:'gateway_call_failed_no_retry'})};
 }});
 await assert.rejects(tools[0].execute('first',{}),/gateway_call_failed_no_retry/);
 await assert.rejects(tools[1].execute('second',{}),/gateway_call_failed_no_retry/);
 assert.equal(calls,1);
});

test('argument errors do not block other calls and untrusted error text is omitted',async()=>{
 let calls=0;
 const [tool]=createDataGatewayTools(config(),{fetchImpl:async()=>{
  calls++;return {ok:false,status:400,json:async()=>({error:calls===1?'gateway_arguments_invalid':'secret-canary upstream text'})};
 }});
 await assert.rejects(tool.execute('first',{}),/gateway_arguments_invalid/);
 await assert.rejects(tool.execute('second',{}),error=>!error.message.includes('secret-canary'));
 assert.equal(calls,2);
});

test('one tool publication change leaves another admitted tool callable without replay',async()=>{
 const c=config(),first='data_gateway_discover_data_capabilities',other='data_gateway_other',calls=[];
 c.dataGateway.catalog.tools[other]={...c.dataGateway.catalog.tools[first],name:'other'};
 c.dataGateway.catalog.tool_hashes[other]='c'.repeat(64);
 const tools=createDataGatewayTools(c,{fetchImpl:async(_url,options)=>{
  const request=JSON.parse(options.body);calls.push(request);
  if(request.name===first)return {ok:false,status:400,json:async()=>({error:'gateway_publication_changed'})};
  return {ok:true,json:async()=>({result_json:'{"status":"ok"}',observation:{
   kind:'external_gateway_observation',task_id:'task-1',tool_call_id:request.call_id,tool:other,
   catalog_revision:c.dataGateway.catalog.revision,tool_schema_sha256:c.dataGateway.catalog.tool_hashes[other]}})};
 }});
 await assert.rejects(tools[0].execute('first',{}),error=>
  error.message.includes('gateway_publication_changed')&&!error.message.includes('probe other gateway tools'));
 assert.equal(calls.length,1);
 const result=await tools[1].execute('second',{});
 assert.equal(JSON.parse(result.content[0].text).status,'ok');
 assert.deepEqual(calls.map(call=>call.name),[first,other]);
});

test('transport stop state cannot leak into a new task',async()=>{
 let calls=0;
 const fetchImpl=async()=>{calls++;return {ok:false,status:400,json:async()=>({error:'gateway_timeout'})};};
 const [first]=createDataGatewayTools(config(),{fetchImpl});
 await assert.rejects(first.execute('call-1',{}),/gateway_timeout/);
 await assert.rejects(first.execute('call-2',{}),/gateway-wide availability is unverified/);
 assert.equal(calls,1);
 const next=config();next.dataGateway.taskId='task-2';
 const [second]=createDataGatewayTools(next,{fetchImpl});
 await assert.rejects(second.execute('call-1',{}),/gateway_timeout/);
 assert.equal(calls,2);
});

test('abort while reading an error response remains cancellation',async()=>{
 const controller=new AbortController();
 const reason=new Error('task cancelled');
 const [tool]=createDataGatewayTools(config(),{fetchImpl:async()=>({ok:false,status:400,
  json:async()=>{controller.abort(reason);throw reason;}})});
 await assert.rejects(tool.execute('call',{},controller.signal),error=>error===reason);
});
