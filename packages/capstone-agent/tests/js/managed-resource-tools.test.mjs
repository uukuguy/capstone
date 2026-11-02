import test from 'node:test';
import assert from 'node:assert/strict';
import {createManagedResourceTools} from '../../src/capstone_agent/resources/managed-resource-tools.mjs';
test('no task resource grant exposes no management tool',()=>assert.deepEqual(createManagedResourceTools({}),[]));
test('uses host selected route/grant and preserves operation receipt',async()=>{
 const tools=createManagedResourceTools({managedResources:{url:'http://localhost/task',grant:'private'},deadlineAt:Date.now()+5000},{fetchImpl:async(url,options)=>{
  assert.equal(url,'http://localhost/task');assert.equal(options.headers.Authorization,'Bearer private');assert.equal(JSON.parse(options.body).operation,'list');
  return {ok:true,json:async()=>({ok:true,result:{allowed_actions:['resources.use'],resources:[]}})};
 }});
 const result=await tools[0].execute('call',{operation:'list',document:{}});
 assert.equal(result.isError,false);assert.equal(JSON.parse(result.content[0].text).allowed_actions[0],'resources.use');assert.ok(!JSON.stringify(result).includes('private'));
});
test('permission denial remains error, not fabricated installation success',async()=>{
 const [tool]=createManagedResourceTools({managedResources:{url:'http://localhost/task',grant:'private'},deadlineAt:Date.now()+5000},{fetchImpl:async()=>({ok:true,json:async()=>({ok:false,kind:'permission',code:'resource_permission_denied'})})});
 assert.equal((await tool.execute('call',{operation:'install',document:{}})).isError,true);
});
test('disconnected mutation reports unknown effects without retry',async()=>{
 let calls=0;
 const [tool]=createManagedResourceTools({managedResources:{url:'http://localhost/task',grant:'private'},deadlineAt:Date.now()+5000},{fetchImpl:async()=>{calls++;throw Error('private transport detail')}});
 const result=await tool.execute('call',{operation:'install',document:{request_id:'one'}});
 const diagnostic=JSON.parse(result.content[0].text);
 assert.equal(calls,1);assert.equal(diagnostic.executed,null);assert.equal(diagnostic.request_id,'one');assert.equal(result.isError,true);assert.ok(!JSON.stringify(result).includes('private transport'));
});
