import test from 'node:test';
import assert from 'node:assert/strict';
import {createPresentationTools} from '../../src/capstone_agent/resources/presentation-templates.mjs';

const config=()=>({taskId:'task',deadlineAt:Date.now()+10000,
  applicationPolicy:{allowed_tools:['agent_presentations']},
  presentationLibrary:{url:'http://private/presentation-template-tasks/task',grant:'test',inputRoot:'/inputs/task'}});

test('render freezes the selected template and invokes only the fixed renderer with source bundle support',async()=>{
 const sha='a'.repeat(64),reference={template_id:'state-grid',version:'sha256:'+sha,sha256:sha};
 let request,executed;
 const [tool]=createPresentationTools(config(),{
  fetchImpl:async(url,options)=>{request=JSON.parse(options.body);return new Response(JSON.stringify({ok:true,result:{
   path:'/inputs/task/presentation-templates/state-grid/'+sha+'.pptx',template:reference}}));},
  runRenderer:async(command,argv,options)=>{executed={command,argv,options};return {stdout:JSON.stringify({
   schema:'capstone-presentation-library-render/1',output:'new.pptx',template_sha256:sha,pdf:{status:'failed'}})};}});
 const result=await tool.execute('render-one',{operation:'render',document:{bundle:'saved.source.zip',output:'new.pptx'}});
 assert.equal(request.operation,'materialize');assert.deepEqual(request.document,{});
 assert.equal(executed.command,'/usr/local/bin/capstone-presentation');
 assert.deepEqual(executed.argv.slice(0,4),['--bundle','saved.source.zip','--output','new.pptx']);
 assert.equal(executed.argv.at(-1),'--pdf');
 assert.equal(result.details.result.pdf.status,'failed');
 assert.deepEqual(result.details.result.template_reference,reference);
 assert.deepEqual(result.details.evidence_refs,[]);
});

test('render forwards bounded renderer diagnostics while hiding arbitrary process errors',async()=>{
 const sha='b'.repeat(64),template={template_id:'state-grid',version:'sha256:'+sha,sha256:sha};
 const failure={schema:'capstone-presentation-render-error/1',code:'presentation_render_rejected',
  message:'Missing explanation',diagnostic:{location:'slides[0].argument'},delivery_confirmed:false};
 for(const trusted of [true,false]){
  const [tool]=createPresentationTools(config(),{
   fetchImpl:async()=>new Response(JSON.stringify({ok:true,result:{template,
    path:'/inputs/task/presentation-templates/state-grid/'+sha+'.pptx'}})),
   runRenderer:async()=>{throw Object.assign(Error('private transport details'),{
    stderr:trusted?JSON.stringify(failure):'private process environment'});}});
  const result=await tool.execute('render',{operation:'render',document:{spec:'content.json',output:'new.pptx'}});
  assert.equal(result.isError,true);
  assert.equal(JSON.stringify(result).includes('private'),false);
  if(trusted)assert.equal(result.details.diagnostic.diagnostic.location,'slides[0].argument');
  else assert.equal(result.details.code,'presentation_render_failed');
 }
});

test('presentation tools require an admitted host binding and application tool grant',()=>{
  assert.deepEqual(createPresentationTools({}),[]);
  const c=config();c.applicationPolicy.allowed_tools=[];
  assert.deepEqual(createPresentationTools(c),[]);
});

test('upload versions follow the admitted integer resource contract, separate from template versions',()=>{
 const [tool]=createPresentationTools(config());
 const document=tool.parameters.properties.document.properties;
 assert.equal(document.resource.properties.version.type,'integer');
 assert.equal(document.resource.properties.version.minimum,1);
 assert.equal(document.reference.properties.version.type,'string');
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
