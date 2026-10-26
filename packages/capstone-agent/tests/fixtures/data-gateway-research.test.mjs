import test from 'node:test';
import assert from 'node:assert/strict';
import {createDataGatewayTools} from '../../src/capstone_agent/resources/general-data-gateway.mjs';
import {applicationToolOptions} from '../../src/capstone_agent/resources/general-sdk.mjs';

function config(){return {deadlineAt:Date.now()+10000,applicationPolicy:{allowed_tools:['data_gateway_discover_data_capabilities']},
  dataGateway:{url:'http://127.0.0.1:8790/data-gateway/task-1',grant:'task-grant',taskId:'task-1',
    catalog:{revision:'a'.repeat(64),tool_hashes:{data_gateway_discover_data_capabilities:'b'.repeat(64)},
      tools:{data_gateway_discover_data_capabilities:{name:'discover_data_capabilities',description:'Discover data',inputSchema:{type:'object',properties:{}}}}}}};}

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
