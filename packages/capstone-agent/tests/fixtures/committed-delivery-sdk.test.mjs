import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join,resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {configureCommittedDelivery,finalizeCommittedDelivery} from '../../src/capstone_agent/resources/committed-delivery.mjs';
import {runSettledPrompt} from '../../src/capstone_agent/resources/general-sdk.mjs';

test('pinned SDK stops after persisted finish without requesting another model response',{timeout:15000},async()=>{
  const root=resolve('.grid-agent/runtime/pi/source/packages');
  const sdk=await import(pathToFileURL(join(root,'coding-agent/dist/index.js')).href);
  const ai=await import(pathToFileURL(join(root,'ai/dist/index.js')).href);
  const cwd=await mkdtemp(join(tmpdir(),'dr-direct-sdk-'));
  const delivery={outcome:'limited',summary:'报告已保存，保留数据覆盖缺口。',delivery_result_refs:['result:one'],delivery_product_refs:['artifact:one'],limitations:['覆盖缺口']};
  let requests=0,guard,session;
  const model={id:'offline-finish',name:'Offline finish',provider:'capstone-general',api:'openai-completions',baseUrl:'http://127.0.0.1:1',reasoning:false,input:['text'],contextWindow:32000,maxTokens:1024,cost:{input:0,output:0,cacheRead:0,cacheWrite:0}};
  const runtime={getModel:()=>model,hasConfiguredAuth:()=>true,getAuth:async()=>({auth:{apiKey:'offline-fixture'}}),isUsingOAuth:()=>false,
    streamSimple(){requests++;if(requests>1)throw Error('Redundant final model request');
      const message={role:'assistant',content:[{type:'toolCall',id:'finish-one',name:'agent_research_finish',arguments:{}}],api:model.api,provider:model.provider,model:model.id,timestamp:Date.now(),usage:{input:4,output:2,cacheRead:0,cacheWrite:0,totalTokens:6,cost:{input:0,output:0,cacheRead:0,cacheWrite:0,total:0}},stopReason:'toolUse'};
      const stream=ai.createAssistantMessageEventStream();stream.push({type:'done',reason:'toolUse',message});stream.end();return stream;}};
  try{
    const settingsManager=sdk.SettingsManager.inMemory({packages:[],extensions:[],skills:[],compaction:{enabled:false}});
    const resourceLoader=new sdk.DefaultResourceLoader({cwd,agentDir:cwd,settingsManager,noContextFiles:true,noThemes:true,extensionFactories:[pi=>{
      guard=configureCommittedDelivery(pi,{readState:async()=>({delivery})});
    }]});
    await resourceLoader.reload();
    const customTools=[{name:'agent_research_finish',label:'Finish',description:'Commit delivery',parameters:{type:'object',properties:{}},execute:async()=>finalizeCommittedDelivery({content:[{type:'text',text:'Committed'}],details:{ok:true,result:{delivery}}})}];
    ({session}=await sdk.createAgentSession({cwd,agentDir:cwd,model,modelRuntime:runtime,settingsManager,resourceLoader,tools:['agent_research_finish'],customTools,sessionManager:sdk.SessionManager.inMemory()}));
    await session.bindExtensions({onError:error=>{throw error;}});session.setActiveToolsByName(['agent_research_finish']);
    const events=[];
    await runSettledPrompt(session,{kind:'text',text:'Save delivery'},null,event=>events.push(event),undefined,{delivery:()=>guard.delivery()});
    assert.equal(requests,1,JSON.stringify(events.filter(event=>event.type==='tool_execution_end')));assert.deepEqual(events.at(-1).committed_delivery,delivery);
    assert.ok(events.at(-1).messages.every(item=>!['error','aborted'].includes(item.stopReason)));
  }finally{session?.dispose();await rm(cwd,{recursive:true,force:true});}
});
