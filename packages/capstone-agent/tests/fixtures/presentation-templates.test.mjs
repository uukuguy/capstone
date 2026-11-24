import test from 'node:test';
import assert from 'node:assert/strict';
import {createPresentationTools} from '../../src/capstone_agent/resources/presentation-templates.mjs';

const config=()=>({taskId:'task',deadlineAt:Date.now()+10000,
  applicationPolicy:{allowed_tools:['agent_presentations']},
  presentationLibrary:{url:'http://private/presentation-template-tasks/task',grant:'test',inputRoot:'/inputs/task'}});

test('content contract is returned by the fixed renderer without template mutation or source access',async()=>{
 const [tool]=createPresentationTools(config(),{fetchImpl:async()=>{throw Error('Unexpected host mutation');},
  runRenderer:async(command,args)=>{
   assert.equal(command,'/usr/local/bin/capstone-presentation');assert.deepEqual(args,['--contract']);
   return {stdout:JSON.stringify({schema:'capstone-presentation-content-contract/1',slide_defaults:{role:'content'}})};
  }});
 const result=await tool.execute('contract',{operation:'contract',document:{}});
 assert.equal(result.isError,false);assert.equal(result.details.result.slide_defaults.role,'content');
});

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

test('successful contract loads the approved guide for subsequent requests without changing the receipt',async()=>{
 const {createGuideProjection}=await import('../../src/capstone_agent/resources/model-context-input.mjs');
 const guide='Verified rendering and review guidelines.';
 const projection=createGuideProjection({presentation:guide});
 const state={systemPrompt:'Stable base',messages:[{role:'user',content:'Make a deck'}]};
 const renderer=async()=>({stdout:JSON.stringify({schema:'capstone-presentation-content-contract/1'})});
 const [tool]=createPresentationTools({...config(),loadPresentationGuide:()=>projection.load('presentation')},{runRenderer:renderer});
 assert.deepEqual(tool.parameters.required,['operation']);
 assert.equal(tool.parameters.oneOf,undefined);
 assert.deepEqual(createPresentationTools(config())[0].parameters.required,['operation','document']);
 assert.equal(projection.project(state),state);
 const receipt=await tool.execute('guide',{operation:'contract'});
 const legacyReceipt=await tool.execute('guide-old',{operation:'contract',document:{spec:'unused.json'}});
 assert.deepEqual(legacyReceipt,receipt);
 assert.equal(receipt.isError,false);
 assert.equal(JSON.stringify(receipt).includes(guide),false);
 const projected=projection.project(state);
 assert.ok(projected.systemPrompt.startsWith(state.systemPrompt));
 assert.ok(projected.systemPrompt.endsWith(guide));
 assert.equal(projected.messages,state.messages);
 assert.equal(state.systemPrompt,'Stable base');
 projection.load('presentation');
 assert.deepEqual(projection.project(state),projected);
});

test('admitted presentation guide reads the contract with zero model arguments',async()=>{
 let rendererCalls=0,loaded=0;
 const opts={runRenderer:async(command,args)=>{
  rendererCalls++;assert.deepEqual(args,['--contract']);
  return {stdout:JSON.stringify({schema:'capstone-presentation-content-contract/1'})};
 }};
 const base={...config(),loadPresentationGuide:()=>{loaded++;}};
 assert.equal(createPresentationTools(base,opts).length,1);
 base.applicationPolicy.allowed_tools.push('agent_presentation_guide');
 const [library,guide]=createPresentationTools(base,opts);
 assert.equal(guide.name,'agent_presentation_guide');
 assert.deepEqual(guide.parameters,{type:'object',properties:{},additionalProperties:false});
 assert.match(library.description,/^For a new PPTX, call agent_presentation_guide before/);
 const result=await guide.execute('load',{});
 assert.equal(result.isError,false);
 assert.equal(result.details.capability,'agent_presentation_guide');
 assert.match(result.content[0].text,/workspace root/);
 assert.match(result.content[0].text,/slides\/data.csv/);
 assert.equal(JSON.parse(result.content[1].text).schema,'capstone-presentation-content-contract/1');
 assert.equal(rendererCalls,1);
 assert.equal(loaded,1);
});

