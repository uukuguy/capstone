// Actual runtime progress and inspection bindings for the Python host guard.
import assert from 'node:assert/strict';
import {createEnterpriseGraphController} from '../../src/capstone_agent/resources/enterprise-graph-runtime.mjs';
const owner={thread_id:'binding-thread',work_id:'binding-work',research_id:'binding-research',goal_revision:1};
const config={researchTaskId:'binding-task',researchAttemptId:'binding-attempt',researchOwner:owner,researchSources:[],
  researchRuntime:{delegation:{concurrency:1},graphLimits:{maxNodes:8,maxItems:32,maxText:2048,maxExecutions:16,snapshotBytes:200000,publicBytes:50000}}};
let view={research_revision:0,state:null},action,release;
const timeline=[],proposal=new Promise(resolve=>{release=resolve;});
const ports={config,readResearch:async()=>structuredClone(view),
  commitResearch:async(_id,request)=>{assert.equal(request.expected_revision,view.research_revision);
    view={research_revision:view.research_revision+1,state:{...request.changes,notes:[...(view.state?.notes??[]),...request.changes.notes]}};
    return {details:{ok:true,result:{status:'committed',receipt:{research_revision:view.research_revision}}}};},
  inspectProducts:async({products})=>({ready:true,products}),resolveInputs:async()=>({manifests:[],handles:[]}),
  dispatchNode:async request=>{action=request.action;return proposal;},onProgress:value=>timeline.push({kind:'progress',value})};
const controller=createEnterpriseGraphController(ports);
const node={id:'A',purpose:'Retained observation',questions:['What was returned?'],checks:['Inspect actual observation'],depends_on:[],
  expected_outputs:['Observation'],mode:'execute',execution:'delegated',instruction:'Return an actual fixture observation',source_refs:[],
  outputs:[{slot:'finding',kind:'observation',description:'Retained finding'}],inputs:[]};
assert.equal((await controller.execute('plan','plan',{goal:'Inspect retained output',output_mode:'text',source_refs:[],nodes:[node]})).details.ok,true);
release({status:'completed',receipts:[{ref:'fixture-observation',owner,attempt_id:config.researchAttemptId,action_id:action.id,status:'completed'}],products:[],output:'Actual fixture observation'});
for(let i=0;i<100;i++){
  if((await controller.readState()).graph.nodes[0].phase==='executed')break;
  await new Promise(resolve=>setImmediate(resolve));
}
async function inspect(stage,current){
  const revision=view.research_revision;
  const reply=await current.readReference(stage,{section:'reference',action_id:action.id},{onBinding:token=>timeline.push({kind:'binding',stage,value:{
    type:'enterprise_graph_tool_binding',owner:token.action.owner,attempt_id:token.action.attempt_id,task_id:config.researchTaskId,
    action_id:token.action.id,step_id:token.action.step_id,checkpoint:token.checkpoint,tool_call_id:stage,tool_name:'agent_research_read'}})});
  assert.equal(reply.details.ok,true,JSON.stringify(reply));assert.equal(view.research_revision,revision);
}
await inspect('before-record',controller);
assert.equal((await controller.execute('record','record',{action_id:action.id,outcome:'completed',outputs:[{slot:'finding',observation_refs:['fixture-observation'],
  artifact_refs:[],summary:'Actual fixture observation',scope:'Retained output'}],limitations:[]})).details.ok,true);
await inspect('after-record',controller);await controller.continuationState();await inspect('after-continuation',controller);
const state=await controller.readState();assert.equal((await controller.execute('assess','assess',{action_id:state.graph.nodes[0].assess_action_id,outcome:'success',
  checks:[{description:'Inspect actual observation',status:'passed',refs:['fixture-observation'],explanation:'Actual retained observation'}],summary:'Accepted'})).details.ok,true);
await inspect('after-assess',controller);
const restored=createEnterpriseGraphController(ports);await restored.readState();await inspect('after-restore',restored);
await restored.close();await controller.close();process.stdout.write(JSON.stringify({timeline,view,owner,attempt_id:config.researchAttemptId,task_id:config.researchTaskId}));
