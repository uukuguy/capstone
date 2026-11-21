import test from 'node:test';
import assert from 'node:assert/strict';
import {createInstructionSteering} from '../src/capstone_agent/resources/general-sdk.mjs';
import {createManagedChildSession,runSettledPrompt} from '../src/capstone_agent/resources/general-sdk.mjs';
import {mkdtemp,mkdir,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';

test('steering acknowledges actual user message consumption, with stable identity', async()=>{
 let observe; const queued=[], receipts=[];
 const session={subscribe(fn){observe=fn;return ()=>{};},async steer(text){queued.push(text);}};
 const steering=createInstructionSteering(session,{},event=>receipts.push(event));
 const frame={type:'steer',instruction_id:'instruction-1',text:'/skill:other keep the prior result'};
 await steering.accept(JSON.stringify(frame));
 await steering.accept(JSON.stringify(frame));
 assert.equal(queued.length,1);assert.equal(receipts.length,0);
 observe({type:'message_start',message:{role:'assistant',content:queued[0]}});
 assert.equal(receipts.length,0);
 observe({type:'message_start',message:{role:'user',content:[{type:'text',text:queued[0]}]}});
 assert.equal(receipts.length,0);
 observe({type:'message_end',message:{role:'user',content:[{type:'text',text:queued[0]}]}});
 assert.deepEqual(receipts,[{type:'general_pi_instruction_consumed',instruction_id:'instruction-1'}]);
 await assert.rejects(steering.accept(JSON.stringify({...frame,text:'changed'})),/identity/);
 steering.close();
 await assert.rejects(steering.accept(JSON.stringify({...frame,instruction_id:'later'})),/closed/);
});

test('steering rejects grant fields and invalid or unbounded text',async()=>{
 const steering=createInstructionSteering({subscribe(){return ()=>{}},async steer(){}},{},()=>{});
 for(const frame of [{type:'steer',instruction_id:'x',text:'ok',grants:[]},
   {type:'steer',instruction_id:'x',text:''},{type:'steer',instruction_id:'x',text:'x'.repeat(2000000)}]){
  await assert.rejects(steering.accept(JSON.stringify(frame)));
 }
 steering.close();
});

test('steering enforces the host instruction limit before adding another message',async()=>{
 const queued=[];
 const steering=createInstructionSteering({subscribe(){return ()=>{}},async steer(text){queued.push(text)}},{instructionLimit:1},()=>{});
 await steering.accept(JSON.stringify({type:'steer',instruction_id:'first',text:'One'}));
 await assert.rejects(steering.accept(JSON.stringify({type:'steer',instruction_id:'second',text:'Two'})),/bounds/);
 assert.equal(queued.length,1);steering.close();
});

test('pinned SDK stores steering before receipt and settles the resulting model turn',async()=>{
 const root=resolve('.grid-agent/runtime/pi/source/packages');
 const sdk=await import(pathToFileURL(resolve(root,'coding-agent/dist/index.js')).href);
 const ai=await import(pathToFileURL(resolve(root,'ai/dist/index.js')).href);
 const cwd=await mkdtemp(resolve(tmpdir(),'native-steering-')),oldCwd=process.cwd(),oldAgent=process.env.PI_CODING_AGENT_DIR;
 const model={id:'steer-offline',name:'Offline',provider:'capstone-general',api:'openai-completions',baseUrl:'http://127.0.0.1:1',
  reasoning:false,input:['text'],contextWindow:32000,maxTokens:1024,cost:{input:0,output:0,cacheRead:0,cacheWrite:0}};
 let turn=0,owned,steering;const receipts=[],events=[];
 const original='Run a tool.';
 const envelope='User instruction (instruction-1):\n/skill:other preserve this exact text';
 const runtime={getModel:()=>model,hasConfiguredAuth:()=>true,getAuth:async()=>({auth:{apiKey:'offline-fixture'}}),isUsingOAuth:()=>false,
  streamSimple(_model,context){
   if(turn){
    assert.equal(receipts.length,1);
    for(const expected of [original,envelope]){
     assert.equal(context.messages.filter(m=>m.role==='user'&&(typeof m.content==='string'?m.content===expected:m.content.some(p=>p.text===expected))).length,1);
    }
   }
   const message={role:'assistant',content:turn++===0?[{type:'toolCall',id:'tool-1',name:'bash',arguments:{command:'printf safe'}}]:[{type:'text',text:'Steering settled.'}],
    api:model.api,provider:model.provider,model:model.id,timestamp:Date.now(),stopReason:turn===1?'toolUse':'stop',
    usage:{input:0,output:0,cacheRead:0,cacheWrite:0,totalTokens:0,cost:{input:0,output:0,cacheRead:0,cacheWrite:0,total:0}}};
   const stream=ai.createAssistantMessageEventStream();stream.push({type:'done',reason:message.stopReason,message});stream.end();return stream;
  }};
 try{
  process.chdir(cwd);process.env.PI_CODING_AGENT_DIR=resolve(cwd,'agent');await mkdir(process.env.PI_CODING_AGENT_DIR);
  owned=await createManagedChildSession({model:model.id,settings:{packages:[],extensions:[],skills:[]},extensions:[],allowedSkills:[],contextFiles:[],
   systemPrompt:'Use authorized shell tools.',applicationPolicy:{allowed_tools:['bash']}},sdk,runtime,{toolNames:['bash'],cwd});
  const session=owned.session;
  steering=createInstructionSteering(session,{input:{kind:'text',text:original}},receipt=>{
   assert(session.messages.some(m=>m.role==='user'&&m.content.some(p=>p.text===envelope)),'receipt requires stored context');
   receipts.push(receipt);
  });
  const unsubscribe=session.subscribe(event=>{
   if(event.type==='tool_execution_start')void steering.accept(JSON.stringify({type:'steer',instruction_id:'instruction-1',text:'/skill:other preserve this exact text'}));
   if(event.type==='message_start'&&event.message.role==='user'&&event.message.content.some(p=>p.text===envelope))assert.equal(receipts.length,0);
  });
  await runSettledPrompt(session,{kind:'text',text:'Run a tool.'},null,event=>events.push(event));
  unsubscribe();assert.equal(turn,2);assert.equal(receipts.length,1);
  for(let pass=0;pass<2;pass++){
   const last=session.sessionManager.getBranch().at(-1);
   session.sessionManager.appendCompaction('A summary without user guidance.',last.id,1000);
   session.agent.state.messages=session.sessionManager.buildSessionContext().messages;
   assert(!session.messages.some(m=>m.role==='user'));
   await runSettledPrompt(session,{kind:'text',text:'Continue after the saved compaction.'},null,event=>events.push(event));
   assert.equal(turn,3+pass);assert.equal(receipts.length,1);
  }
  assert.equal(events.at(-1).type,'agent_end');assert.equal(events.at(-1).messages.at(-1).content[0].text,'Steering settled.');
 }finally{
  steering?.close();await owned?.close();process.chdir(oldCwd);
  if(oldAgent===undefined)delete process.env.PI_CODING_AGENT_DIR;else process.env.PI_CODING_AGENT_DIR=oldAgent;
  await rm(cwd,{recursive:true,force:true});
 }
});

test('model context restores compacted admitted instructions without replaying pending input', async()=>{
 let observe;
 const queued=[];
 const agent={transformContext:async messages=>messages.slice()};
 const session={agent,subscribe(fn){observe=fn;return ()=>{};},async steer(text){queued.push(text);}};
 const original={role:'user',content:'Prepare the report in Chinese',timestamp:0};
 const steering=createInstructionSteering(session,{input:{kind:'text',text:original.content}},()=>{});
 observe({type:'message_end',message:original});
 for(const [id,text] of [['first','Use only the approved inputs'],['next','Pending instruction']]){
  await steering.accept(JSON.stringify({type:'steer',instruction_id:id,text}));
 }
 const admitted={role:'user',content:queued[0],timestamp:1};
 observe({type:'message_end',message:admitted});
 assert.deepEqual(await agent.transformContext([original,admitted]),[original,admitted]);
 const recent={role:'user',content:'Use the revised format',timestamp:2};
 for(let pass=0;pass<2;pass++){
  assert.deepEqual(await agent.transformContext([recent]),[original,admitted,recent]);
 }
 steering.close();
 assert.deepEqual(await agent.transformContext([recent]),[recent]);
});
