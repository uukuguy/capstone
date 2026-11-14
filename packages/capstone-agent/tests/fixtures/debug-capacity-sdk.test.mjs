import test from 'node:test';
import {Readable} from 'node:stream';
import assert from 'node:assert/strict';
import {mkdtemp,mkdir,rm,writeFile,realpath} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {pathToFileURL,fileURLToPath} from 'node:url';
import {createManagedChildSession,runSettledPrompt,runManagedSession} from '../../src/capstone_agent/resources/general-sdk.mjs';
import {runtimeLimits,checkCapacity,onDebugCapacityExceeded,CapacityExceeded} from '../../src/capstone_agent/resources/runtime-limits.mjs';
const root=fileURLToPath(new URL('../../../../',import.meta.url));

for(const kind of ['builtin','research-progress','valid-parallel'])test(
 'actual pinned SDK preserves debug repair, grants and independent tools: '+kind,
 {timeout:15000},async()=>{
 const sdk=await import(pathToFileURL(join(root,'.grid-agent/runtime/pi/source/packages/coding-agent/dist/index.js')).href);
 const ai=await import(pathToFileURL(join(root,'.grid-agent/runtime/pi/source/packages/ai/dist/index.js')).href);
 const dir=await realpath(await mkdtemp(join(tmpdir(),'debug-capacity-sdk-'))),oldCwd=process.cwd(),oldAgent=process.env.PI_CODING_AGENT_DIR;
 const agent=join(dir,'.agent');await mkdir(agent);
 const stdinDescriptor=Object.getOwnPropertyDescriptor(process,'stdin');
 let responses=0,reads=0,writes=0,denied=0,child,enteredWrite;
 const writeStarted=new Promise(resolve=>{enteredWrite=resolve;});
 const diagnostics=[],typedFailures=[],events=[];
 const stopObservation=onDebugCapacityExceeded(error=>typedFailures.push(error));
 const stderrWrite=process.stderr.write;
 const model={id:'offline-debug',name:'Offline debug',provider:'capstone-general',api:'openai-completions',baseUrl:'http://127.0.0.1:1',reasoning:false,input:['text'],contextWindow:32000,maxTokens:1024,cost:{input:0,output:0,cacheRead:0,cacheWrite:0,totalTokens:0}};
 const toolCall=(id,name,args={})=>({type:'toolCall',id,name,arguments:args});
 const runtime={getModel:()=>model,hasConfiguredAuth:()=>true,getAuth:async()=>({auth:{apiKey:'offline'}}),isUsingOAuth:()=>false,
  streamSimple(_model,context){
   responses++;
   let content,stopReason='toolUse';
   if(responses===1){
    content=[kind==='research-progress'?toolCall('exceed','agent_task_progress',{kind:'goal',text:'too long'}):
     toolCall('exceed','read',{size:kind==='valid-parallel'?1:2}),
     toolCall('independent','write'),toolCall('outside-grant','denied')];
   }else if(responses===2){
    const results=context.messages.filter(message=>message.role==='toolResult');
    const exceeded=results.find(result=>result.toolCallId==='exceed');
    assert.equal(exceeded.isError,kind!=='valid-parallel','An oversized call cannot appear successful');
    assert.equal(results.find(result=>result.toolCallId==='independent').isError,false,'Independent admitted work remains available');
    assert.equal(results.find(result=>result.toolCallId==='outside-grant').isError,true);
    assert.equal(denied,0,'Rejected calls never enter their implementation');
    if(kind==='valid-parallel'){content=[{type:'text',text:'Completed independent work.'}];stopReason='stop';}
    else{
     assert.match(JSON.stringify(exceeded),/capacity_exceeded/);
     assert.equal(writes,1,'Debug capacity does not cancel sibling work');
     content=[kind==='builtin'?toolCall('repair','read',{size:1}):toolCall('repair','write')];
    }
   }else{
    const repaired=context.messages.find(message=>message.role==='toolResult'&&message.toolCallId==='repair');
    assert.equal(repaired.isError,false,'The same task grant admits a corrected next action');
    content=[{type:'text',text:'Completed after observed correction.'}];stopReason='stop';
   }
   const message={role:'assistant',content,api:model.api,provider:model.provider,model:model.id,timestamp:Date.now(),
    usage:{input:0,output:0,cacheRead:0,cacheWrite:0,totalTokens:0,cost:{input:0,output:0,cacheRead:0,cacheWrite:0,total:0}},stopReason};
   const stream=ai.createAssistantMessageEventStream();stream.push({type:'done',reason:message.stopReason,message});stream.end();return stream;
  }};
 const limits=runtimeLimits({input_text_chars:1},{mode:'debug'});
 const tools=['read','write','denied'].map(name=>({name,label:name,description:name,
  parameters:{type:'object',properties:{size:{type:'number'}}},async execute(_id,args){
   if(name==='read'){reads++;if(kind==='valid-parallel')await writeStarted;
    checkCapacity(limits,'input_text_chars',args.size,'characters','offline_tool');}
   else if(name==='write'){writes++;enteredWrite();}
   else denied++;
   return {content:[{type:'text',text:'actual tool'}],details:{}};
  }}));
 try{
  process.stderr.write=function(chunk,...args){
   if(String(chunk).includes('"type":"capacity_diagnostic"')){diagnostics.push(JSON.parse(String(chunk)));return true;}
   return stderrWrite.call(this,chunk,...args);
  };
  process.chdir(dir);process.env.PI_CODING_AGENT_DIR=agent;
  if(kind==='research-progress'){
   const channel=join(dir,'channel');await mkdir(channel);await mkdir(join(channel,'requests'));await mkdir(join(channel,'receipts'));
   const identity={run_id:'run-debug',turn_id:'turn-debug',attempt_id:'attempt-debug',research_id:'research-debug'};
   await writeFile(join(channel,'binding.json'),JSON.stringify({schema_version:'capability-research-channel/1.0',...identity,
    read_tool_schema:{type:'object',additionalProperties:false,properties:{}},update_tool_schema:{type:'object',additionalProperties:false,properties:{changes:{},expected_revision:{}}},
    progress_tool_schema:{type:'object',additionalProperties:false,required:['kind','text'],properties:{kind:{type:'string',enum:['goal']},text:{type:'string'}}}}));
   await writeFile(join(channel,'view.json'),JSON.stringify({schema_version:'capability-research-view/1.0',...identity,research_revision:0,state:null}));
   const extension=join(dir,'debug-progress.mjs'),module=pathToFileURL(join(root,'packages/pi-capability-tools/src/research-tools.mjs')).href;
   await writeFile(extension,`import {configureResearchTools} from ${JSON.stringify(module)};export default pi=>configureResearchTools(pi,${JSON.stringify(channel)},{runtimeLimitMode:'debug',runtimeLimits:{research_progress_chars:4}});`);
   Object.defineProperty(process,'stdin',{value:Readable.from([JSON.stringify({type:'prompt',message:'trigger'})+'\n']),configurable:true});
   await runManagedSession({model:model.id,settings:{compaction:{enabled:false}},extensions:[extension],allowedSkills:[],contextFiles:[],
    runtimeLimitMode:'debug',runtimeLimits:{research_progress_chars:4},applicationPolicy:{allowed_tools:['agent_task_progress','write']},input:{kind:'text',text:'Run tool'}},
    {...sdk,createCodingTools:()=>tools,DefaultResourceLoader:class extends sdk.DefaultResourceLoader{
     async reload(){await super.reload();if(this.getExtensions().errors.length)throw Error(JSON.stringify(this.getExtensions().errors));}}},runtime);
  }else{
   child=await createManagedChildSession({model:model.id,settings:{compaction:{enabled:false}},extensions:[],allowedSkills:[],contextFiles:[],
    runtimeLimitMode:'debug',runtimeLimits:{input_text_chars:1},applicationPolicy:{allowed_tools:['read','write']}},
    {...sdk,createCodingTools:()=>tools},runtime,{toolNames:['read','write'],cwd:dir});
   await runSettledPrompt(child.session,{kind:'text',text:'Run independent tools'},null,event=>events.push(event));
   assert.equal(child.session.agent.toolExecution,'parallel');
   assert.equal(events.at(-1).type,'agent_end');
   assert.equal(events.at(-1).messages.at(-1).stopReason,'stop');
  }
  assert.equal(responses,kind==='valid-parallel'?2:3);
  assert.equal(reads,kind==='builtin'?2:kind==='valid-parallel'?1:0);
  assert.equal(writes,kind==='research-progress'?2:1);assert.equal(denied,0);
  assert.equal(diagnostics.length,kind==='valid-parallel'?0:1);
  assert.equal(typedFailures.length,diagnostics.length);
  if(kind!=='valid-parallel'){
   assert.ok(typedFailures[0] instanceof CapacityExceeded);
   assert.equal(typedFailures[0].code,'capacity_exceeded');
   assert.equal(typedFailures[0].capacity.mode,'debug');
   assert.deepEqual(diagnostics[0],{type:'capacity_diagnostic',code:'capacity_exceeded',mode:'debug',
    dimension:kind==='builtin'?'input_text_chars':'research_progress_chars',actual:kind==='builtin'?2:8,
    limit:kind==='builtin'?1:4,unit:'characters',phase:kind==='builtin'?'offline_tool':'research_progress'});
   assert.ok(Buffer.byteLength(JSON.stringify(diagnostics[0]))<1024);
  }
  await child?.close();
  assert.throws(()=>checkCapacity(limits,'input_text_chars',2,'characters','after_close'));
  assert.equal(diagnostics.length,kind==='valid-parallel'?0:1,'Closed sessions release diagnostic observation');
 }finally{
  stopObservation();process.stderr.write=stderrWrite;await child?.close();
  if(stdinDescriptor)Object.defineProperty(process,'stdin',stdinDescriptor);
  process.chdir(oldCwd);if(oldAgent===undefined)delete process.env.PI_CODING_AGENT_DIR;else process.env.PI_CODING_AGENT_DIR=oldAgent;
  await rm(dir,{recursive:true,force:true});
 }
});
