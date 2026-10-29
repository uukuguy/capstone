import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,mkdir,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {createPooledAnalysisSession} from '../../src/capstone_agent/resources/general-sdk.mjs';
test('pooled reasoning reuses the model but has separate no-tool contexts and no inherited business history',async()=>{
  const root=resolve('.grid-agent/runtime/pi/source/packages');
  const sdk=await import(pathToFileURL(resolve(root,'coding-agent/dist/index.js')).href);
  const ai=await import(pathToFileURL(resolve(root,'ai/dist/index.js')).href);
  const previous=process.cwd(),oldAgent=process.env.PI_CODING_AGENT_DIR;
  const cwd=await mkdtemp(resolve(tmpdir(),'pooled-context-'));const owned=[];
  const model={id:'offline',name:'Offline',provider:'capstone-general',api:'openai-completions',baseUrl:'http://127.0.0.1:1',reasoning:false,input:['text'],contextWindow:32000,maxTokens:1024,cost:{input:0,output:0,cacheRead:0,cacheWrite:0}};
  const contexts=[];
  const runtime={getModel:()=>model,hasConfiguredAuth:()=>true,getAuth:async()=>({auth:{apiKey:'offline'}}),isUsingOAuth:()=>false,
    streamSimple(_model,context){
      contexts.push(context);assert.equal(context.tools?.length??0,0);assert.doesNotMatch(JSON.stringify(context),/PARENT_PRIVATE_HISTORY/);
      const message={role:'assistant',content:[{type:'text',text:'Observed analysis'}],api:model.api,provider:model.provider,model:model.id,timestamp:Date.now(),stopReason:'stop',usage:{input:1,output:1,cacheRead:0,cacheWrite:0,totalTokens:2,cost:{input:0,output:0,cacheRead:0,cacheWrite:0,total:0}}};
      const stream=ai.createAssistantMessageEventStream();stream.push({type:'done',reason:'stop',message});stream.end();return stream;
    }};
  try{
    process.chdir(cwd);process.env.PI_CODING_AGENT_DIR=resolve(cwd,'agent');await mkdir(process.env.PI_CODING_AGENT_DIR);
    const config={model:'offline',settings:{packages:[],extensions:[],skills:[]},extensions:[],allowedSkills:[],contextFiles:[{path:'history',content:'PARENT_PRIVATE_HISTORY'}],appendSystemPrompt:['PARENT_PRIVATE_HISTORY'],applicationPolicy:{allowed_tools:['bash','agent_llm_submit']}};
    for(const id of ['one','two']){const path=resolve(cwd,id);await mkdir(path);owned.push(await createPooledAnalysisSession(config,sdk,runtime,{cwd:path}))}
    assert.equal(owned[0].session.settingsManager.getRetrySettings().enabled,false);
    await Promise.all(owned.map((child,i)=>child.session.prompt('Analyze explicitly supplied observations '+i)));
    assert.equal(contexts.length,2);assert.notEqual(owned[0].session,owned[1].session);
  }finally{await Promise.all(owned.map(child=>child.close()));process.chdir(previous);if(oldAgent===undefined)delete process.env.PI_CODING_AGENT_DIR;else process.env.PI_CODING_AGENT_DIR=oldAgent;await rm(cwd,{recursive:true,force:true})}
});
