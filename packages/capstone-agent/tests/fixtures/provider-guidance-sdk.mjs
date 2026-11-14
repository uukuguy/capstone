// Consume the actual Python runner's captured configuration through the pinned SDK.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {mkdtemp,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import * as sdk from '../../../../.grid-agent/runtime/pi/source/packages/coding-agent/dist/index.js';
import * as ai from '../../../../.grid-agent/runtime/pi/source/packages/ai/dist/index.js';
import {skillContextFiles} from '../../src/capstone_agent/resources/investigation-skills.mjs';

const config=JSON.parse(readFileSync(process.argv[2],'utf8'));
const cwd=await mkdtemp(join(tmpdir(),'provider-sdk-'));
const model={id:'fixture',name:'Fixture',provider:'capstone-general',api:'openai-completions',
 baseUrl:'http://127.0.0.1:1',reasoning:false,input:['text'],contextWindow:32000,maxTokens:1024,
 cost:{input:0,output:0,cacheRead:0,cacheWrite:0,total:0}};
let calls=0,session;
const runtime={getModel:()=>model,hasConfiguredAuth:()=>true,getAuth:async()=>({auth:{apiKey:'offline'}}),isUsingOAuth:()=>false,
 streamSimple(_model,context){
  calls++;assert.match(context.systemPrompt,/VISIBLE_PROVIDER_RULE/);
  assert.ok(!context.systemPrompt.includes('HIDDEN_PROVIDER_RULE'));
  assert.match(context.systemPrompt,/only to its declaring provider/);
  const message={role:'assistant',content:[{type:'text',text:'Checked'}],api:model.api,provider:model.provider,
   model:model.id,timestamp:Date.now(),stopReason:'stop',usage:{input:0,output:0,cacheRead:0,cacheWrite:0,totalTokens:0,cost:{total:0}}};
  const stream=ai.createAssistantMessageEventStream();stream.push({type:'done',reason:'stop',message});stream.end();return stream;
 }};
try{
 const settingsManager=sdk.SettingsManager.inMemory({compaction:{enabled:false}});
 const resourceLoader=new sdk.DefaultResourceLoader({cwd,agentDir:cwd,settingsManager,noExtensions:true,noSkills:true,
  noPromptTemplates:true,noThemes:true,noContextFiles:true,agentsFilesOverride:()=>({agentsFiles:skillContextFiles(config)})});
 await resourceLoader.reload();
 ({session}=await sdk.createAgentSession({cwd,agentDir:cwd,model,modelRuntime:runtime,settingsManager,resourceLoader,
  tools:[],customTools:[],sessionManager:sdk.SessionManager.inMemory()}));
 await session.prompt('Check the selected provider declaration.');assert.equal(calls,1);
}finally{session?.dispose();await rm(cwd,{recursive:true,force:true});}