test('table briefing stages exact sources before rendering and rejects missing cells before writes',async()=>{
 const {mkdtemp,readdir,readFile,rm}=await import('node:fs/promises');
 const {tmpdir}=await import('node:os');
 const {join}=await import('node:path');
 const cwd=await mkdtemp(join(tmpdir(),'capstone-brief-test-'));
 const sha='c'.repeat(64),template={template_id:'state-grid',version:'sha256:'+sha,sha256:sha};
 let renders=0;
 const cfg={...config(),toolResultCwd:cwd,loadPresentationGuide(){}};
 cfg.applicationPolicy.allowed_tools.push('agent_presentation_guide','agent_presentation_build');
 const tool=createPresentationTools(cfg,{
  fetchImpl:async()=>new Response(JSON.stringify({ok:true,result:{template,
    path:'/inputs/task/presentation-templates/state-grid/'+sha+'.pptx'}})),
  runRenderer:async(_command,args,options)=>{
   renders++;
   const spec=JSON.parse(await readFile(join(options.cwd,args[1]),'utf8'));
   const slide=spec.slides[0],path=slide.blocks[0].csv;
   assert.ok(path.startsWith(args[1].split('/')[0]+'/'));
   assert.match(await readFile(join(options.cwd,path),'utf8'),/"Feb","110"/);
   assert.equal(slide.argument.explanation,'Use rose by 10%.');
   assert.deepEqual(slide.source_notes,['Provided data']);
   return {stdout:JSON.stringify({schema:'capstone-presentation-library-render/1',output:args[3],template_sha256:sha})};
  }}).find(entry=>entry.name==='agent_presentation_build');
 const draft={title:'Monthly use',columns:['Month','MWh'],rows:[['Jan',100],['Feb',110]],
  explanation:'Use rose by 10%.',source_note:'Provided data'};
 try{
  const missing=await tool.execute('missing',{...draft,rows:[['Jan']]});
  assert.equal(missing.isError,true);
  assert.deepEqual(await readdir(cwd),[]);
  assert.equal(renders,0);
  const result=await tool.execute('run',draft);
  assert.equal(result.isError,false);
  assert.equal(renders,1);
  assert.match(result.details.result.output,/presentation\.pptx$/);
  assert.match(result.details.saved_inputs.spec,/spec\.json$/);
 }finally{await rm(cwd,{recursive:true,force:true});}
});

test('thin PPT guide enables the workflow through a stable skill tool contract',async()=>{
 const cfg={...config(),loadPresentationGuide(){},stablePresentationStep:true};
 cfg.applicationPolicy.allowed_tools.push('agent_presentation_guide','agent_skill_step');
 const tools=createPresentationTools(cfg,{runRenderer:async()=>({stdout:'{"schema":"capstone-presentation-content-contract/1"}'})});
 assert.ok(!tools.some(tool=>tool.name==='agent_presentation_build'));
 const step=tools.find(tool=>tool.name==='agent_skill_step');
 const before=JSON.stringify(step.parameters);
 const args={step:'agent_presentation_build',arguments:{}};
 assert.equal((await step.execute('early',args)).details.code,'presentation_guide_required');
 const result=await tools.find(tool=>tool.name==='agent_presentation_guide').execute('guide',{});
 assert.match(result.content[0].text,/agent_skill_step/);
 assert.match(result.content[0].text,/source_note/);
 assert.doesNotMatch(JSON.stringify(result.content),/capstone-presentation-content-contract/);
 assert.deepEqual(tools.find(tool=>tool.name==='agent_presentation_guide').parameters.properties,{});
 const full=await tools.find(tool=>tool.name==='agent_presentations').execute('full',{operation:'contract'});
 assert.match(JSON.stringify(full.content),/capstone-presentation-content-contract/);
 assert.equal(JSON.stringify(step.parameters),before);
 assert.equal((await step.execute('unknown',{...args,step:'bash'})).isError,true);
 assert.equal((await step.execute('invalid',args)).details.code,'presentation_inputs_invalid');
});
