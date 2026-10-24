// Actual pinned SDK and graph child wrappers; deterministic provider, HTTP host relay.
import assert from 'node:assert/strict';
import {mkdir} from 'node:fs/promises';
import {createInterface} from 'node:readline';
import {join,resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {createManagedChildSession} from '../../src/capstone_agent/resources/general-sdk.mjs';
const lines=createInterface({input:process.stdin});
const setup=await new Promise(done=>lines.once('line',line=>done(JSON.parse(line))));lines.close();
const root=resolve('.grid-agent/runtime/pi/source/packages');
const sdk=await import(pathToFileURL(join(root,'coding-agent/dist/index.js')).href);
const ai=await import(pathToFileURL(join(root,'ai/dist/index.js')).href);
process.chdir(setup.workspace);
process.env.PI_CODING_AGENT_DIR=join(setup.workspace,'.pi');await mkdir(process.env.PI_CODING_AGENT_DIR);
const owner={thread_id:'thread',work_id:'work',research_id:'research',goal_revision:1};
const action={id:'action-gateway',step_id:'gateway',owner,attempt_id:'attempt-1',definition_ref:'definition',
 execution_revision:1,input_bindings:[],source_refs:[],source_versions:[]};
const name='data_gateway_discover_data_capabilities',events=[],receipts=[];
const config={researchTaskId:'task-1',model:'fixture',extensions:[],allowedSkills:[],
 contextFiles:[{path:'registered-production-data',content:'Use application-authorized data_gateway_ tools for production data.'}],
 settings:{compaction:{enabled:false},packages:[],extensions:[],skills:[]},deadlineAt:Date.now()+15000,
 applicationPolicy:{allowed_tools:[name]},researchRuntime:{},dataGateway:setup.gateway};
const model={id:'fixture',name:'Fixture',provider:'capstone-general',api:'openai-completions',
 baseUrl:'http://127.0.0.1:1',reasoning:false,input:['text'],contextWindow:32000,maxTokens:1024,
 cost:{input:0,output:0,cacheRead:0,cacheWrite:0}};
let turns=0;
const runtime={getModel:()=>model,hasConfiguredAuth:()=>true,getAuth:async()=>({auth:{apiKey:'fixture'}}),isUsingOAuth:()=>false,
 streamSimple(_model,context){
  const first=turns++===0;
  if(!first){const result=context.messages.find(x=>x.role==='toolResult');assert.ok(result&&!result.isError);}
  const message={role:'assistant',content:first?[{type:'toolCall',id:'lookup-call',name,arguments:{}}]:[{type:'text',text:'Observed partial data.'}],
   stopReason:first?'toolUse':'stop',api:model.api,provider:model.provider,model:model.id,timestamp:0,
   usage:{input:2,output:3,totalTokens:5,cost:{total:0}}};
  const stream=ai.createAssistantMessageEventStream();stream.push({type:'done',reason:message.stopReason,message});stream.end();return stream;
 }};
const child=await createManagedChildSession(config,sdk,runtime,{cwd:setup.workspace,toolNames:[name],researchExecution:true,
 graphBinding:{action,checkpoint:{ref:'checkpoint',revision:1},emit:e=>events.push(e),receipts}});
try{
 assert.deepEqual(child.session.getActiveToolNames(),[name]);
 assert.match(child.session.systemPrompt,/application-authorized data_gateway_ tools/);
 await child.session.prompt('Discover the authorized data capabilities.');
 const end=events.find(e=>e.type==='enterprise_graph_child_tool'&&e.activity==='end');
 assert.ok(end&&!end.is_error);assert.equal(receipts.length,1);assert.equal(receipts[0].status,'completed');
 assert.equal(end.result.details.tool_call_id,end.tool_call_id);
 process.stdout.write(JSON.stringify({turns,event:end,receipt:receipts[0]})+'\n');
}finally{await child.close();}
