import assert from 'node:assert/strict';
import {readFile,mkdtemp,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import * as adapter from '../../src/capstone_agent/resources/general-sdk.mjs';

const config=JSON.parse(await readFile(process.argv[2],'utf8'));
const sdk=await import(pathToFileURL(resolve('.grid-agent/runtime/pi/source/packages/coding-agent/dist/index.js')).href);
const cwd=await mkdtemp(resolve(tmpdir(),'mission-resource-registration-'));
const model={id:'offline',name:'Offline',provider:'fixture',api:'openai-completions',baseUrl:'http://127.0.0.1:1',
 reasoning:false,input:['text'],contextWindow:32000,maxTokens:1024,cost:{input:0,output:0,cacheRead:0,cacheWrite:0}};
const runtime={getModel:()=>model,hasConfiguredAuth:()=>true,getAuth:async()=>({auth:{apiKey:'offline-fixture'}}),isUsingOAuth:()=>false,
 streamSimple(){throw new Error('This registration check must not call a model');}};
let session;
try{
 const settingsManager=sdk.SettingsManager.inMemory({compaction:{enabled:false}});
 const loader=new sdk.DefaultResourceLoader({cwd,agentDir:cwd,settingsManager,noExtensions:true,noSkills:true,
  noPromptTemplates:true,noThemes:true,noContextFiles:true,agentsFilesOverride:()=>({agentsFiles:[]})});
 await loader.reload();
 ({session}=await sdk.createAgentSession({cwd,agentDir:cwd,modelRuntime:runtime,model,resourceLoader:loader,settingsManager,
  sessionManager:sdk.SessionManager.inMemory(),...adapter.applicationToolOptions(config,adapter.createIsolatedNativeTools(sdk,cwd))}));
 session.setActiveToolsByName(config.applicationPolicy.allowed_tools);
 const tools=session.getActiveToolNames().sort();
 assert(!tools.includes('bash')&&!tools.includes('read')&&!tools.includes('edit'));
 assert(tools.includes('write'));
 for(const helper of ['agent_resource_open','agent_resource_read'])assert.equal(tools.includes(helper),config.applicationPolicy.allowed_tools.includes(helper));
 process.stdout.write(JSON.stringify({tools})+'\n');
}finally{session?.dispose();await rm(cwd,{recursive:true,force:true});}
