import test from 'node:test';
import {Readable} from 'node:stream';
import assert from 'node:assert/strict';
import {mkdtemp,mkdir,rm,writeFile,realpath} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {pathToFileURL,fileURLToPath} from 'node:url';
import {createManagedChildSession,runSettledPrompt,runManagedSession} from '../../src/capstone_agent/resources/general-sdk.mjs';
import {runtimeLimits,checkCapacity} from '../../src/capstone_agent/resources/runtime-limits.mjs';
const root=fileURLToPath(new URL('../../../../',import.meta.url));

for(const kind of ['builtin','research-progress'])test('actual pinned SDK debug capacity aborts task before another tool or model response: '+kind, {timeout:15000},async()=>{
 const sdk=await import(pathToFileURL(join(root,'.grid-agent/runtime/pi/source/packages/coding-agent/dist/index.js')).href);
 const ai=await import(pathToFileURL(join(root,'.grid-agent/runtime/pi/source/packages/ai/dist/index.js')).href);
 const dir=await realpath(await mkdtemp(join(tmpdir(),'debug-capacity-sdk-'))),oldCwd=process.cwd(),oldAgent=process.env.PI_CODING_AGENT_DIR;
 const agent=join(dir,'.agent');await mkdir(agent);
 const stdinDescriptor=Object.getOwnPropertyDescriptor(process,'stdin');
 let responses=0,reads=0,writes=0,child;
 const model={id:'offline-debug',name:'Offline debug',provider:'capstone-general',api:'openai-completions',baseUrl:'http://127.0.0.1:1',reasoning:false,input:['text'],contextWindow:32000,maxTokens:1024,cost:{input:0,output:0,cacheRead:0,cacheWrite:0}};
 const runtime={getModel:()=>model,hasConfiguredAuth:()=>true,getAuth:async()=>({auth:{apiKey:'offline'}}),isUsingOAuth:()=>false,streamSimple(){
  responses++;
  const content=responses===1?[{type:'toolCall',id:'exceed',name:kind==='builtin'?'read':'agent_task_progress',arguments:kind==='builtin'?{}:{kind:'goal',text:'too long'}},{type:'toolCall',id:'must-not-write',name:'write',arguments:{}}]:[{type:'text',text:'Model repair must not be requested.'}];
  const message={role:'assistant',content,api:model.api,provider:model.provider,model:model.id,timestamp:Date.now(),usage:{input:0,output:0,cacheRead:0,cacheWrite:0,totalTokens:0,cost:{input:0,output:0,cacheRead:0,cacheWrite:0,total:0}},stopReason:responses===1?'toolUse':'stop'};
  const stream=ai.createAssistantMessageEventStream();stream.push({type:'done',reason:message.stopReason,message});stream.end();return stream;
 }};
 const limits=runtimeLimits({input_text_chars:1},{mode:'debug'});
 const tools=['read','write'].map(name=>({name,label:name,description:name,parameters:{type:'object',properties:{}},async execute(){
  if(name==='read'){reads++;checkCapacity(limits,'input_text_chars',2,'characters','offline_tool');}
  else writes++;
  return {content:[{type:'text',text:'actual tool'}],details:{}};
 }}));
 try{
  process.chdir(dir);process.env.PI_CODING_AGENT_DIR=agent;
  if(kind==='research-progress'){
   const channel=join(dir,'channel');await mkdir(channel);await mkdir(join(channel,'requests'));await mkdir(join(channel,'receipts'));
   const identity={run_id:'run-debug',turn_id:'turn-debug',attempt_id:'attempt-debug',research_id:'research-debug'};
   await writeFile(join(channel,'binding.json'),JSON.stringify({schema_version:'capability-research-channel/1.0',...identity,read_tool_schema:{type:'object',additionalProperties:false,properties:{}},update_tool_schema:{type:'object',additionalProperties:false,properties:{changes:{},expected_revision:{}}},progress_tool_schema:{type:'object',additionalProperties:false,required:['kind','text'],properties:{kind:{type:'string',enum:['goal']},text:{type:'string'}}}}));
   await writeFile(join(channel,'view.json'),JSON.stringify({schema_version:'capability-research-view/1.0',...identity,research_revision:0,state:null}));
   const extension=join(dir,'debug-progress.mjs');const module=pathToFileURL(join(root,'packages/pi-capability-tools/src/research-tools.mjs')).href;
   await writeFile(extension,`import {configureResearchTools} from ${JSON.stringify(module)};export default pi=>configureResearchTools(pi,${JSON.stringify(channel)},{runtimeLimitMode:'debug',runtimeLimits:{research_progress_chars:4}});`);
   Object.defineProperty(process,'stdin',{value:Readable.from([JSON.stringify({type:'prompt',message:'trigger'})+'\n']),configurable:true});
   await assert.rejects(runManagedSession({model:model.id,settings:{compaction:{enabled:false}},extensions:[extension],allowedSkills:[],contextFiles:[],runtimeLimitMode:'debug',runtimeLimits:{research_progress_chars:4},applicationPolicy:{allowed_tools:['agent_task_progress','write']},input:{kind:'text',text:'Run tool'}},{...sdk,createCodingTools:()=>tools,DefaultResourceLoader:class extends sdk.DefaultResourceLoader{async reload(){await super.reload();if(this.getExtensions().errors.length)throw Error(JSON.stringify(this.getExtensions().errors));}}},runtime),error=>error.capacity?.mode==='debug'&&error.capacity.dimension==='research_progress_chars');
   assert.equal(responses,1);assert.equal(writes,0);return;
  }
  child=await createManagedChildSession({model:model.id,settings:{compaction:{enabled:false}},extensions:[],allowedSkills:[],contextFiles:[],runtimeLimitMode:'debug',runtimeLimits:{input_text_chars:1},applicationPolicy:{allowed_tools:['read','write']}},{...sdk,createCodingTools:()=>tools},runtime,{toolNames:['read','write'],cwd:dir});
  await assert.rejects(runSettledPrompt(child.session,{kind:'text',text:'Run tools'},null,()=>{}),error=>error.capacity?.mode==='debug'&&error.capacity.dimension==='input_text_chars');
  assert.equal(responses,1);assert.equal(reads,1);assert.equal(writes,0);
 }finally{
  await child?.close();if(stdinDescriptor)Object.defineProperty(process,'stdin',stdinDescriptor);process.chdir(oldCwd);if(oldAgent===undefined)delete process.env.PI_CODING_AGENT_DIR;else process.env.PI_CODING_AGENT_DIR=oldAgent;await rm(dir,{recursive:true,force:true});
 }
});
