import test from 'node:test';
import assert from 'node:assert/strict';
import {configureGeneralMcp} from '../../src/capstone_agent/resources/general-mcp.mjs';
import {createEnterpriseResearchController} from '../../src/capstone_agent/resources/enterprise-research-runtime.mjs';
test('published MCP work follows the same committed plan and actual receipt boundary',async()=>{
 let state=null,revision=0,cycle,mcp,calls=0;const config={researchTaskId:'task',researchAttemptId:'attempt',researchOwner:{thread_id:'thread',work_id:'work',research_id:'research',goal_revision:1},
  researchRuntime:{enabled:true},applicationPolicy:{allowed_tools:['lookup','agent_research_cycle']},mcp:{descriptor:{tool_schemas:{lookup:{inputSchema:{type:'object',properties:{}},description:'Authorized lookup'}}}}};
 const controller=createEnterpriseResearchController({config,readResearch:async()=>({research_revision:revision,state}),inspectProducts:async()=>({products:[],ready:true}),
  commitResearch:async(_id,request)=>{revision++;state={...state,...request.changes,notes:[...(state?.notes??[]),...request.changes.notes]};return {details:{ok:true,result:{status:'committed',receipt:{research_revision:revision}}}};}});
 controller.register({on(){},registerTool:t=>{cycle=t;}});
 await configureGeneralMcp({on(){},registerTool:t=>{mcp=t;}},config,{research:()=>controller,bridge:{async call(){calls++;return {result_json:'actual source',observation:{},is_error:false};}}});
 await assert.rejects(mcp.execute('before-plan',{}),/plan/i);assert.equal(calls,0);
 const initial=await cycle.execute('plan',{operation:'plan',goal:'Read authorized source',output_mode:'text',source_refs:[],objectives:[{id:'read',purpose:'Read source',questions:['What is available?'],depends_on:[],expected_outputs:['answer'],checks:[],mode:'execute',input_refs:[],resolves:[]}]});
 await mcp.execute('after-plan',{});assert.equal(calls,1);
 const recorded=await cycle.execute('record',{operation:'record',action_id:initial.details.result.pending_action.id,outcome:'completed',findings:[],product_refs:[],limitations:[]});
 assert.equal(recorded.details.ok,true);assert.equal(recorded.details.result.execution_receipts[0].status,'completed');
});
