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
