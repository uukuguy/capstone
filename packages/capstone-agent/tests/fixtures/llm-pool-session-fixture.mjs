import assert from 'node:assert/strict';
import {mkdtemp,mkdir,rm} from 'node:fs/promises';
import {resolve} from 'node:path';
import {tmpdir} from 'node:os';
import {pathToFileURL} from 'node:url';
import {readFileSync} from 'node:fs';
import {runManagedSession} from '../../src/capstone_agent/resources/general-sdk.mjs';

const root=resolve('.grid-agent/runtime/pi/source/packages');
const sdk=await import(pathToFileURL(resolve(root,'coding-agent/dist/index.js')).href);
const ai=await import(pathToFileURL(resolve(root,'ai/dist/index.js')).href);
const policy=JSON.parse(readFileSync(new URL('../../src/capstone_agent/resources/llm-call-pool-policy.json',import.meta.url),'utf8'));
const requestPolicy=JSON.parse(readFileSync(new URL('../../src/capstone_agent/resources/model-request-pool-policy.json',import.meta.url),'utf8'));
const model={id:'offline',name:'Offline',provider:'capstone-general',api:'openai-completions',baseUrl:'http://127.0.0.1:1',reasoning:false,input:['text'],contextWindow:32000,maxTokens:1024,cost:{input:0,output:0,cacheRead:0,cacheWrite:0}};
let parents=0,children=0,active=0,maximum=0;
const runtime={getModel:()=>model,hasConfiguredAuth:()=>true,getAuth:async()=>({auth:{apiKey:'offline'}}),isUsingOAuth:()=>false,
  streamSimple(_model,context){
    const child=context.systemPrompt.includes('Analyze only the explicit supplied observations');
    const stream=ai.createAssistantMessageEventStream();let content,stopReason='stop';
    if(child){children++;active++;maximum=Math.max(maximum,active);assert.equal(context.tools?.length??0,0);content=[{type:'text',text:'Independent observed answer'}]}
    else{
      parents++;
      if(parents===1){content=[{type:'toolCall',id:'submit',name:'agent_llm_submit',arguments:{calls:[{id:'甲',instruction:'Analyze first observation',input:'one'},{id:'乙',instruction:'Analyze second observation',input:'two'}]}}];stopReason='toolUse'}
      else if(parents===2||(()=>{
        const last=context.messages.filter(message=>message.role==='toolResult'&&message.toolName==='agent_llm_collect').at(-1);
        const body=last?JSON.parse(last.content.find(part=>part.type==='text').text):null;
        return body?.pool.jobs.some(job=>!['completed','failed','cancelled','blocked'].includes(job.status));
      })()){assert.ok(parents<6);content=[{type:'toolCall',id:'collect-'+parents,name:'agent_llm_collect',arguments:{wait_ms:1000}}];stopReason='toolUse'}
      else{assert.match(JSON.stringify(context.messages),/Independent observed answer/);content=[{type:'text',text:'Integrated actual parallel observations.'}]}
    }
    const finish=()=>{
      if(child)active--;
      const message={role:'assistant',content,api:model.api,provider:model.provider,model:model.id,timestamp:Date.now(),stopReason,usage:{input:1,output:1,cacheRead:0,cacheWrite:0,totalTokens:2,cost:{input:0,output:0,cacheRead:0,cacheWrite:0,total:0}}};
      stream.push({type:'done',reason:stopReason,message});stream.end();
    };
    if(child)setTimeout(finish,30);else queueMicrotask(finish);return stream;
  }};
const cwd=await mkdtemp(resolve(tmpdir(),'llm-pool-session-'));const previous=process.cwd();
try{
  process.chdir(cwd);process.env.PI_CODING_AGENT_DIR=resolve(cwd,'agent');await mkdir(process.env.PI_CODING_AGENT_DIR);
  await runManagedSession({model:'offline',settings:{packages:[],extensions:[],skills:[],retry:{enabled:false}},extensions:[],allowedSkills:[],contextFiles:[],
    input:{kind:'text',text:'Analyze two independent observations.'},systemPrompt:'Use explicit independent analysis and integrate actual results.',
    applicationPolicy:{allowed_tools:['agent_llm_submit','agent_llm_collect','agent_llm_cancel']},llmCallPool:policy,modelRequestPool:requestPolicy,researchRuntime:{deepResearch:false}},sdk,runtime);
  assert.ok(parents>=3&&parents<=5);assert.equal(children,2);assert.equal(maximum,2);
}finally{process.chdir(previous);await rm(cwd,{recursive:true,force:true})}
