import test from 'node:test';
import assert from 'node:assert/strict';
import {createPresentationTools} from '../../src/capstone_agent/resources/presentation-templates.mjs';

const config=()=>({taskId:'task',deadlineAt:Date.now()+10000,
  applicationPolicy:{allowed_tools:['agent_presentations']},
  presentationLibrary:{url:'http://private/presentation-template-tasks/task',grant:'test',inputRoot:'/inputs/task'}});

test('presentation tools require an admitted host binding and application tool grant',()=>{
  assert.deepEqual(createPresentationTools({}),[]);
  const c=config();c.applicationPolicy.allowed_tools=[];
  assert.deepEqual(createPresentationTools(c),[]);
});

test('the actual SDK call identity crosses the fixed private adapter without caller scope fields',async()=>{
  const calls=[];
  const [tool]=createPresentationTools(config(),{fetchImpl:async(url,options)=>{
    calls.push({url,body:JSON.parse(options.body)});
    return new Response(JSON.stringify({ok:true,result:{revision:1}}));
  }});
  const result=await tool.execute('native-call',{operation:'select',document:{reference:{template_id:'state-grid',version:'sha256:'+'a'.repeat(64),sha256:'a'.repeat(64)},expected_revision:0}});
  assert.equal(result.isError,false);assert.equal(calls.length,1);
  assert.equal(calls[0].body.call_id,'native-call');
  assert.equal(calls[0].url,config().presentationLibrary.url);
  assert.equal(Object.hasOwn(calls[0].body,'workspace'),false);
});

test('unknown transport outcomes never auto replay a mutation or expose exception text',async()=>{
  let count=0;
  const [tool]=createPresentationTools(config(),{fetchImpl:async()=>{count++;throw Error('PRIVATE_SENSITIVE_MESSAGE');}});
  const result=await tool.execute('native-call',{operation:'publish',document:{reference:{}}});
  assert.equal(count,1);assert.equal(result.isError,true);
  assert.equal(result.details.code,'presentation_operation_outcome_unknown');
  assert.equal(JSON.stringify(result).includes('PRIVATE_SENSITIVE_MESSAGE'),false);
});

test('a template materialization cannot grant an arbitrary returned file path',async()=>{
  const template={template_id:'state-grid',version:'sha256:'+'a'.repeat(64),sha256:'a'.repeat(64)};
  const [tool]=createPresentationTools(config(),{fetchImpl:async()=>new Response(JSON.stringify({ok:true,result:{path:'/host/secret',template}}))});
  await assert.rejects(tool.execute('materialize',{operation:'materialize',document:{}}),/identity/);
});
