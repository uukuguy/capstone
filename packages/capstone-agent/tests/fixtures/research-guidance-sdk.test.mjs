import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join,resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {configureResearchGuidance} from '../../src/capstone_agent/resources/research-guidance.mjs';

test('pinned SDK receives one scope reminder after a real tool turn without another user message',async()=>{
 const root=resolve('.grid-agent/runtime/pi/source/packages');
 const sdk=await import(pathToFileURL(join(root,'coding-agent/dist/index.js')).href);
 const ai=await import(pathToFileURL(join(root,'ai/dist/index.js')).href);
 const cwd=await mkdtemp(join(tmpdir(),'scope-sdk-'));
 const model={id:'scope-fixture',name:'Scope',provider:'capstone-general',api:'openai-completions',baseUrl:'http://127.0.0.1:1',reasoning:false,input:['text'],contextWindow:32000,maxTokens:1024,cost:{input:0,output:0,cacheRead:0,cacheWrite:0}};
 const contexts=[],checkpoints=[];let session;
 const runtime={getModel:()=>model,hasConfiguredAuth:()=>true,getAuth:async()=>({auth:{apiKey:'offline-fixture'}}),isUsingOAuth:()=>false,
  streamSimple(_model,context){
   contexts.push({messages:structuredClone(context.messages),systemPrompt:context.systemPrompt});const first=contexts.length===1;
   const message={role:'assistant',content:first?[{type:'toolCall',id:'read-one',name:'fixture_read',arguments:{}}]:[{type:'text',text:'The selected sample is empty; wider coverage is unknown.'}],api:model.api,provider:model.provider,model:model.id,timestamp:Date.now(),stopReason:first?'toolUse':'stop',usage:{input:1,output:1,cacheRead:0,cacheWrite:0,totalTokens:2,cost:{input:0,output:0,cacheRead:0,cacheWrite:0,total:0}}};
   const stream=ai.createAssistantMessageEventStream();stream.push({type:'done',reason:message.stopReason,message});stream.end();return stream;
  }};
 try{
  const settingsManager=sdk.SettingsManager.inMemory({packages:[],extensions:[],skills:[],compaction:{enabled:false}});
  const resourceLoader=new sdk.DefaultResourceLoader({cwd,agentDir:cwd,settingsManager,noContextFiles:true,noThemes:true,extensionFactories:[pi=>configureResearchGuidance(pi,'Report progress.',{lightweight:true,checkpointCalls:1,onCheckpoint:event=>checkpoints.push(event)})]});
  await resourceLoader.reload();
  const customTools=[{name:'fixture_read',label:'Read fixture',description:'Read selected sample',parameters:{type:'object',properties:{}},execute:async()=>({content:[{type:'text',text:'{"rows":[],"scope":"one selected window"}'}]})}];
  ({session}=await sdk.createAgentSession({cwd,agentDir:cwd,model,modelRuntime:runtime,settingsManager,resourceLoader,tools:['fixture_read'],customTools,sessionManager:sdk.SessionManager.inMemory()}));
  await session.bindExtensions({onError:error=>{throw error;}});session.setActiveToolsByName(['fixture_read']);
  await session.prompt('Read one selected window.');
  assert.equal(contexts.length,2,JSON.stringify(session.messages));
  assert.equal(contexts[1].messages.filter(m=>m.role==='user').length,1);
  const tool=contexts[1].messages.find(m=>m.role==='toolResult');
  assert.match(tool.content[0].text,/"rows":\[\]/);
  assert.match(tool.content.at(-1).text,/Scope review checkpoint: 1 completed leaf calls/);
  assert.equal(session.messages.find(m=>m.role==='toolResult').content.length,1);
  assert.deepEqual(checkpoints.map(c=>c.state),['context_prepared','response_received']);
  assert.deepEqual(checkpoints.map(c=>c.checkpoint_id),[1,1]);
 }finally{session?.dispose();await rm(cwd,{recursive:true,force:true});}
});
