import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,mkdir,writeFile,chmod,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {resolve,join} from 'node:path';
import {pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';

test('pinned SDK registers and executes admitted range tool',async()=>{
 const root=resolve('.grid-agent/runtime/pi/source/packages');
 const sdk=await import(pathToFileURL(resolve(root,'coding-agent/dist/index.js')).href);
 const ai=await import(pathToFileURL(resolve(root,'ai/dist/index.js')).href);
 const adapter=await import('../src/capstone_agent/resources/general-sdk.mjs');
 const cwd=await mkdtemp(join(tmpdir(),'range-sdk-'));
 const previous=process.env.PI_CODING_AGENT_DIR,previousCwd=process.cwd();
 const resource={schema:'capstone-resource/1',thread_id:'thr_test',resource_id:'resource_'+'a'.repeat(32),sha256:'b'.repeat(64),size_bytes:10000000,file_name:'large.bin',version:1};
 const bytes=Buffer.from('sample'),callId='range-call',request_id=createHash('sha256').update(JSON.stringify(['range',callId])).digest('hex');
 const receipt={schema:'capstone-resource-read/1',read_id:'read_test',thread_id:'thr_test',attempt_id:'attempt',task_id:'task',request_id,resource,offset:100,length:6,sha256:createHash('sha256').update(bytes).digest('hex'),preview:{status:'text',bytes_read:6,truncated:false,text:'sample'}};
 const model={id:'range-offline',name:'Offline',provider:'capstone-general',api:'openai-completions',baseUrl:'http://127.0.0.1:1',reasoning:false,input:['text'],contextWindow:32000,maxTokens:1024,cost:{input:0,output:0,cacheRead:0,cacheWrite:0}};
 let turn=0,owned;
 const runtime={getModel:()=>model,hasConfiguredAuth:()=>true,getAuth:async()=>({auth:{apiKey:'offline-fixture'}}),isUsingOAuth:()=>false,
  streamSimple(_model,context){
   assert.ok(context.tools.some(tool=>tool.name==='agent_resource_read'));
   if(turn===1){
    const result=context.messages.filter(message=>message.role==='toolResult').at(-1);
    assert.equal(result.isError,false,JSON.stringify(result));
    assert.deepEqual(JSON.parse(result.content[0].text).receipt,receipt);
   }
   const content=turn===0?[{type:'toolCall',id:callId,name:'agent_resource_read',arguments:{resource_id:resource.resource_id,offset:100,length:6}}]:[{type:'text',text:'Selected bytes returned.'}];
   const message={role:'assistant',content,api:model.api,provider:model.provider,model:model.id,timestamp:Date.now(),stopReason:turn++===0?'toolUse':'stop',usage:{input:0,output:0,cacheRead:0,cacheWrite:0,totalTokens:0,cost:{input:0,output:0,cacheRead:0,cacheWrite:0,total:0}}};
   const stream=ai.createAssistantMessageEventStream();stream.push({type:'done',reason:message.stopReason,message});stream.end();return stream;
  }};
 try{
  for(const dir of ['agent','port/range-requests','port/range-responses','inputs/ranges'])await mkdir(join(cwd,dir),{recursive:true});
  const path=join(cwd,'inputs/ranges',request_id);await writeFile(path,bytes);await chmod(path,0o440);
  await writeFile(join(cwd,'port/range-responses',request_id+'.json'),JSON.stringify({ok:true,receipt,path}));
  process.chdir(cwd);process.env.PI_CODING_AGENT_DIR=join(cwd,'agent');
  const config={taskId:'task',resourceAttemptId:'attempt',model:model.id,settings:{packages:[],extensions:[],skills:[]},extensions:[],allowedSkills:[],contextFiles:[],systemPrompt:'Use the admitted range tool.',applicationPolicy:{allowed_tools:['agent_resource_read','agent_resource_open']},resourceReferencePath:join(cwd,'port'),resourceInputRoot:join(cwd,'inputs'),resourceReferences:[resource],resourceReadBytes:1024,deadlineAt:Date.now()+5000};
  owned=await adapter.createManagedChildSession(config,sdk,runtime,{toolNames:['agent_resource_read'],cwd});
  await owned.session.prompt('Read the selected bytes.');
  assert.equal(turn,2);
 }finally{await owned?.close();process.chdir(previousCwd);if(previous===undefined)delete process.env.PI_CODING_AGENT_DIR;else process.env.PI_CODING_AGENT_DIR=previous;await rm(cwd,{recursive:true,force:true});}
});
