import {test} from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,mkdir,writeFile,rm} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {createGraphContextClient} from '../../src/capstone_agent/resources/graph-context-client.mjs';
const module=await import('../../src/capstone_agent/resources/enterprise-graph-runtime.mjs').catch(error=>{
  if(error.code==='ERR_MODULE_NOT_FOUND')return {};throw error;
});
const {createEnterpriseGraphController}=module;
const owner={thread_id:'thread',work_id:'work',research_id:'research',goal_revision:1};
const limits={maxNodes:32,maxItems:64,maxText:4096,maxExecutions:64,snapshotBytes:900000,publicBytes:200000,resultBytes:50000};
const node=(id,extra={})=>({id,purpose:'Purpose '+id,questions:['Question '+id],checks:['Verify '+id],depends_on:[],
  expected_outputs:['Actual output'],mode:'execute',execution:'delegated',instruction:'Inspect '+id,
  source_refs:[],outputs:[{slot:'value',kind:'observation',description:'Actual observation'}],inputs:[],...extra});
const graph=()=>[node('A'),node('B'),node('C',{depends_on:['A'],mode:'synthesis',inputs:[{name:'prior',from:{step_id:'A',slot:'value'}}]}),node('D',{depends_on:['A','B']})];
const plan=nodes=>({goal:'Answer the requested task',output_mode:'text',nodes,source_refs:[]});
const defer=()=>{let resolve;const promise=new Promise(done=>{resolve=done;});return {promise,resolve};};
async function tick(){await new Promise(resolve=>setImmediate(resolve));}
function fixture(extra={}){
  let view={research_revision:0,state:null},rejectNext=false,loseNext=false,loseCommand,held,loseReplays=false;
  const requests=[],events=[],calls=[],gates=new Map(),seen=new Map();
  const config={researchTaskId:'task',researchOwner:owner,researchAttemptId:'attempt',researchSources:[],researchRuntime:{graphLimits:limits,delegation:{concurrency:2}},...extra.config};
  const ports={config,readResearch:async()=>structuredClone(view),
    commitResearch:async(id,request)=>{
      requests.push({id,request:structuredClone(request)});
      if(rejectNext){rejectNext=false;return {details:{ok:false,result:{status:'rejected',code:'rejected'}}};}
      if(seen.has(id)){
        assert.deepEqual(request,seen.get(id).request);
        if(held){const gate=held;held=undefined;gate.entered.resolve();await gate.release.promise;}
        return loseReplays?{details:{ok:false}}:seen.get(id).ack;
      }
      assert.equal(request.expected_revision,view.research_revision);
      view={research_revision:view.research_revision+1,state:{...(view.state??{}),...request.changes,notes:[...(view.state?.notes??[]),...request.changes.notes]}};
      const ack={details:{ok:true,result:{status:'committed',receipt:{research_revision:view.research_revision}}}};
      seen.set(id,{request:structuredClone(request),ack});
      if(held){const gate=held;held=undefined;gate.entered.resolve();await gate.release.promise;}
      if(loseNext||JSON.parse(request.changes.notes.at(-1).text).command_id===loseCommand){loseNext=false;loseCommand=undefined;return {details:{ok:false}};}return ack;
    },inspectProducts:async({products})=>({ready:true,products}),onProgress:event=>events.push(event),
    resolveInputs:async action=>({manifests:action.input_bindings.map(binding=>{
      for(const note of [...view.state.notes].reverse()){
        const manifest=JSON.parse(note.text).snapshot.results.find(item=>item.result_ref===binding.result_ref);
        if(manifest)return manifest;
      }
      throw Error('Missing exact manifest');
    }),handles:action.input_bindings.map(binding=>({result_ref:binding.result_ref,ref:'handle-'+binding.name,immutable:true,read_only:true}))}),
    dispatchNode:async(request,{signal,validateProposal})=>{calls.push({...request,validateProposal});const gate=defer();gates.set(request.node.id,gate);
      signal.addEventListener('abort',()=>gate.resolve({status:'cancelled',receipts:[],products:[],output:''}),{once:true});return gate.promise;},...extra.ports};
  const controller=createEnterpriseGraphController(ports);
  const settle=async(id,status='completed',output='Child output',products=[],handoff)=>{
    const call=calls.filter(item=>item.node.id===id).at(-1),action=call.action;
    gates.get(id).resolve({status,receipts:[{ref:'obs-'+id,owner,attempt_id:'attempt',action_id:action.id,status}],products,output,...(handoff?{handoff}:{})});
    await tick();await controller.readState();
  };
  return {controller,ports,calls,events,requests,settle,get view(){return structuredClone(view);},reject(){rejectNext=true;},lose(){loseNext=true;},
    hold(){held={entered:defer(),release:defer()};return held;},loseCommand(value){loseCommand=value;},loseReplays(value){loseReplays=value;}};
}
const record=action_id=>({action_id,outcome:'completed',outputs:[{slot:'value',observation_refs:[],artifact_refs:[],summary:'Actual result',scope:'Observed inputs'}],limitations:[]});
const registered=controller=>{const tools=[];controller.register({registerTool:tool=>tools.push(tool)});return Object.fromEntries(tools.map(tool=>[tool.name,tool]));};
test('adaptive loop permits several direct cycles then locks native work after Deep Research activation',async()=>{
  const ref='native-observation:task:observed',source={ref,revision:'sha256:'+'a'.repeat(64)};
  const selected=[];
  const f=fixture({config:{researchRuntime:{graphLimits:limits,delegation:{concurrency:1},
    isolatedTaskExecution:true,lightweightTaskNodes:true,adaptiveAgentLoop:true}},
    ports:{prepareSources:async refs=>{selected.push(refs);return [source];}}});
  try{
    for(let i=0;i<3;i++){
      assert.equal(await f.controller.beginTool({toolCallId:'direct-'+i,toolName:'read'}),null);
      assert.equal(await f.controller.continuationState(),null);
    }
    assert.equal(f.requests.length,0,'Direct cycles must not create research checkpoints');
    const result=await f.controller.execute('plan','escalate',plan([node('A',{source_refs:[ref]})]));
    assert.equal(result.details.ok,true);
    assert.deepEqual(selected,[[ref]]);
    assert.deepEqual(f.calls[0].action.source_versions,[source]);
    await assert.rejects(f.controller.beginTool({toolCallId:'after-plan',toolName:'read'}),/independent task/);
    await f.settle('A');
    const restoredSelections=[];
    const restored=createEnterpriseGraphController({...f.ports,prepareSources:async refs=>{
      restoredSelections.push(refs);return [source];
    }});
    try{
      await restored.readState();assert.deepEqual(restoredSelections,[[ref]]);
      const revised=await restored.execute('revise','more',{
        nodes:[node('B',{source_refs:[ref]})],reason:'Additional independent question',rerun:[]});
      assert.equal(revised.details.ok,true);
      assert.deepEqual(f.calls.at(-1).action.source_versions,[source]);
    }finally{await restored.close({reason:'Done'});}
  }finally{await f.controller.close({reason:'Done'});}
});
test('failed source promotion does not admit a Deep Research plan',async()=>{
  const f=fixture({config:{researchRuntime:{graphLimits:limits,delegation:{concurrency:1},
    isolatedTaskExecution:true,lightweightTaskNodes:true,adaptiveAgentLoop:true}},
    ports:{prepareSources:async()=>{throw new Error('Source persistence is not confirmed');}}});
  try{
    const result=await f.controller.execute('plan','escalate',plan([node('A',{source_refs:['native-observation:missing']})]));
    assert.equal(result.details.ok,false);assert.equal(f.calls.length,0);assert.equal(f.requests.length,0);
  }finally{await f.controller.close({reason:'Done'});}
});
test('lightweight scheduler starts synthesis from selected limited returns without a second acceptance form',async()=>{
  const f=fixture({config:{researchRuntime:{graphLimits:limits,delegation:{concurrency:1},isolatedTaskExecution:true,lightweightTaskNodes:true}}});
  try{
    assert.equal((await f.controller.execute('plan','plan',plan([node('A'),node('B',{mode:'synthesis',depends_on:['A'],
      inputs:[{name:'finding',from:{step_id:'A',slot:'value'}}]})]))).details.ok,true);
    await f.settle('A');const first=f.calls[0].action;
    const returned=record(first.id);returned.outputs[0].observation_refs=['obs-A'];returned.limitations=['No visual inspection'];
    assert.equal((await f.controller.execute('record','record',returned)).details.ok,true);
    const assessment=(await f.controller.readState()).graph.nodes.find(n=>n.id==='A').assess_action_id;
    assert.equal((await f.controller.execute('assess','assess',{action_id:assessment,outcome:'limited',
      checks:[{description:'Verify A',status:'not_run',refs:[],explanation:'Visual inspection remains open'}],summary:'Useful with a stated limitation'})).details.ok,true);
    assert.equal(f.calls[1].node.id,'B');
    assert.deepEqual(f.calls[1].action.input_bindings[0].accepted_limitations.record_limitations,['No visual inspection']);
    assert.equal((await f.controller.readState()).graph.nodes.find(n=>n.id==='A').phase,'limited');
  }finally{await f.controller.close({reason:'Done'});}
});
test('research success with unchecked findings records limited once and starts its consumer',async()=>{
  const f=fixture({config:{researchRuntime:{graphLimits:limits,delegation:{concurrency:1},isolatedTaskExecution:true,lightweightTaskNodes:true}}});
  try{
    assert.equal((await f.controller.execute('plan','plan',plan([node('A'),node('B',{depends_on:['A'],mode:'synthesis',
      inputs:[{name:'finding',from:{step_id:'A',slot:'value'}}]})]))).details.ok,true);
    await f.settle('A');const returned=record(f.calls[0].action.id);returned.outputs[0].observation_refs=['obs-A'];
    assert.equal((await f.controller.execute('record','record',returned)).details.ok,true);
    const action=(await f.controller.readState()).graph.nodes.find(n=>n.id==='A').assess_action_id;
    const request={action_id:action,outcome:'success',checks:[{description:'Verify A',status:'not_run',refs:[],
      explanation:'User review pending'}],summary:'Useful findings'};
    const reply=await f.controller.execute('assess','assess',request);
    assert.equal(reply.details.ok,true,JSON.stringify(reply));
    assert.equal((await f.controller.readState()).graph.nodes.find(n=>n.id==='A').phase,'limited');
    assert.equal(f.calls[1].node.id,'B');
    assert.equal(f.calls[1].action.input_bindings[0].accepted_limitations.unmet_checks[0].status,'not_run');
    assert.equal((await f.controller.execute('assess','assess',request)).details.ok,true);
    assert.equal(f.calls.length,2);
  }finally{await f.controller.close({reason:'Done'});}
});
test('research assessment relaxation retains legacy strictness and rejects invented evidence',async()=>{
  for(const lightweight of [false,true]){
    const f=fixture({config:{researchRuntime:{graphLimits:limits,delegation:{concurrency:1},isolatedTaskExecution:true,
      lightweightTaskNodes:lightweight}}});
    try{
      assert.equal((await f.controller.execute('plan','plan',plan([node('A')]))).details.ok,true);
      await f.settle('A');const returned=record(f.calls[0].action.id);returned.outputs[0].observation_refs=['obs-A'];
      assert.equal((await f.controller.execute('record','record',returned)).details.ok,true);
      const action=(await f.controller.readState()).graph.nodes[0].assess_action_id;
      const request={action_id:action,outcome:'success',checks:[{description:'Verify A',status:'not_run',refs:[],
        explanation:'Not checked'}],summary:'Useful findings'};
      if(!lightweight)assert.equal((await f.controller.execute('assess','strict',request)).details.ok,false);
      request.checks.push({description:'Unknown check',status:'passed',refs:['invented-observation'],explanation:'Unsupported'});
      assert.equal((await f.controller.execute('assess','invented',request)).details.ok,false);
      assert.equal((await f.controller.readState()).graph.nodes[0].phase,'recorded');
    }finally{await f.controller.close({reason:'Done'});}
  }
});
test('lightweight return records and assesses in one submission without hiding unmet checks',async()=>{
  const f=fixture({config:{researchRuntime:{graphLimits:limits,delegation:{concurrency:1},isolatedTaskExecution:true,lightweightTaskNodes:true}}});
  try{
    await f.controller.execute('plan','plan',plan([node('A'),node('B',{depends_on:['A'],mode:'synthesis',
      inputs:[{name:'finding',from:{step_id:'A',slot:'value'}}]})]));
    await f.settle('A');const returned=record(f.calls[0].action.id);returned.outputs[0].observation_refs=['obs-A'];
    returned.assessment={outcome:'success',summary:'Useful returned findings',checks:[
      {description:'Verify A',status:'not_run',refs:[],explanation:'Review remains open'}]};
    const reply=await f.controller.execute('record','combined',returned);
    assert.equal(reply.details.ok,true,JSON.stringify(reply));
    assert.equal((await f.controller.readState()).graph.nodes[0].phase,'limited');
    assert.equal(f.calls[1].node.id,'B');
    assert.equal(f.calls[1].action.input_bindings[0].accepted_limitations.unmet_checks[0].status,'not_run');
    const saved=JSON.parse(f.view.state.notes.at(-1).text).snapshot.executions[0];
    assert.equal(saved.record.outcome,'completed');assert.equal(saved.assessment.outcome,'limited');
    assert.deepEqual(await f.controller.execute('record','combined',returned),reply);
    assert.equal(f.calls.length,2);
    assert.ok(registered(f.controller).agent_research_record.parameters.properties.assessment);
  }finally{await f.controller.close({reason:'Done'});}
});
test('combined return rejects malformed assessment before recording, and preserves a valid record on assessment errors',async()=>{
  const f=fixture({config:{researchRuntime:{graphLimits:limits,delegation:{concurrency:1},isolatedTaskExecution:true,lightweightTaskNodes:true}}});
  try{
    await f.controller.execute('plan','plan',plan([node('A')]));await f.settle('A');
    const returned=record(f.calls[0].action.id);returned.outputs[0].observation_refs=['obs-A'];
    returned.assessment={outcome:'success',summary:'Claim',extra:'invalid'};
    assert.equal((await f.controller.execute('record','invalid',returned)).details.ok,false);
    assert.equal((await f.controller.readState()).graph.nodes[0].phase,'executed');
    returned.assessment={outcome:'limited',summary:'Claim',checks:[{description:'Verify A',status:'passed',refs:['invented'],explanation:'Unsupported'}]};
    const reply=await f.controller.execute('record','bad-evidence',returned);
    assert.equal(reply.details.ok,false);assert.ok(reply.details.recorded);
    assert.equal((await f.controller.readState()).graph.nodes[0].phase,'recorded');
  }finally{await f.controller.close({reason:'Done'});}
});
test('combined return adopts exact producer checks and leaves the strict legacy contract unchanged',async()=>{
  for(const lightweight of [true,false]){
    const f=fixture({config:{researchRuntime:{graphLimits:limits,delegation:{concurrency:1},
      isolatedTaskExecution:true,lightweightTaskNodes:lightweight}}});
    try{
      await f.controller.execute('plan','plan',plan([node('A')]));const action=f.calls[0].action;
      const handoff={schema:'capstone-node-proposal/1',binding:{action_id:action.id,definition_ref:action.definition_ref,
        execution_revision:action.execution_revision,consumed_results:[],source_versions:[]},
        outputs:[{slot:'value',artifact_refs:[],observation_refs:['obs-A'],summary:'Actual finding',scope:'Assigned source'}],
        checks:[{description:'Verify A',status:'not_run',refs:[],explanation:'Not required for draft'}],limitations:[]};
      await f.settle('A','completed','Actual finding',[],handoff);
      const proposal=(await f.controller.readState()).pending_proposals[0].proposal;
      const reply=await f.controller.execute('record','one-return',{action_id:action.id,proposal_ref:proposal.proposal_ref,
        outcome:'completed',limitations:[],assessment:{outcome:'success',summary:'Useful, review remains open'}});
      assert.equal(reply.details.ok,lightweight);
      assert.equal((await f.controller.readState()).graph.nodes[0].phase,lightweight?'limited':'executed');
      assert.equal(Boolean(registered(f.controller).agent_research_record.parameters.properties.assessment),lightweight);
    }finally{await f.controller.close({reason:'Done'});}
  }
});
test('expired draft advice still schedules needed work and is visible to parent and child',async()=>{
  const original=Date.now;let clock=100000;Date.now=()=>clock;
  const f=fixture({config:{researchRuntime:{graphLimits:limits,delegation:{concurrency:1},isolatedTaskExecution:true,
    lightweightTaskNodes:true,turnGuidance:{mode:'usable_draft',target_seconds:240,integration_reserve_seconds:60}}}});
  try{
    await f.controller.execute('plan','plan',plan([node('A'),node('B',{depends_on:['A'],mode:'synthesis',
      inputs:[{name:'finding',from:{step_id:'A',slot:'value'}}]})]));
    assert.equal(f.calls[0].turn_guidance.phase,'work');
    clock+=301000;await f.settle('A');
    const returned=record(f.calls[0].action.id);returned.outputs[0].observation_refs=['obs-A'];
    returned.assessment={outcome:'limited',summary:'Useful first answer',checks:[]};
    assert.equal((await f.controller.execute('record','accept',returned)).details.ok,true);
    assert.equal(f.calls[1].node.id,'B');assert.equal(f.calls[1].turn_guidance.phase,'deliver_available');
    assert.equal(f.calls[1].turn_guidance.started_at_ms,100000);
    const state=await f.controller.readState();
    assert.equal(state.turn_guidance.advisory_only,true);assert.equal(state.phase,'active');
    assert.equal(JSON.parse(f.view.state.notes.at(-1).text).turn_guidance_started_at_ms,100000);
  }finally{await f.controller.close({reason:'Done'});Date.now=original;}
});
test('combined return replay remains bound to its original execution after a revision',async()=>{
  const f=fixture({config:{researchRuntime:{graphLimits:limits,delegation:{concurrency:1},isolatedTaskExecution:true,lightweightTaskNodes:true}}});
  try{
    await f.controller.execute('plan','plan',plan([node('A')]));await f.settle('A');
    const returned=record(f.calls[0].action.id);returned.outputs[0].observation_refs=['obs-A'];
    returned.assessment={outcome:'limited',summary:'Initial findings',checks:[]};
    const accepted=await f.controller.execute('record','combined',returned);
    assert.equal(accepted.details.ok,true);
    const first=(await f.controller.readState()).graph.results[0].result_ref;
    const revised=await f.controller.execute('revise','revise',{nodes:[node('A')],reason:'New evidence requires correction',
      rerun:[{step_id:'A',reason:{kind:'discrepancy',refs:['obs-A']},supersedes:[first]}]});
    assert.equal(revised.details.ok,true,JSON.stringify(revised));
    assert.deepEqual(await f.controller.execute('record','combined',returned),accepted);
    assert.equal((await f.controller.readState()).graph.nodes[0].phase,'executing');
  }finally{await f.controller.close({reason:'Done'});}
});
test('unscheduled research checks are retained as notes without blocking a declared-check-free task',async()=>{
  const f=fixture({config:{researchRuntime:{graphLimits:limits,delegation:{concurrency:1},isolatedTaskExecution:true,lightweightTaskNodes:true}}});
  try{
    await f.controller.execute('plan','plan',plan([node('A',{checks:[]})]));await f.settle('A');
    const returned=record(f.calls[0].action.id);returned.outputs[0].observation_refs=['obs-A'];
    returned.assessment={outcome:'success',summary:'Useful finding',checks:[
      {description:'Extra consistency note',status:'passed',refs:['obs-A'],explanation:'Producer observation, not a declared check'}]};
    const reply=await f.controller.execute('record','accept-extra',returned);
    assert.equal(reply.details.ok,true,JSON.stringify(reply));
    const saved=JSON.parse(f.view.state.notes.at(-1).text);
    assert.deepEqual(saved.snapshot.executions[0].assessment.checks,[]);
    assert.equal(saved.commands.at(-1).reply.details.result.assessment_notes[0].description,'Extra consistency note');
    assert.equal((await f.controller.readState()).graph.nodes[0].phase,'success');
  }finally{await f.controller.close({reason:'Done'});}
});
test('incremental revision itself records a continue decision without a redundant review call',async()=>{
  const f=fixture({config:{researchRuntime:{graphLimits:limits,delegation:{concurrency:1},isolatedTaskExecution:true,
    lightweightTaskNodes:true,goalDrivenExecution:true}}});
  try{
    await f.controller.execute('plan','plan',{...plan([node('A',{checks:[]})]),
      requirements:[{id:'answer',kind:'finding',description:'Answer the whole user question'}]});
    await f.settle('A');const returned=record(f.calls[0].action.id);returned.outputs[0].observation_refs=['obs-A'];
    returned.assessment={outcome:'success',summary:'Discovery available',checks:[]};
    assert.equal((await f.controller.execute('record','accept',returned)).details.ok,true);
    const reply=await f.controller.execute('revise','next',{nodes:[node('B')],rerun:[],reason:'Observed discovery supports the next question'});
    assert.equal(reply.details.ok,true,JSON.stringify(reply));
    const state=await f.controller.readState();assert.equal(state.organization.review.decision,'continue');
    assert.equal(state.organization.review.requirements[0].status,'open');
    assert.equal(f.calls[1].node.id,'B');
  }finally{await f.controller.close({reason:'Done'});}
});
test('advisory continuation and published tools agree that node quality review is optional',async()=>{
  const f=fixture({config:{researchRuntime:{graphLimits:limits,delegation:{concurrency:1},isolatedTaskExecution:true,
    lightweightTaskNodes:true,nodeReviewMode:'advisory',goalDrivenExecution:true}}});
  try{
    await f.controller.execute('plan','plan',{...plan([node('A',{checks:[]})]),
      requirements:[{id:'answer',kind:'finding',description:'Answer the whole user question'}]});
    await f.settle('A');
    const instruction=JSON.parse((await f.controller.continuationState()).prompt).instruction;
    assert.doesNotMatch(instruction,/explicitly assess their quality/);
    assert.match(instruction,/no separate node assessment/);
    const tools=registered(f.controller);
    assert.deepEqual(Object.keys(tools.agent_research_assess.parameters.properties),['goal_review']);
    assert.deepEqual(tools.agent_research_assess.parameters.required,['goal_review']);
    assert.equal(tools.agent_research_record.parameters.properties.assessment,undefined);
    assert.match(tools.agent_research_record.description,/exactly one/);
    for(const name of ['agent_research_plan','agent_research_revise']){
      const fields=tools[name].parameters.properties.nodes.items.properties;
      assert.notEqual(fields.purpose,fields.instruction,'Per-field guidance must not share mutable schema objects');
      assert.match(tools[name].parameters.properties.nodes.items.properties.purpose.description,/cohesive/);
      assert.doesNotMatch(tools[name].parameters.properties.nodes.items.properties.purpose.description,/Separate independently answerable/);
    }
    assert.match(tools.agent_research_assess.description,/Omit all node-assessment fields/);
    assert.match(tools.agent_research_assess.description,/goal_review_ref/);
    assert.doesNotMatch(tools.agent_research_finish.description,/record and assess every node/);
  }finally{await f.controller.close({reason:'Done'});}
});
test('advisory goal review ignores unrelated node-review fields without adopting their claims',async()=>{
  const f=fixture({config:{researchRuntime:{graphLimits:limits,delegation:{concurrency:1},isolatedTaskExecution:true,
    lightweightTaskNodes:true,nodeReviewMode:'advisory',goalDrivenExecution:true}}});
  try{
    await f.controller.execute('plan','plan',{...plan([node('A',{checks:[]})]),
      requirements:[{id:'answer',kind:'finding',description:'Answer the whole user question'}]});
    await f.settle('A');const returned=record(f.calls[0].action.id);returned.outputs[0].observation_refs=['obs-A'];
    assert.equal((await f.controller.execute('record','accept',returned)).details.ok,true);
    const state=await f.controller.readState(),ref=state.graph.results[0].result_ref;
    const payload={goal_review:{decision:'limited',requirements:[{id:'answer',status:'satisfied',result_refs:[ref],explanation:'Actual retained finding'}],summary:'Useful research finding'},
      action_id:'unrelated-action',outcome:'failure',checks:[],summary:'An unrelated node review'};
    const reply=await f.controller.execute('assess','review',payload);
    assert.equal(reply.details.ok,true,JSON.stringify(reply));
    assert.equal(reply.details.result.organization.review.decision,'limited');
    assert.equal((await f.controller.readState()).graph.nodes[0].phase,'success');
    assert.deepEqual(await f.controller.execute('assess','review',payload),reply);
    const bad={...payload,goal_review:{...payload.goal_review,requirements:[{id:'answer',status:'satisfied',result_refs:['unadmitted'],explanation:'Not admitted'}]}};
    assert.equal((await f.controller.execute('assess','foreign',bad)).details.ok,false);
  }finally{await f.controller.close({reason:'Done'});}
});
for(const review of ['advisory','strict'])for(const checkStatus of ['passed','not_run'])for(const lostReceipt of [false,true])test(`validated ${review} return with ${checkStatus} checks ${review==='advisory'?'dispatches dependents without planner registration':'retains explicit review'}; lost receipt=${lostReceipt}`,async()=>{
  const f=fixture({config:{researchRuntime:{graphLimits:limits,delegation:{concurrency:1},isolatedTaskExecution:true,
    lightweightTaskNodes:true,nodeReviewMode:review}}});
  try{
    await f.controller.execute('plan','plan',plan([node('A'),node('B',{depends_on:['A'],mode:'synthesis',
      inputs:[{name:'finding',from:{step_id:'A',slot:'value'}}]})]));
    const action=f.calls[0].action;
    const handoff={schema:'capstone-node-proposal/1',binding:{action_id:action.id,definition_ref:action.definition_ref,
      execution_revision:action.execution_revision,consumed_results:[],source_versions:[]},
      outputs:[{slot:'value',artifact_refs:[],observation_refs:['obs-A'],summary:'Actual finding',scope:'Simulated data'}],
      checks:[{description:'Verify A',status:checkStatus,refs:checkStatus==='passed'?['obs-A']:[],explanation:'Producer check'}],
      limitations:checkStatus==='not_run'?['Independent check not run']:[]};
    const before=f.requests.length;
    if(lostReceipt)f.lose();
    await f.settle('A','completed','Actual finding',[],handoff);await tick();
    if(lostReceipt){
      assert.equal((await f.controller.readState()).update_pending,true);
      await f.controller.recoverPending();await tick();
      assert.equal(f.calls.filter(call=>call.node.id==='A').length,1,'Receipt recovery must not repeat native work');
    }
    const state=await f.controller.readState();
    if(review==='strict'){
      assert.equal(state.graph.nodes[0].phase,'executed');assert.equal(f.calls.length,1);
    }else{
      assert.equal(state.graph.nodes[0].phase,checkStatus==='passed'?'success':'limited');
      assert.equal(f.calls[1]?.node.id,'B');
      assert.deepEqual(state.graph.results[0].observation_refs,['obs-A']);
      assert.equal(state.pending_proposals.some(item=>item.step_id==='A'),false);
      assert.equal(f.requests.length-before,lostReceipt?3:2,'One atomic return checkpoint, exact recovery if needed, and one dependent start');
    }
  }finally{await f.controller.close({reason:'Done'});}
});
test('advisory automatic registration cannot admit a foreign observation',async()=>{
  const f=fixture({config:{researchRuntime:{graphLimits:limits,delegation:{concurrency:1},isolatedTaskExecution:true,
    lightweightTaskNodes:true,nodeReviewMode:'advisory'}}});
  try{
    await f.controller.execute('plan','plan',plan([node('A',{checks:[]})]));const action=f.calls[0].action;
    await f.settle('A','completed','Unverified finding',[],{schema:'capstone-node-proposal/1',
      binding:{action_id:action.id,definition_ref:action.definition_ref,execution_revision:action.execution_revision,consumed_results:[],source_versions:[]},
      outputs:[{slot:'value',artifact_refs:[],observation_refs:['foreign'],summary:'Unsupported',scope:'Unknown'}],checks:[],limitations:[]});
    const state=await f.controller.readState();assert.equal(state.graph.nodes[0].phase,'executed');
    assert.equal(state.graph.results.length,0);assert.equal(state.pending_proposals[0].proposal.status,'rejected');
  }finally{await f.controller.close({reason:'Done'});}
});
test('advisory mode automatically settles returned work and never treats parent review as a node gate',async()=>{
  const f=fixture({config:{researchRuntime:{graphLimits:limits,delegation:{concurrency:1},isolatedTaskExecution:true,
    lightweightTaskNodes:true,nodeReviewMode:'advisory'}}});
  try{
    await f.controller.execute('plan','plan',plan([node('A'),node('B',{depends_on:['A'],mode:'synthesis',
      inputs:[{name:'finding',from:{step_id:'A',slot:'value'}}]})]));
    await f.settle('A');const returned=record(f.calls[0].action.id);returned.outputs[0].observation_refs=['obs-A'];
    returned.assessment={outcome:'failure',summary:'Model requests stricter verification',checks:[
      {description:'Invented gate',status:'failed',refs:['not-admitted'],explanation:'A diagnostic claim only'}]};
    const accepted=await f.controller.execute('record','accept',returned);
    assert.equal(accepted.details.ok,true,JSON.stringify(accepted));
    let state=await f.controller.readState();assert.equal(state.graph.nodes[0].phase,'limited');
    assert.equal(f.calls[1].node.id,'B');
    const actionId=state.graph.nodes[0].assess_action_id;
    const note=await f.controller.execute('assess','late-review',{action_id:actionId,outcome:'failure',
      checks:[{description:'Another gate',status:'failed',refs:['unknown'],explanation:'Not a source grant'}],summary:'Unfinished review'});
    assert.equal(note.details.ok,true,JSON.stringify(note));assert.equal(note.details.result.diagnostic_only,true);
    state=await f.controller.readState();assert.equal(state.graph.nodes[0].phase,'limited');
    assert.deepEqual(state.graph.results[0].observation_refs,['obs-A']);
    assert.equal(state.graph.nodes[1].phase,'executing');
    assert.deepEqual(await f.controller.execute('record','accept',returned),accepted);
  }finally{await f.controller.close({reason:'Done'});}
});
test('advisory record needs no parent assessment and still requires actual admitted output sources',async()=>{
  const f=fixture({config:{researchRuntime:{graphLimits:limits,delegation:{concurrency:1},isolatedTaskExecution:true,
    lightweightTaskNodes:true,nodeReviewMode:'advisory'}}});
  try{
    await f.controller.execute('plan','plan',plan([node('A',{checks:[]})]));await f.settle('A');
    const returned=record(f.calls[0].action.id);returned.outputs[0].observation_refs=['unknown'];
    assert.equal((await f.controller.execute('record','foreign',returned)).details.ok,false);
    assert.equal((await f.controller.readState()).graph.nodes[0].phase,'executed');
    returned.outputs[0].observation_refs=['obs-A'];
    assert.equal((await f.controller.execute('record','valid',returned)).details.ok,true);
    assert.equal((await f.controller.readState()).graph.nodes[0].phase,'success');
  }finally{await f.controller.close({reason:'Done'});}
});
test('incremental tasks select independently from the host source catalog',async()=>{
  const f=fixture({config:{researchSources:[{ref:'first',revision:'v1'},{ref:'later',revision:'v2'}],
    researchRuntime:{graphLimits:limits,delegation:{concurrency:2},isolatedTaskExecution:true,lightweightTaskNodes:true}}});
  try{
    const initial=plan([node('A',{source_refs:['first']})]);initial.source_refs=['unused-stale-root-ref'];
    assert.equal((await f.controller.execute('plan','initial',initial)).details.ok,true);
    assert.deepEqual(f.calls[0].action.source_versions,[{ref:'first',revision:'v1'}]);
    assert.equal((await f.controller.execute('revise','later',{nodes:[node('B',{source_refs:['later']})],reason:'Next independent task',rerun:[]})).details.ok,true);
    assert.deepEqual(f.calls[1].action.source_versions,[{ref:'later',revision:'v2'}]);
    const before=f.calls.length;
    assert.equal((await f.controller.execute('revise','unknown',{nodes:[node('C',{source_refs:['ungranted']})],reason:'Unknown source',rerun:[]})).details.ok,false);
    assert.equal(f.calls.length,before);
  }finally{await f.controller.close({reason:'Done'});}
});
test('lightweight tasks do not require a model-created check inventory or duplicate root sources',async()=>{
  const f=fixture({config:{researchRuntime:{graphLimits:limits,delegation:{concurrency:1},isolatedTaskExecution:true,lightweightTaskNodes:true}}});
  try{
    const tools=registered(f.controller),schema=tools.agent_research_plan.parameters;
    assert.equal(schema.required.includes('source_refs'),false);
    assert.equal(schema.properties.nodes.items.required.includes('checks'),false);
    assert.equal(schema.properties.nodes.items.required.includes('questions'),false);
    assert.equal(schema.properties.nodes.items.required.includes('expected_outputs'),false);
    const task=node('A');delete task.checks;delete task.questions;delete task.expected_outputs;
    assert.equal((await f.controller.execute('plan','no-check-inventory',plan([task]))).details.ok,true);
    assert.deepEqual(f.calls[0].node.checks,[]);
    assert.deepEqual(f.calls[0].node.questions,[task.purpose]);
    assert.deepEqual(f.calls[0].node.expected_outputs,task.outputs.map(output=>output.description));
  }finally{await f.controller.close({reason:'Done'});}
});
test('standalone synthesis accepts explicitly selected historical products',async()=>{
  const f=fixture({config:{researchSources:[{ref:'prior',revision:'v1'}],deliveryReviewSources:[{source_ref:'prior',origin:'previous_product'}],
    researchRuntime:{graphLimits:limits,delegation:{concurrency:1},isolatedTaskExecution:true,lightweightTaskNodes:true}}});
  try{
    assert.equal((await f.controller.execute('plan','historical',plan([node('report',{mode:'synthesis',source_refs:['prior']})]))).details.ok,true);
    assert.equal(f.calls[0].node.mode,'synthesis');
    assert.deepEqual(f.calls[0].action.source_versions,[{ref:'prior',revision:'v1'}]);
  }finally{await f.controller.close({reason:'Done'});}
});
test('lightweight planning defaults omitted empty arrays without inventing task inputs or dependencies',async()=>{
  const f=fixture({config:{researchRuntime:{graphLimits:limits,delegation:{concurrency:1},isolatedTaskExecution:true,lightweightTaskNodes:true}}});
  const empty=id=>{const value=node(id);for(const key of ['depends_on','inputs'])delete value[key];return value;};
  try{
    const tools=registered(f.controller);
    for(const name of ['agent_research_plan','agent_research_revise']){
      const required=tools[name].parameters.properties.nodes.items.required;
      assert.ok(['depends_on','inputs'].every(key=>!required.includes(key)));
      assert.ok(required.includes('source_refs'),'Source grants require an explicit choice');
    }
    const result=await f.controller.execute('plan','light-plan',plan([empty('A')]));
    assert.equal(result.details.ok,true,JSON.stringify(result));
    assert.deepEqual(f.calls[0].action.input_bindings,[]);
    assert.deepEqual(f.calls[0].action.source_refs,[]);
    const added=await f.controller.execute('revise','light-revise',{nodes:[empty('B')],reason:'New independent question',rerun:[]});
    assert.equal(added.details.ok,true,JSON.stringify(added));
    const invalid=await f.controller.execute('revise','light-dependent',{nodes:[{...empty('C'),inputs:[{name:'prior',from:{step_id:'A',slot:'value'}}]}],reason:'Invalid missing dependency',rerun:[]});
    assert.equal(invalid.details.ok,false,'A selected producer still requires its explicit dependency');
    const missing=empty('D');delete missing.source_refs;
    const unselected=await f.controller.execute('revise','missing-source',{nodes:[missing],reason:'Source selection omitted',rerun:[]});
    assert.equal(unselected.details.ok,false);
    assert.match(JSON.stringify(unselected),/source_refs/);
    assert.deepEqual((await f.controller.readState()).graph.nodes.map(x=>x.id),['A','B']);
  }finally{await f.controller.close();}
});
test('synthesis role guides work while the host catalog controls source permission',async()=>{
  const f=fixture({config:{researchSources:['raw','prior'],deliveryReviewSources:[{source_ref:'raw',origin:'original_input'},
    {source_ref:'prior',origin:'previous_product'}],researchRuntime:{graphLimits:limits,delegation:{concurrency:1},isolatedTaskExecution:true,lightweightTaskNodes:true}}});
  try{
    const consumer=source=>node('B',{mode:'synthesis',depends_on:['A'],inputs:[{name:'finding',from:{step_id:'A',slot:'value'}}],source_refs:[source]});
    const invalid=await f.controller.execute('plan','ungranted-synthesis',plan([node('A'),consumer('ungranted')]));
    assert.equal(invalid.details.ok,false);assert.match(JSON.stringify(invalid),/not admitted/i);assert.equal(f.calls.length,0);
    const valid=await f.controller.execute('plan','context-synthesis',plan([node('A',{source_refs:['raw']}),consumer('raw')]));
    assert.equal(valid.details.ok,true,JSON.stringify(valid));
    assert.deepEqual((await f.controller.readState()).graph.nodes.find(n=>n.id==='B').source_refs,['raw']);
  }finally{await f.controller.close();}
});
test('lightweight compact graph removes duplicate lineage while retaining full recoverable bindings',async()=>{
  const sources=Array.from({length:4},(_,i)=>({ref:'source-'+i+'x'.repeat(100),revision:'sha256:'+'a'.repeat(64)}));
  const f=fixture({config:{researchSources:sources,researchRuntime:{graphLimits:limits,delegation:{concurrency:2},isolatedTaskExecution:true,lightweightTaskNodes:true}}});
  const planned=await f.controller.execute('plan','compact-plan',{...plan([node('A',{source_refs:sources.map(x=>x.ref)}),
    node('B',{depends_on:['A'],inputs:[{name:'prior',from:{step_id:'A',slot:'value'}}]})]),source_refs:sources.map(x=>x.ref)});
  assert.equal(planned.details.ok,true,JSON.stringify(planned));
  await f.settle('A');await accept(f,'A');
  const full=await f.controller.readState(),compact=await f.controller.readState({compact:true});
  const fullNode=full.graph.nodes.find(x=>x.id==='B'),smallNode=compact.graph.nodes.find(x=>x.id==='B');
  assert.ok(fullNode.input_bindings[0].source_versions.length);
  assert.equal(smallNode.input_bindings[0].source_versions,undefined);
  assert.equal(smallNode.input_bindings[0].result_ref,fullNode.input_bindings[0].result_ref);
  assert.doesNotMatch(JSON.stringify(compact.graph.actions),/source_versions|method_ref|owner/);
  assert.match(compact.graph.definitions,/graph_ref/);
  assert.ok(JSON.stringify(compact).length<JSON.stringify(full).length);
  assert.deepEqual((await f.controller.readState()).graph,full.graph);
  await f.controller.close();
});
test('work edition inspects valid partial slots without approving an incomplete proposal or foreign binding',async()=>{
  const f=fixture({config:{researchRuntime:{graphWorkEdition:'capstone-graph-work/1',graphWork:{schema:'capstone-graph-work/1',mode:'off'},graphLimits:limits,delegation:{concurrency:2}}}});
  await f.controller.execute('plan','plan',plan([node('A',{outputs:[{slot:'value',kind:'observation',description:'Useful finding'},{slot:'file',kind:'artifact',description:'Optional missing file'}]})]));
  const {action,validateProposal}=f.calls[0];
  const handoff={schema:'capstone-node-proposal/1',binding:{action_id:action.id,definition_ref:action.definition_ref,execution_revision:1,consumed_results:[],source_versions:[]},
    outputs:[{slot:'value',artifact_refs:[],observation_refs:['obs-A'],summary:'Actual partial result',scope:'Declared subset'}],
    checks:[{description:'Verify A',status:'not_run',refs:[],explanation:'Time reserved for integration'}],limitations:['File output was not completed']};
  const candidate={handoff,receipts:[{ref:'obs-A',action_id:action.id,attempt_id:'attempt',owner,status:'completed'}],products:[],inspect_partial:true};
  assert.throws(()=>validateProposal({...candidate,inspect_partial:false}),/each declared output/);
  const inspected=validateProposal(candidate);
  assert.equal(inspected.status,'incomplete');assert.equal(inspected.proposal_ref,undefined);
  assert.deepEqual(inspected.outputs,handoff.outputs);assert.deepEqual(inspected.missing_slots,['file']);
  const foreign=structuredClone(candidate);foreign.handoff.binding.action_id='foreign-action';
  assert.throws(()=>validateProposal(foreign),/action or input version/);
  const unsupported=structuredClone(candidate);unsupported.handoff.outputs[0].observation_refs=['foreign-private-ref'];
  assert.deepEqual(validateProposal(unsupported).outputs,[]);
  assert.doesNotMatch(JSON.stringify(validateProposal(unsupported)),/foreign-private-ref/);
  await f.controller.close();
});
test('shared whole-task budget includes preparation and remains frozen across restore and late readiness',async()=>{
  const realNow=Date.now,origin=realNow()-99000;
  const config={deadlineAt:origin+1800000,researchRuntime:{graphWorkEdition:'capstone-graph-work/1',graphWorkStartedAt:origin,
    graphWork:{schema:'capstone-graph-work/1',mode:'usable_draft',target_seconds:240,integration_reserve_seconds:60,child_wrapup_seconds:15},graphLimits:limits,delegation:{concurrency:2}}};
  const f=fixture({config});
  try{
    const initial=await f.controller.readState();assert.ok(initial.work_budget.remaining_seconds<=141);
    await f.controller.execute('plan','plan',plan([node('A'),node('B')]));
    assert.equal(f.calls.length,2);assert.deepEqual(f.calls[0].work_envelope,f.calls[1].work_envelope);
    const envelope=f.calls[0].work_envelope;
    assert.equal(envelope.wrapup_at_ms,origin+165000);assert.equal(envelope.finish_by_ms,origin+180000);
    assert.deepEqual(JSON.parse(f.view.state.notes[0].text).snapshot.work_envelope,envelope);
    await f.controller.close();Date.now=()=>origin+181000;
    const restored=createEnterpriseGraphController({...f.ports,config:{...f.ports.config,researchRuntime:{...config.researchRuntime,graphWorkStartedAt:origin+60000}},
      dispatchNode:()=>assert.fail('No restored launch')});
    const state=await restored.readState();assert.equal(state.work_budget.phase,'integration');
    assert.equal(state.work_budget.soft_task_deadline_ms,origin+240000);await restored.close();
    const changedPolicy=createEnterpriseGraphController({...f.ports,config:{...f.ports.config,researchRuntime:{...config.researchRuntime,
      graphWork:{...config.researchRuntime.graphWork,target_seconds:241}}}});
    await assert.rejects(changedPolicy.readState(),/accepted policy/);
    const late=fixture({config});await late.controller.execute('plan','late-plan',plan([node('A')]));
    assert.equal(late.calls.length,0);assert.equal((await late.controller.readState()).graph.nodes[0].phase,'ready');
    assert.equal((await late.controller.readState()).work_budget.phase,'integration');await late.controller.close();
  }finally{Date.now=realNow;await f.controller.close();}
});
test('proposal preflight shares final admission rules and remains pure across sibling settlement',async()=>{
  const f=fixture();await f.controller.execute('plan','plan',plan([node('A'),node('B')]));
  const request=f.calls.find(item=>item.node.id==='A'),action=request.action;
  const receipt={ref:'obs-A',owner,attempt_id:'attempt',action_id:action.id,status:'completed'};
  const handoff={schema:'capstone-node-proposal/1',binding:{action_id:action.id,definition_ref:action.definition_ref,execution_revision:action.execution_revision,consumed_results:[],source_versions:[]},
    outputs:[{slot:'value',product_paths:[],observation_refs:['obs-A'],summary:'Actual observation',scope:'Declared scope'}],
    checks:[{description:'Verify A',status:'passed',refs:['obs-A'],explanation:'Actual inspected support'}],limitations:[]};
  const candidate={handoff,receipts:[receipt],products:[],metadata:true,selected_paths:[]},before=f.view.research_revision;
  assert.deepEqual(request.validateProposal(candidate),{status:'metadata_valid'});assert.equal(f.view.research_revision,before);
  for(const [change,code,field] of [
    [item=>item.checks[0].refs=[],'check_support_missing','checks[0].refs'],
    [item=>item.checks[0].refs=['foreign-secret-reference'],'check_refs','checks[0].refs'],
    [item=>item.checks[0].description='Different label','check_label','checks[0].description'],
    [item=>item.outputs[0].slot='unknown','output_support','outputs'],
    [item=>item.binding.execution_revision=2,'proposal_binding','binding']]){
    const wrong=structuredClone(candidate);change(wrong.handoff);
    assert.throws(()=>request.validateProposal(wrong),error=>{
      assert.equal(error.diagnostic.code,code);assert.equal(error.diagnostic.field,field);
      assert.doesNotMatch(JSON.stringify(error.diagnostic),/foreign-secret-reference|\/private\//);return true;
    });assert.equal(f.view.research_revision,before);
  }
  await f.settle('B');assert.deepEqual(request.validateProposal(candidate),{status:'metadata_valid'});
  await f.controller.close();
  assert.throws(()=>request.validateProposal(candidate),error=>error.name==='AbortError');
});
test('structured child proposal binds declared slots and checks once, then records and assesses by its exact ref',async()=>{
  const f=fixture();
  await f.controller.execute('plan','plan',plan([node('A',{outputs:[{slot:'files',kind:'artifact',description:'Saved table'}]})]));
  const request=f.calls[0],action=request.action;
  assert.equal(request.contract_schema,'capstone-node-contract/1');
  const product={ref:'product-table',path:'context-results/table.csv',sha256:'a'.repeat(64),bytes:6,roles:['support'],status:'ready',owner,attempt_id:'attempt',action_id:action.id};
  const handoff={schema:'capstone-node-proposal/1',binding:{action_id:action.id,definition_ref:action.definition_ref,
    execution_revision:action.execution_revision,consumed_results:[],source_versions:[]},
    outputs:[{slot:'files',artifact_refs:[product.ref],observation_refs:['obs-A'],summary:'Saved table',scope:'Assigned inputs'}],
    checks:[{description:'Verify A',status:'passed',refs:['obs-A'],explanation:'Actual successful native observation'}],limitations:[]};
  await f.settle('A','completed','Saved table',[product],handoff);
  const state=await f.controller.readState(),proposal=state.pending_proposals[0].proposal;
  assert.equal(proposal.status,'validated');assert.match(proposal.proposal_ref,/^proposal:/);
  assert.deepEqual(proposal.outputs,handoff.outputs);assert.deepEqual(proposal.checks,handoff.checks);
  const recorded=await f.controller.execute('record','record-proposal',{action_id:action.id,proposal_ref:proposal.proposal_ref,outcome:'completed',limitations:[]});
  assert.equal(recorded.details.ok,true,JSON.stringify(recorded));
  const assessAction=(await f.controller.readState()).graph.actions.find(item=>item.kind==='assess');
  const conflict=await f.controller.execute('assess','conflicting-assess',{action_id:assessAction.id,proposal_ref:proposal.proposal_ref,
    checks:handoff.checks,outcome:'success',summary:'Parent judgment'});
  assert.equal(conflict.details.ok,false);
  assert.equal(conflict.details.error.assessment_feedback.proposal_ref,proposal.proposal_ref);
  assert.deepEqual(conflict.details.error.assessment_feedback.omit_fields,['checks']);
  assert.doesNotMatch(conflict.content[0].text,/Copy required_check_labels/);
  assert.equal((await f.controller.execute('assess','assess-proposal',{action_id:assessAction.id,proposal_ref:proposal.proposal_ref,outcome:'success',summary:'Parent accepted supported checks'})).details.ok,true);
  const retained=JSON.parse(f.view.state.notes.at(-1).text);
  assert.deepEqual(retained.snapshot.executions[0].record.outputs,handoff.outputs);
  assert.deepEqual(retained.snapshot.executions[0].assessment.checks,handoff.checks);
  assert.equal((await f.controller.readState()).graph.nodes[0].phase,'success');
  await f.controller.close();
});
test('graph semantic progress ignores failed receipts and checkpoint-only control calls',async()=>{
  const f=fixture();await f.controller.execute('plan','plan',plan([node('P',{execution:'parent'})]));
  await f.controller.execute('start','start',{step_id:'P'});const before=await f.controller.progressKey();
  const failed=await f.controller.beginTool({toolCallId:'failed',toolName:'bash'});f.controller.endTool(failed,{isError:true});
  assert.equal(await f.controller.progressKey(),before);
  const ok=await f.controller.beginTool({toolCallId:'read-one',toolName:'read'});f.controller.endTool(ok,{content:[{type:'text',text:'actual'}],details:{native_research_source:{source_ref:'obs:one'}}});
  const advanced=await f.controller.progressKey();assert.notEqual(advanced,before);
  const duplicate=await f.controller.beginTool({toolCallId:'read-two',toolName:'read'});f.controller.endTool(duplicate,{content:[{type:'text',text:'actual'}],details:{native_research_source:{source_ref:'obs:two'}}});
  assert.equal(await f.controller.progressKey(),advanced);
  await f.controller.close();
});
test('parent start control is attributed to its exact committed issued action',async()=>{
  const f=fixture();await f.controller.execute('plan','plan',plan([node('P',{execution:'parent'})]));
  const reply=await f.controller.execute('start','start-owned',{step_id:'P',kind:'execute'}),state=await f.controller.readState();
  const issued=state.graph.nodes[0].execute_action_id,progress=f.events.find(item=>item.control?.tool_call_id==='start-owned');
  assert.equal(progress.action_id,issued);assert.equal(reply.details.result.action_id,issued);assert.equal(reply.details.result.step_id,'P');
  await f.controller.close();
});
test('bad structured associations retain true native status and saved grants without becoming approved proposals',async()=>{
  for(const corrupt of [value=>{value.binding.execution_revision++;},value=>{value.outputs[0].slot='other';},
    value=>{value.outputs[0].artifact_refs=['foreign-product'];},value=>{value.outputs[0].observation_refs=['foreign-observation'];},
    value=>{value.checks[0].description='Wrong label';},value=>{value.checks[0].refs=['foreign-observation'];},
    value=>{value.checks[0].refs=[];},value=>{value.outputs.push(value.outputs[0]);}]){
    const f=fixture();await f.controller.execute('plan','plan',plan([node('A',{outputs:[{slot:'file',kind:'artifact',description:'Saved file'}]})]));
    const action=f.calls[0].action,product={ref:'product-table',path:'context-results/table.csv',sha256:'a'.repeat(64),bytes:6,
      roles:['support'],status:'ready',owner,attempt_id:'attempt',action_id:action.id};
    const handoff={schema:'capstone-node-proposal/1',binding:{action_id:action.id,definition_ref:action.definition_ref,
      execution_revision:action.execution_revision,consumed_results:[],source_versions:[]},
      outputs:[{slot:'file',artifact_refs:[product.ref],observation_refs:['obs-A'],summary:'Saved file',scope:'Assigned input'}],
      checks:[{description:'Verify A',status:'passed',refs:['obs-A'],explanation:'Native observation'}],limitations:[]};
    corrupt(handoff);await f.settle('A','completed','Actual saved bytes',[product],handoff);
    const state=await f.controller.readState(),saved=f.view;
    assert.equal(state.pending_proposals[0].status,'completed');assert.equal(state.pending_proposals[0].proposal.status,'rejected');
    assert.deepEqual(state.pending_proposals[0].product_refs,[product.ref]);
    assert.equal((await f.controller.execute('record','bad-reference',{action_id:action.id,proposal_ref:'proposal:invented',outcome:'completed',limitations:[]})).details.ok,false);
    assert.equal((await f.controller.execute('record','bad-manual',{action_id:action.id,outcome:'completed',outputs:[{slot:'file',artifact_refs:['foreign-product'],observation_refs:['obs-A'],summary:'Bad grant',scope:'Assigned'}],limitations:[]})).details.ok,false);
    assert.deepEqual(f.view,saved);await f.controller.close();
  }
});
test('proposal shorthand is exclusive and producer check claims still require explicit parent acceptance',async()=>{
  const f=fixture();await f.controller.execute('plan','plan',plan([node('A')]));const action=f.calls[0].action;
  const handoff={schema:'capstone-node-proposal/1',binding:{action_id:action.id,definition_ref:action.definition_ref,execution_revision:action.execution_revision,consumed_results:[],source_versions:[]},
    outputs:[{slot:'value',artifact_refs:[],observation_refs:['obs-A'],summary:'Actual',scope:'Assigned'}],checks:[{description:'Verify A',status:'not_run',refs:[],explanation:'Not checked'}],limitations:['Check not performed']};
  await f.settle('A','completed','Actual result',[],handoff);const proposal=(await f.controller.readState()).pending_proposals[0].proposal;
  assert.equal((await f.controller.execute('record','both',{action_id:action.id,proposal_ref:proposal.proposal_ref,outputs:handoff.outputs,outcome:'completed',limitations:[]})).details.ok,false);
  assert.equal((await f.controller.execute('record','record',{action_id:action.id,proposal_ref:proposal.proposal_ref,outcome:'completed',limitations:[]})).details.ok,true);
  const assess=(await f.controller.readState()).graph.actions.find(item=>item.kind==='assess');
  assert.equal((await f.controller.execute('assess','claimed-success',{action_id:assess.id,proposal_ref:proposal.proposal_ref,outcome:'success',summary:'Unperformed check'})).details.ok,false);
  assert.equal((await f.controller.execute('assess','limited',{action_id:assess.id,proposal_ref:proposal.proposal_ref,outcome:'limited',summary:'Explicit parent limitation'})).details.ok,true);
  await f.controller.close();
});
async function parentWithInput(){
  let resolutions=0,f;
  f=fixture({ports:{resolveInputs:async action=>{resolutions++;return {handles:action.input_bindings.map(binding=>({ref:'handle-'+binding.name,
    result_ref:binding.result_ref,immutable:true,read_only:true})),manifests:action.input_bindings.map(binding=>
      JSON.parse(f.view.state.notes.at(-1).text).snapshot.results.find(item=>item.result_ref===binding.result_ref))};}}});
  const controller=f.controller;
  await controller.execute('plan','plan',plan([node('P',{execution:'parent',mode:'synthesis',depends_on:['A'],inputs:[{name:'prior',from:{step_id:'A',slot:'value'}}]}),node('A')]));
  await f.settle('A');const a=f.calls[0].action,payload=record(a.id);payload.outputs[0].observation_refs=['obs-A'];
  await controller.execute('record','record-A',payload);let state=await controller.readState();
  await controller.execute('assess','assess-A',{action_id:state.graph.nodes.find(item=>item.id==='A').assess_action_id,outcome:'success',
    checks:[{description:'Verify A',status:'passed',refs:['obs-A'],explanation:'Actual observation'}],summary:'Accepted'});
  await controller.execute('start','start-P',{step_id:'P',kind:'execute'});
  return {...f,controller,resolutions:()=>resolutions};
}
test('private parent input context resolves once per exact action without public handles',async()=>{
  const f=await parentWithInput(),before=f.resolutions(),first=await f.controller.readParentInputs();
  assert.equal(first.action.step_id,'P');assert.deepEqual(first.action.source_refs,[]);
  assert.deepEqual(first.inputs.manifests.map(item=>item.result_ref),first.action.input_bindings.map(item=>item.result_ref));
  assert.deepEqual(await f.controller.readParentInputs(),first);assert.equal(f.resolutions(),before+1);
  assert.doesNotMatch(JSON.stringify(await f.controller.readState()),/handle-prior/);
  assert.doesNotMatch(JSON.stringify(f.events),/handle-prior/);await f.controller.close();
});
test('private parent context distinguishes absent parent and an explicit empty input set',async()=>{
  const f=fixture();assert.equal(await f.controller.readParentInputs(),null);
  await f.controller.execute('plan','plan',plan([node('P',{execution:'parent'})]));
  assert.equal(await f.controller.readParentInputs(),null);
  await f.controller.execute('start','start',{step_id:'P',kind:'execute'});
  assert.deepEqual((await f.controller.readParentInputs()).inputs,{manifests:[],handles:[]});await f.controller.close();
});
test('closing cancels an in-flight private parent resolution and never caches its result',async()=>{
  const entered=defer();let aborted=false;
  const f=fixture({ports:{resolveInputs:async(_action,{signal})=>{entered.resolve();await new Promise((resolve,reject)=>{
    signal.addEventListener('abort',()=>{aborted=true;reject(signal.reason);},{once:true});});}}});
  await f.controller.execute('plan','plan',plan([node('P',{execution:'parent'})]));
  await f.controller.execute('start','start',{step_id:'P',kind:'execute'});
  const reading=f.controller.readParentInputs();await entered.promise;
  await f.controller.close();assert.equal(aborted,true);await assert.rejects(reading,{name:'AbortError'});
});
test('failed parent resolution retries once and successful metadata is then cached',async()=>{
  let attempts=0;
  const f=fixture({ports:{resolveInputs:async()=>{if(++attempts===1)throw new Error('Temporary provider failure');return {manifests:[],handles:[]};}}});
  await f.controller.execute('plan','plan',plan([node('P',{execution:'parent'})]));
  f.lose();await f.controller.execute('start','start',{step_id:'P',kind:'execute'});
  assert.equal(f.controller.status.update_pending,true);
  await assert.rejects(f.controller.readParentInputs(),/Temporary provider failure/);
  const recovered=await f.controller.readParentInputs();assert.equal(recovered.action.step_id,'P');
  await f.controller.readParentInputs();assert.equal(attempts,2);assert.equal(f.controller.status.update_pending,false);await f.controller.close();
});
test('a new parent action selects fresh refs while its old cached input remains immutable',async()=>{
  const external=version=>({schema:'capstone-task-result/1',result_ref:'external-'+version,owner,
    producer:{step_id:'prior',action_id:'prior-'+version,attempt_id:'prior-attempt',execution_revision:1},slot:'value',kind:'observation',
    source_versions:[{ref:'source',revision:version}],method:{unavailable:'Fixture retained observation'},consumed_results:[],
    observation_refs:['prior-observation-'+version],artifact_refs:[],supersedes:[],summary:'Retained '+version,scope:'Prior version',recompute_reason:null});
  const results=['v1','v2'].map(external);let resolves=0;
  const f=fixture({config:{researchResults:results},ports:{resolveInputs:async action=>{resolves++;return {handles:[],
    manifests:action.input_bindings.map(binding=>results.find(item=>item.result_ref===binding.result_ref))};}}});
  const parent=version=>node('P',{execution:'parent',mode:'synthesis',inputs:[{name:'prior',result_ref:'external-'+version}]});
  await f.controller.execute('plan','plan',plan([parent('v1')]));await f.controller.execute('start','start-v1',{step_id:'P'});
  const first=await f.controller.readParentInputs();
  await f.controller.execute('record','record-v1',{...record(first.action.id),outputs:[{slot:'value',observation_refs:['prior-observation-v1'],artifact_refs:[],summary:'Retained synthesis',scope:'v1'}]});
  let state=await f.controller.readState();await f.controller.execute('assess','assess-v1',{action_id:state.graph.nodes[0].assess_action_id,outcome:'success',
    checks:[{description:'Verify P',status:'passed',refs:['prior-observation-v1'],explanation:'Retained observation'}],summary:'Accepted'});
  const priorResult=state.graph.results[0].result_ref;
  assert.equal((await f.controller.execute('revise','revise',{nodes:[parent('v2')],reason:'Use explicit newer result',
    rerun:[{step_id:'P',reason:{kind:'source_changed',refs:['external-v2']},supersedes:[priorResult]}]})).details.ok,true);
  await f.controller.execute('start','start-v2',{step_id:'P'});const second=await f.controller.readParentInputs();
  assert.notEqual(first.action.id,second.action.id);assert.equal(second.inputs.manifests[0].result_ref,'external-v2');
  assert.equal(first.inputs.manifests[0].result_ref,'external-v1');await f.controller.readParentInputs();assert.equal(resolves,2);await f.controller.close();
});
test('proposal inspection exposes named products and exact refs without minting evidence',async()=>{
  const bindings=[];
  const f=fixture({ports:{readReferenceContent:async({ref})=>({ref,kind:'product',sha256:'a'.repeat(64),bytes:6,
    offset_bytes:0,read_bytes:6,next_offset_bytes:null,content_status:'text',text:'actual'})}});
  await f.controller.execute('plan','plan',plan([node('A',{outputs:[{slot:'files',kind:'artifact',description:'Several actual files'}]})]));
  const action=f.calls[0].action,product={ref:'product-report',path:'context-results/exact/report.csv',sha256:'a'.repeat(64),bytes:6,
    roles:['primary'],status:'ready',owner,attempt_id:'attempt',action_id:action.id};
  await f.settle('A','completed','Saved files',[product]);const before=f.view;
  const metadata=await f.controller.readReference('metadata',{section:'reference',action_id:action.id},{onBinding:value=>bindings.push(value)});
  assert.equal(metadata.details.ok,true);const result=metadata.details.result;
  assert.equal(result.products[0].logical_path,product.path);assert.equal(result.products[0].ref,product.ref);
  assert.deepEqual(result.declared_outputs,[{slot:'files',kind:'artifact',description:'Several actual files'}]);
  assert.equal(bindings.length,1);assert.deepEqual(bindings[0].action,action);assert.deepEqual(bindings[0].checkpoint,(await f.controller.readState()).checkpoint);
  const read=await f.controller.readReference('content',{section:'reference',action_id:action.id,ref:product.ref,mode:'text',offset_bytes:0,length_bytes:6});
  assert.equal(read.details.ok,true,JSON.stringify(read));
  assert.equal(read.details.result.text,'actual');assert.equal(read.details.result.inspection_only,true);
  assert.deepEqual(f.view,before);assert.equal(f.controller.status.update_pending,false);
  for(const patch of [{ref:'/tmp/arbitrary'},{action_id:'foreign'},{ref:'ungranted'},{length_bytes:1e12}]){
    const reply=await f.controller.readReference('bad',{section:'reference',action_id:action.id,ref:product.ref,mode:'text',offset_bytes:0,length_bytes:6,...patch});
    assert.equal(reply.details.ok,false);
  }
  assert.deepEqual(f.view,before);await f.controller.close();
});
test('binary reference inspection returns metadata without requiring a content read range',async()=>{
  const f=fixture({ports:{readReferenceContent:async({ref})=>({ref,kind:'product',sha256:'a'.repeat(64),bytes:100,
    content_status:'metadata_only',content_reason:'unsupported_text_type'})}});
  await f.controller.execute('plan','plan',plan([node('A')]));const action=f.calls[0].action;
  await f.settle('A','completed','Binary product',[{ref:'binary-file',path:'context-results/image.png',sha256:'a'.repeat(64),bytes:100,
    roles:['support'],status:'ready',owner,attempt_id:'attempt',action_id:action.id}]);
  const reply=await f.controller.readReference('binary',{section:'reference',action_id:action.id,ref:'binary-file',mode:'text',offset_bytes:0,length_bytes:8});
  assert.equal(reply.details.ok,true,JSON.stringify(reply));assert.equal(reply.details.result.content_status,'metadata_only');
  assert.equal(reply.details.result.text,undefined);await f.controller.close();
});
test('registered next command reconciles an exact lost settlement acknowledgement without native replay',async()=>{
  const f=fixture(),tools=registered(f.controller);
  await tools.agent_research_plan.execute('plan',plan([node('A')]));
  f.lose();await f.settle('A');const retained=f.requests.at(-1),action=f.calls[0].action;
  const payload=record(action.id);payload.outputs[0].observation_refs=['obs-A'];
  const result=await tools.agent_research_record.execute('new-record-call',payload);
  assert.equal(result.details.ok,true,JSON.stringify(result));
  assert.deepEqual(f.requests.at(-2),retained);assert.equal(f.calls.length,1);
  assert.equal((await f.controller.readState()).graph.results[0].producer.action_id,action.id);
  await f.controller.close();
});
test('continuation reconciles a lost model checkpoint acknowledgement before another model turn',async()=>{
  const f=fixture(),tools=registered(f.controller);
  await tools.agent_research_plan.execute('plan',plan([node('A')]));await f.settle('A');
  const payload=record(f.calls[0].action.id);payload.outputs[0].observation_refs=['obs-A'];f.lose();
  assert.equal((await tools.agent_research_record.execute('record',payload)).details.ok,false);
  const retained=f.requests.at(-1),continuation=JSON.parse((await f.controller.continuationState()).prompt);
  assert.equal(continuation.update_pending,false);assert.equal(continuation.graph.nodes[0].phase,'recorded');
  assert.deepEqual(f.requests.at(-1),retained);assert.equal(f.calls.length,1);
  await f.controller.close();
});
test('registered command waits for active checkpoint adoption without duplicate recovery',async()=>{
  const f=fixture(),tools=registered(f.controller);
  await tools.agent_research_plan.execute('plan',plan([node('A')]));
  const hold=f.hold(),settling=f.settle('A');await hold.entered.promise;
  const count=f.requests.length,payload=record(f.calls[0].action.id);payload.outputs[0].observation_refs=['obs-A'];
  let replied=false;const next=tools.agent_research_record.execute('next',payload).then(reply=>{replied=true;return reply;});
  await tick();assert.equal(replied,false);assert.equal(f.requests.length,count);
  hold.release.resolve();await settling;assert.equal((await next).details.ok,true);assert.equal(f.requests.length,count+1);
  assert.equal(f.calls.length,1);await f.controller.close();
});
test('unconfirmed continuation recovery makes one exact attempt and retains the failure',async()=>{
  const f=fixture();await f.controller.execute('plan','plan',plan([node('A')]));f.lose();await f.settle('A');
  const retained=f.requests.at(-1),count=f.requests.length;f.loseReplays(true);
  await assert.rejects(f.controller.continuationState(),{code:'research_update_not_confirmed'});
  assert.equal(f.requests.length,count+1);assert.deepEqual(f.requests.at(-1),retained);
  assert.equal(f.controller.status.update_pending,true);assert.equal(f.calls.length,1);
  f.loseReplays(false);await f.controller.continuationState();await f.controller.close();
});
test('continuation does not request a model turn if scheduling creates another unconfirmed checkpoint',async()=>{
  let f,loseScheduledStart=true;
  f=fixture({config:{researchRuntime:{graphLimits:limits,delegation:{concurrency:1}}},ports:{onProgress:event=>{
    f.events.push(event);
    if(loseScheduledStart&&event.graph.nodes[0].phase==='executed'){loseScheduledStart=false;f.lose();}
  }}});
  await f.controller.execute('plan','plan',plan([node('A'),node('B')]));f.lose();await f.settle('A');
  await assert.rejects(f.controller.continuationState(),{code:'research_update_not_confirmed'});
  assert.equal(f.controller.status.update_pending,true);assert.deepEqual(f.calls.map(item=>item.node.id),['A']);
  await f.controller.continuationState();assert.deepEqual(f.calls.map(item=>item.node.id),['A','B']);await f.controller.close();
});
test('aborted admission leaves the active exact write alone and never runs the queued command',async()=>{
  const f=fixture(),tools=registered(f.controller),abort=new AbortController();
  await tools.agent_research_plan.execute('plan',plan([node('A')]));
  const hold=f.hold(),settling=f.settle('A');await hold.entered.promise;
  const retained=f.requests.at(-1),count=f.requests.length,payload=record(f.calls[0].action.id);payload.outputs[0].observation_refs=['obs-A'];
  const next=tools.agent_research_record.execute('cancelled-next',payload,abort.signal);
  await tick();abort.abort(new DOMException('Stop queued admission','AbortError'));
  await assert.rejects(next,{name:'AbortError'});assert.equal(f.requests.length,count);assert.deepEqual(f.requests.at(-1),retained);
  hold.release.resolve();await settling;await tick();assert.equal(f.requests.length,count);
  assert.equal((await f.controller.readState()).graph.nodes[0].phase,'executed');assert.equal(f.calls.length,1);
  await f.controller.close();
});
test('aborted active recovery adopts a late committed acknowledgement without launching native work',async()=>{
  let f;f=fixture({ports:{onProgress:event=>{
    f.events.push(event);if(event.events.some(item=>item.kind==='graph_committed'))f.lose();
  }}});
  await f.controller.execute('plan','plan',plan([node('A')]));
  assert.equal(f.controller.status.update_pending,true);assert.equal(f.calls.length,0);
  const retained=f.requests.at(-1),hold=f.hold(),abort=new AbortController();
  const recovering=f.controller.continuationState({signal:abort.signal});await hold.entered.promise;
  abort.abort(new DOMException('Stop active recovery','AbortError'));
  await assert.rejects(recovering,{name:'AbortError'});assert.equal(f.calls.length,0);
  hold.release.resolve();await tick();await tick();
  assert.deepEqual(f.requests.at(-1),retained);assert.equal(f.controller.status.update_pending,false);
  const state=await f.controller.readState();assert.equal(state.checkpoint.revision,f.view.research_revision);
  assert.equal(state.graph.nodes[0].phase,'executing');assert.equal(f.calls.length,0);
  await f.controller.close();
});
test('deadline bounds continuation waiting without clearing an active retained checkpoint',async()=>{
  const config={deadlineAt:Date.now()+10000},f=fixture({config});
  await f.controller.execute('plan','plan',plan([node('A')]));
  const hold=f.hold(),settling=f.settle('A');await hold.entered.promise;
  // The task deadline is host-owned; the model cannot change it.
  f.ports.config.deadlineAt=Date.now()+20;
  const waiting=f.controller.continuationState(),timer=setTimeout(()=>{},100);
  try{await assert.rejects(waiting,{name:'TimeoutError'});}finally{clearTimeout(timer);}
  assert.equal(f.controller.status.update_pending,true);assert.equal(f.calls.length,1);
  hold.release.resolve();await settling;await f.controller.close();
});
test('registered changed command bytes cannot replace the exact retained request',async()=>{
  const f=fixture(),tools=registered(f.controller);
  await tools.agent_research_plan.execute('plan',plan([node('A')]));await f.settle('A');
  const payload=record(f.calls[0].action.id);payload.outputs[0].observation_refs=['obs-A'];f.lose();
  await tools.agent_research_record.execute('record',payload);const retained=f.requests.at(-1),count=f.requests.length;
  const result=await tools.agent_research_record.execute('record',{...payload,limitations:['Changed command bytes']});
  assert.equal(result.details.ok,false);assert.equal(f.requests.length,count+1);assert.deepEqual(f.requests.at(-1),retained);
  const exact=await tools.agent_research_record.execute('record',payload);assert.equal(exact.details.ok,true);
  assert.equal(f.requests.length,count+1);assert.equal(f.calls.length,1);await f.controller.close();
});
test('correctable invalid assessment refs create no pending checkpoint',async()=>{
  const f=fixture(),tools=registered(f.controller);
  await tools.agent_research_plan.execute('plan',plan([node('A')]));await f.settle('A');
  const payload=record(f.calls[0].action.id);payload.outputs[0].observation_refs=['obs-A'];
  await tools.agent_research_record.execute('record',payload);const state=await f.controller.readState(),count=f.requests.length;
  const assessment={action_id:state.graph.nodes[0].assess_action_id,outcome:'success',
    checks:[{description:'Verify A',status:'passed',refs:['invented-ref'],explanation:'Invalid reference'}],summary:'Acceptance'};
  const before=f.view,rejected=await tools.agent_research_assess.execute('invalid',assessment);
  assert.equal(rejected.details.ok,false);
  assert.deepEqual(rejected.details.error.assessment_feedback,{action_id:assessment.action_id,
    required_check_labels:['Verify A'],valid_check_refs:['obs-A'],
    recorded_output_result_refs:state.graph.nodes[0].output_bindings.map(item=>item.result_ref)});
  assert.match(rejected.content[0].text,/Verify A/);assert.match(rejected.content[0].text,/obs-A/);
  assert.deepEqual(f.view,before);
  assert.equal(f.controller.status.update_pending,false);assert.equal(f.requests.length,count);
  assessment.checks[0].refs=['obs-A'];assert.equal((await tools.agent_research_assess.execute('corrected',assessment)).details.ok,true);
  await f.controller.close();
});
test('assessment feedback is limited to the exact current action and check refs',async()=>{
  const f=fixture(),tools=registered(f.controller);
  await tools.agent_research_plan.execute('plan',plan([node('A'),node('B')]));await f.settle('A');await f.settle('B');
  for(const id of ['A','B']){const payload=record(f.calls.find(item=>item.node.id===id).action.id);payload.outputs[0].observation_refs=['obs-'+id];
    await tools.agent_research_record.execute('record-'+id,payload);}
  const state=await f.controller.readState(),a=state.graph.nodes.find(item=>item.id==='A'),before=f.view;
  const assessment={action_id:a.assess_action_id,outcome:'success',checks:[{description:'Wrong label',status:'passed',refs:['obs-B'],explanation:'Wrong action'}],summary:'Acceptance'};
  const rejected=await tools.agent_research_assess.execute('invalid-label',assessment);
  assert.deepEqual(rejected.details.error.assessment_feedback,{action_id:a.assess_action_id,required_check_labels:['Verify A'],valid_check_refs:['obs-A'],
    recorded_output_result_refs:a.output_bindings.map(item=>item.result_ref)});
  assert.doesNotMatch(JSON.stringify(rejected),/Verify B|obs-B/);assert.deepEqual(f.view,before);
  for(const action_id of ['unknown-action',f.calls[0].action.id]){
    const reply=await tools.agent_research_assess.execute('invalid-'+action_id,{...assessment,action_id});
    assert.equal(reply.details.error.assessment_feedback,undefined);
  }
  assessment.checks=[{description:'Verify A',status:'passed',refs:[a.output_bindings[0].result_ref],explanation:'Saved output identifier'}];
  assert.equal((await tools.agent_research_assess.execute('output-is-not-evidence',assessment)).details.ok,false);
  assert.equal(f.controller.status.update_pending,false);assert.deepEqual(f.view,before);await f.controller.close();
});
test('assessment correction feedback stays within the public byte capacity',async()=>{
  const f=fixture(),tools=registered(f.controller);
  await tools.agent_research_plan.execute('plan',plan([node('A',{checks:['Check '+ 'x'.repeat(3000)]})]));await f.settle('A');
  const payload=record(f.calls[0].action.id);payload.outputs[0].observation_refs=['obs-A'];
  await tools.agent_research_record.execute('record',payload);const state=await f.controller.readState(),before=f.view;
  // A restored runtime may have a tighter public reply capacity than its checkpoint.
  const restored=createEnterpriseGraphController({...f.ports,config:{...f.ports.config,
    researchRuntime:{...f.ports.config.researchRuntime,graphLimits:{...limits,publicBytes:6000}}}});
  const assessment={action_id:state.graph.nodes[0].assess_action_id,outcome:'success',
    checks:[{description:'Wrong label',status:'passed',refs:['invented'],explanation:'Invalid'}],summary:'Acceptance'};
  const reply=await restored.execute('assess','invalid-bounded',assessment);
  assert.equal(reply.details.ok,false);assert.equal(reply.details.error.assessment_feedback,undefined);
  assert.ok(Buffer.byteLength(JSON.stringify(reply))<=6000);assert.deepEqual(f.view,before);
  await restored.close();await f.controller.close();
});
test('continuation recovery of a lost restored checkpoint never relaunches old native work',async()=>{
  const f=fixture();await f.controller.execute('plan','plan',plan([node('A'),node('B')]));f.lose();
  const restored=createEnterpriseGraphController({...f.ports,dispatchNode:async()=>assert.fail('Restored execution must not run')});
  const state=JSON.parse((await restored.continuationState()).prompt);
  assert.equal(state.update_pending,false);assert.deepEqual(state.graph.nodes.map(item=>item.settled_status),['unknown','unknown']);
  assert.equal(f.calls.length,2);await restored.close();await f.controller.close();
});
test('registered operation reports an already expired task deadline before checkpoint work',async()=>{
  const f=fixture({config:{deadlineAt:Date.now()-1}}),tools=registered(f.controller);
  await assert.rejects(tools.agent_research_plan.execute('expired',plan([node('A')])),{name:'TimeoutError'});
  assert.equal(f.requests.length,0);assert.equal(f.calls.length,0);
});
test('continuation cannot recover a checkpoint owned by another graph owner',async()=>{
  const f=fixture();await f.controller.execute('plan','plan',plan([node('A')]));const count=f.requests.length;
  const other=createEnterpriseGraphController({...f.ports,config:{...f.ports.config,researchOwner:{...owner,work_id:'another-work'}},
    dispatchNode:async()=>assert.fail('Another owner must not execute')});
  await assert.rejects(other.continuationState(),/checkpoint identity is invalid/);
  assert.equal(f.requests.length,count);assert.equal(f.calls.length,1);await f.controller.close();
});
test('model control calls bind to their exact graph checkpoint without inventing a step',async()=>{
  const f=fixture();
  await f.controller.execute('plan','model-plan-call',plan([node('A')]));
  assert.deepEqual(f.events.find(event=>event.control)?.control,
    {tool_call_id:'model-plan-call',tool_name:'agent_research_plan'});
  // The scheduler's automatic start is a distinct checkpoint, not a model tool.
  assert.equal(f.events.at(-1).control,undefined);
  await f.settle('A');
  assert.equal(f.events.at(-1).control,undefined);
  await f.controller.close();
});
async function accept(f,id){
  let state=await f.controller.readState(),current=state.graph.nodes.find(item=>item.id===id);
  const request=record(current.execute_action_id);request.outputs[0].observation_refs=['obs-'+id];
  const reply=await f.controller.execute('record','record-'+id,request);assert.equal(reply.details.ok,true,JSON.stringify(reply));
  state=await f.controller.readState();current=state.graph.nodes.find(item=>item.id===id);
  const assessed=await f.controller.execute('assess','assess-'+id,{action_id:current.assess_action_id,outcome:'success',
    checks:[{description:'Verify '+id,status:'passed',refs:['obs-'+id],explanation:'Actual observation'}],summary:'Accepted '+id});
  assert.equal(assessed.details.ok,true,JSON.stringify(assessed));
}
test('whole-goal loop retains remaining work across incremental batches and restore before file delivery',async()=>{
  const config={researchRuntime:{graphLimits:limits,delegation:{concurrency:2},isolatedTaskExecution:true,goalDrivenExecution:true}};
  const f=fixture({config}),requirements=[{id:'analysis',kind:'finding',description:'Resolve the independent questions'},
    {id:'report',kind:'artifact',description:'Deliver the requested report'}];
  assert.match(registered(f.controller).agent_research_assess.description,/Omit checks entirely/);
  const initial=await f.controller.execute('plan','goal-plan',{...plan([node('A')]),output_mode:'files',requirements});
  assert.equal(initial.details.ok,true,JSON.stringify(initial));
  assert.deepEqual(initial.details.result.organization.requirements,requirements);
  await f.settle('A');await accept(f,'A');
  const premature={outcome:'limited',delivery_result_refs:[],delivery_product_refs:[],limitations:['Only first task done'],summary:'Partial'};
  assert.equal((await f.controller.finish('premature',premature)).details.ok,false);
  const pending={decision:'continue',summary:'First task does not satisfy the goal',requirements:requirements.map(item=>({id:item.id,status:'open',result_refs:[],explanation:'Requires later work'}))};
  const reviewed=await f.controller.execute('assess','goal-continue',{goal_review:pending});
  assert.equal(reviewed.details.ok,true,JSON.stringify(reviewed));
  assert.equal((await f.controller.finish('still-premature',{...premature,goal_review_ref:reviewed.details.result.organization.review.review_ref})).details.ok,false);
  const follow=id=>node(id,{depends_on:['A'],inputs:[{name:'prior',from:{step_id:'A',slot:'value'}}]});
  assert.equal((await f.controller.execute('revise','goal-expand',{nodes:[follow('B'),follow('C')],rerun:[],reason:'First result supports independent questions'})).details.ok,true);
  assert.deepEqual(f.calls.map(item=>item.node.id),['A','B','C']);
  await f.settle('B');await accept(f,'B');await f.settle('C');await accept(f,'C');
  assert.equal((await f.controller.execute('revise','unreviewed-next',{nodes:[node('X')],rerun:[],reason:'Must first review current goal'})).details.ok,false);
  assert.equal((await f.controller.execute('assess','goal-after-analysis',{goal_review:pending})).details.ok,true);
  const synthesis=node('D',{mode:'synthesis',depends_on:['B','C'],inputs:[{name:'left',from:{step_id:'B',slot:'value'}},{name:'right',from:{step_id:'C',slot:'value'}}],outputs:[{slot:'value',kind:'artifact',description:'Final document'}]});
  await f.controller.execute('revise','goal-report',{nodes:[synthesis],rerun:[],reason:'Accepted analyses support synthesis'});
  const action=f.calls.at(-1).action,product={ref:'goal-report-file',path:'report.md',sha256:'a'.repeat(64),bytes:30,status:'ready',owner,action_id:action.id,attempt_id:'attempt',roles:['primary']};
  await f.settle('D','completed','Saved report',[product]);
  const payload=record(action.id);payload.outputs[0].artifact_refs=[product.ref];payload.outputs[0].observation_refs=['obs-D'];
  await f.controller.execute('record','goal-record-D',payload);
  const state=await f.controller.readState();
  await f.controller.execute('assess','goal-assess-D',{action_id:state.graph.nodes.find(item=>item.id==='D').assess_action_id,outcome:'success',checks:[{description:'Verify D',status:'passed',refs:['obs-D'],explanation:'Inspected actual report'}],summary:'Report accepted'});
  await f.controller.close();
  const restored=createEnterpriseGraphController({...f.ports,dispatchNode:async()=>assert.fail('Accepted tasks must not rerun')});
  const current=await restored.readState({compact:true});
  assert.equal(current.organization.review_current,false);assert.equal(current.graph.goal,'Answer the requested task');
  const result=id=>current.graph.nodes.find(item=>item.id===id).output_bindings[0].result_ref;
  const complete={goal_review:{decision:'complete',summary:'Both findings and actual report accepted',requirements:[
    {id:'analysis',status:'satisfied',result_refs:[result('B'),result('C')],explanation:'Actual analytical results'},
    {id:'report',status:'satisfied',result_refs:[result('D')],explanation:'Saved report inspected'}]}};
  const ready=await restored.execute('assess','goal-complete',complete);assert.equal(ready.details.ok,true,JSON.stringify(ready));
  const ref=ready.details.result.organization.review.review_ref;
  const closed=await restored.finish('goal-finish',{outcome:'success',goal_review_ref:ref,delivery_result_refs:[result('D')],delivery_product_refs:[product.ref],limitations:[],summary:'Whole goal delivered'});
  assert.equal(closed.details.ok,true,JSON.stringify(closed));assert.equal(await restored.continuationState(),null);
  await restored.close();
});
test('a genuinely blocked whole goal stops as execution failure rather than a completed round',async()=>{
  const f=fixture({config:{researchRuntime:{graphLimits:limits,delegation:{concurrency:1},isolatedTaskExecution:true,goalDrivenExecution:true}}});
  await f.controller.execute('plan','blocked-plan',{...plan([node('A')]),requirements:[{id:'answer',kind:'finding',description:'Answer from a required source'}]});
  await f.settle('A');await accept(f,'A');
  const review=await f.controller.execute('assess','blocked-review',{goal_review:{decision:'blocked',summary:'Required input unavailable',requirements:[{id:'answer',status:'blocked',result_refs:[],explanation:'Required observation does not exist',blocker:{kind:'missing_input',explanation:'The supplied source lacks the required facts'}}]}});
  assert.equal(review.details.ok,true,JSON.stringify(review));
  const finished=await f.controller.finish('blocked-finish',{outcome:'failure',goal_review_ref:review.details.result.organization.review.review_ref,delivery_result_refs:[],delivery_product_refs:[],limitations:['Required source facts absent'],summary:'Goal blocked'});
  assert.equal(finished.details.ok,true,JSON.stringify(finished));
  await assert.rejects(()=>f.controller.continuationState(),error=>error.code==='task_goal_blocked');
  await f.controller.close();
});
test('a limited research turn can disclose a missing requested file without being forced into more work',async()=>{
  const f=fixture({config:{researchRuntime:{graphLimits:limits,delegation:{concurrency:1},isolatedTaskExecution:true,lightweightTaskNodes:true,goalDrivenExecution:true}}});
  try{
    const planned=await f.controller.execute('plan','plan',{...plan([node('A')]),output_mode:'files',requirements:[
      {id:'finding',kind:'finding',description:'Analysis'},{id:'report',kind:'artifact',description:'Requested report'}]});
    assert.equal(planned.details.ok,true,JSON.stringify(planned));await f.settle('A');await accept(f,'A');
    const state=await f.controller.readState(),ref=state.graph.results[0].result_ref;
    const review=await f.controller.execute('assess','review',{goal_review:{decision:'limited',requirements:[
      {id:'finding',status:'satisfied',result_refs:[ref],explanation:'Actual analysis'},
      {id:'report',status:'open',result_refs:[],explanation:'Report not produced'}],summary:'Useful analysis for follow-up'}});
    assert.equal(review.details.ok,true,JSON.stringify(review));
    const finish=await f.controller.finish('finish',{outcome:'limited',goal_review_ref:review.details.result.organization.review.review_ref,
      delivery_result_refs:[ref],delivery_product_refs:[],limitations:['Requested report is missing'],summary:'Current analysis delivered; report remains open'});
    assert.equal(finish.details.ok,true,JSON.stringify(finish));assert.equal(await f.controller.continuationState(),null);
  }finally{await f.controller.close();}
});
test('presentation role does not block an explicitly assessed lightweight artifact delivery',async()=>{
  const f=fixture({config:{researchRuntime:{graphLimits:limits,delegation:{concurrency:1},isolatedTaskExecution:true,lightweightTaskNodes:true}}});
  try{
    await f.controller.execute('plan','plan',{...plan([node('A',{outputs:[{slot:'value',kind:'artifact',description:'Requested document'}]})]),output_mode:'files'});
    const action=f.calls[0].action,product={ref:'product-document',path:'context-results/document.md',sha256:'a'.repeat(64),bytes:12,
      roles:['support'],status:'ready',owner,attempt_id:'attempt',action_id:action.id};
    await f.settle('A','completed','Actual document',[product]);
    const recorded=await f.controller.execute('record','record',{action_id:action.id,outcome:'completed',
      outputs:[{slot:'value',artifact_refs:[product.ref],observation_refs:[],summary:'Actual saved document',scope:'Requested scope'}],limitations:[]});
    assert.equal(recorded.details.ok,true,JSON.stringify(recorded));
    let state=await f.controller.readState();
    const assessed=await f.controller.execute('assess','assess',{action_id:state.graph.nodes[0].assess_action_id,outcome:'success',
      checks:[{description:'Verify A',status:'passed',refs:['obs-A'],explanation:'Actual native check'}],summary:'Document assessed'});
    assert.equal(assessed.details.ok,true,JSON.stringify(assessed));state=await f.controller.readState();
    const finished=await f.controller.finish('finish',{outcome:'success',delivery_result_refs:[state.graph.results[0].result_ref],
      delivery_product_refs:[product.ref],limitations:[],summary:'Document delivered'});
    assert.equal(finished.details.ok,true,JSON.stringify(finished));
  }finally{await f.controller.close();}
});
test('exports the explicit application adapter',()=>assert.equal(typeof createEnterpriseGraphController,'function'));
test('isolated task pool rejects native parent work while legacy execution stays available',async()=>{
  const f=fixture({config:{researchRuntime:{graphLimits:limits,delegation:{concurrency:2},isolatedTaskExecution:true}}});
  const rejected=await f.controller.execute('plan','bad',plan([node('P',{execution:'parent'})]));
  assert.equal(rejected.details.ok,false);
  assert.match(JSON.stringify(rejected),/independent task executor/);
  assert.equal(f.requests.length,0);
  const tools=registered(f.controller);
  assert.deepEqual(tools.agent_research_plan.parameters.properties.nodes.items.properties.execution.enum,['delegated']);
  assert.match(tools.agent_research_plan.description,/next evidence-supported/);
  await f.controller.close();
});
test('isolated task pool expands discovery then concurrent work then synthesis from accepted results',async()=>{
  const f=fixture({config:{researchRuntime:{graphLimits:limits,delegation:{concurrency:2},isolatedTaskExecution:true}}});
  const discovery=node('A');
  await f.controller.execute('plan','initial',plan([discovery]));
  assert.deepEqual(f.calls.map(item=>item.node.id),['A']);
  await f.settle('A');await accept(f,'A');
  // No future analyses or synthesis existed before the discovery result.
  assert.equal((await f.controller.readState()).graph.nodes.length,1);
  const consumer=id=>node(id,{depends_on:['A'],inputs:[{name:'discovery',from:{step_id:'A',slot:'value'}}]});
  const first=[discovery,consumer('B'),consumer('C')];
  const expanded=await f.controller.execute('revise','expand',{nodes:first.slice(1),rerun:[],reason:'Accepted discovery establishes two independent questions'});
  assert.equal(expanded.details.ok,true,JSON.stringify(expanded));
  assert.deepEqual(f.calls.map(item=>item.node.id),['A','B','C']);
  assert.deepEqual((await f.controller.readState()).graph.nodes.map(item=>item.id),['A','B','C']);
  assert.equal((await f.controller.execute('revise','rewrite-started',{nodes:[{...discovery,purpose:'Changed scope'}],rerun:[],reason:'Invalid retrospective edit'})).details.ok,false);
  assert.equal((await f.controller.execute('revise','duplicate',{nodes:[consumer('X'),consumer('X')],rerun:[],reason:'Invalid duplicates'})).details.ok,false);
  assert.deepEqual(await f.controller.execute('revise','expand',{nodes:first.slice(1),rerun:[],reason:'Accepted discovery establishes two independent questions'}),expanded);
  assert.deepEqual(f.calls.map(item=>item.node.id),['A','B','C']);
  assert.deepEqual(f.calls[1].action.input_bindings.map(item=>item.result_ref),f.calls[2].action.input_bindings.map(item=>item.result_ref));
  await f.settle('B');await accept(f,'B');await f.settle('C');await accept(f,'C');
  assert.notEqual(f.controller.status.phase,'done');
  const next=JSON.parse((await f.controller.continuationState()).prompt);
  assert.match(next.instruction,/empty task pool is not goal completion/);
  const synthesis=node('D',{mode:'synthesis',depends_on:['B','C'],inputs:[
    {name:'left',from:{step_id:'B',slot:'value'}},{name:'right',from:{step_id:'C',slot:'value'}}]});
  assert.equal((await f.controller.execute('revise','synthesis',{nodes:[synthesis],rerun:[],reason:'Accepted results now support synthesis'})).details.ok,true);
  assert.deepEqual(f.calls.map(item=>item.node.id),['A','B','C','D']);
  await f.settle('D');await accept(f,'D');
  const state=await f.controller.readState(),selected=state.graph.nodes.find(item=>item.id==='D').output_bindings[0].result_ref;
  assert.equal((await f.controller.finish('finish',{outcome:'success',delivery_result_refs:[selected],delivery_product_refs:[],limitations:[],summary:'Accepted synthesis'})).details.ok,true);
  assert.equal(await f.controller.continuationState(),null);await f.controller.close();
});
test('compact control context retains exact actionable contracts without future definitions or private grants',async()=>{
  const f=fixture();
  const preparation=node('P',{execution:'parent',purpose:'Inspect source structure only',
    instruction:'Long retained execution method '.repeat(80),checks:['Verify exact schema label'],
    outputs:[{slot:'schema',kind:'artifact',description:'Save reusable source schema'}]});
  const downstream=node('D',{depends_on:['P'],purpose:'Independent downstream analysis',
    inputs:[{name:'schema',from:{step_id:'P',slot:'schema'}}]});
  const reply=await f.controller.execute('plan','plan',plan([preparation,downstream]));
  const expected={step_id:'P',purpose:preparation.purpose,questions:preparation.questions,
    expected_outputs:preparation.expected_outputs,outputs:preparation.outputs,checks:preparation.checks};
  assert.deepEqual(reply.details.result.graph.action_contracts,[expected]);
  await f.controller.execute('start','start',{step_id:'P',kind:'execute'});
  const state=await f.controller.readState({compact:true});
  assert.deepEqual(state.graph.action_contracts,[expected]);
  assert.deepEqual(JSON.parse((await f.controller.continuationState()).prompt).graph.action_contracts,[expected]);
  assert.doesNotMatch(JSON.stringify(state.graph.action_contracts),/Independent downstream analysis|Long retained execution method|handle-/);
  const token=await f.controller.beginTool({toolCallId:'read',toolName:'read'});
  await f.controller.completeTool(token,{details:{native_research_source:{source_ref:'obs-P'}}});
  const recorded=await f.controller.execute('record','record',{action_id:state.graph.nodes[0].execute_action_id,
    outcome:'limited',outputs:[],limitations:['Schema file not saved']});
  assert.equal(recorded.details.ok,true,JSON.stringify(recorded));
  assert.deepEqual(recorded.details.result.graph.action_contracts,[expected]);
  recorded.details.result.graph.action_contracts[0].checks[0]='Mutated caller copy';
  assert.deepEqual((await f.controller.readState({compact:true})).graph.action_contracts,[expected]);
  const assessed=await f.controller.execute('assess','assess',{action_id:recorded.details.result.graph.nodes[0].assess_action_id,
    outcome:'limited',checks:[{description:preparation.checks[0],status:'not_run',refs:[],explanation:'Schema not saved'}],summary:'Missing output'});
  assert.equal(assessed.details.ok,true,JSON.stringify(assessed));
  assert.deepEqual(assessed.details.result.graph.action_contracts,[]);
  await f.controller.close();
});
test('control acknowledgements reference retained graph definitions instead of retransmitting them',async()=>{
  const f=fixture();const definition='Retained detailed method '.repeat(80);
  const reply=await f.controller.execute('plan','plan',plan([node('A',{instruction:definition})]));
  assert.equal(reply.details.ok,true);
  assert.ok(reply.details.result.graph.graph_ref);
  assert.equal(reply.content[0].text.includes(definition),false);
  assert.equal((await f.controller.readState()).graph.nodes[0].instruction,definition);
  await f.settle('A','completed','Retained native result payload');
  assert.equal(JSON.stringify(await f.controller.readState({compact:true})).includes('Retained native result payload'),false);
  assert.equal((await f.controller.readState()).pending_proposals[0].output,'Retained native result payload');
  await f.controller.close({reason:'Done'});
});
test('continuation sends only new proposal bodies once and retains explicit recovery across sibling progress',async()=>{
  const f=fixture(),instruction='Exact retained method '.repeat(100),outputA='Retained native A '.repeat(500),outputB='Retained native B '.repeat(500);
  let restored;
  try{
    await f.controller.execute('plan','plan',plan([node('A',{instruction}),node('B')]));
    await f.settle('A','completed',outputA);
    const first=JSON.parse((await f.controller.continuationState()).prompt);
    assert.equal(JSON.stringify(first).includes(instruction),false);
    assert.equal(first.pending_proposals.find(item=>item.step_id==='A').output,outputA);
    const repeated=JSON.parse((await f.controller.continuationState()).prompt);
    const a=repeated.pending_proposals.find(item=>item.step_id==='A');
    assert.ok(a.action_id);assert.deepEqual(a.receipt_refs,['obs-A']);assert.equal(a.output,undefined);
    assert.ok(Buffer.byteLength(JSON.stringify(repeated))<Buffer.byteLength(JSON.stringify(first))/2);
    await f.settle('B','completed',outputB);
    const sibling=JSON.parse((await f.controller.continuationState()).prompt);
    assert.equal(sibling.pending_proposals.find(item=>item.step_id==='A').output,undefined);
    assert.equal(sibling.pending_proposals.find(item=>item.step_id==='B').output,outputB);
    assert.match(sibling.instruction,/agent_research_read/);
    // Explicit full overview recovery remains usable after model context compaction.
    const full=await f.controller.readState();assert.equal(full.graph.nodes[0].instruction,instruction);
    assert.equal(full.pending_proposals.find(item=>item.step_id==='A').output,outputA);
    assert.equal((await f.controller.readProposal(a.action_id)).output,outputA);
    restored=createEnterpriseGraphController({...f.ports,dispatchNode:async()=>assert.fail('retained proposal must not execute again')});
    const recovery=JSON.parse((await restored.continuationState()).prompt);
    assert.equal(recovery.pending_proposals.find(item=>item.step_id==='A').output,outputA);
    assert.equal(recovery.pending_proposals.find(item=>item.step_id==='B').output,outputB);
    const recoveredAgain=JSON.parse((await restored.continuationState()).prompt);
    assert.ok(recoveredAgain.pending_proposals.every(item=>item.output===undefined));
    assert.equal(f.calls.length,2);
  }finally{await restored?.close();await f.controller.close();}
});
test('new parent inspect call retries a retained host failure at the same checkpoint',async()=>{
  const root=await mkdtemp(join(tmpdir(),'graph-inspect-retry-'));await mkdir(join(root,'responses'));
  const requests=[],controls=[];
  const canonical=value=>Array.isArray(value)?value.map(canonical):value&&typeof value==='object'?
    Object.fromEntries(Object.keys(value).sort().map(key=>[key,canonical(value[key])])):value;
  const client=createGraphContextClient({graphContextPath:root,researchTaskId:'task',researchAttemptId:'attempt',researchOwner:owner},{emit:async request=>{
    requests.push(request);
    const product={ref:'frozen-report',path:'context-results/report.txt',sha256:'a'.repeat(64),bytes:12,roles:['primary'],status:'ready',
      owner,attempt_id:'attempt',action_id:request.action_id};
    const request_sha256=createHash('sha256').update(JSON.stringify(canonical(request))).digest('hex');
    await writeFile(join(root,'responses',request.request_id+'.json'),JSON.stringify({schema:'capstone-enterprise-graph-context/1',
      request_id:request.request_id,request_sha256,ok:requests.length>1,
      result:{ready:true,products:[product],selections:[{path:'report.txt',ref:product.ref}]}}));
  }});
  const f=fixture({ports:{inspectProducts:({action,products},control)=>{
    controls.push(control);
    return client.freeze({action,checkpoint:{ref:'same-committed-checkpoint',revision:2},selection:{products}},control);
  }}});
  try{
    await f.controller.execute('plan','plan',plan([node('A',{execution:'parent'})]));
    await f.controller.execute('start','start',{step_id:'A'});
    const action_id=(await f.controller.readState()).graph.nodes[0].execute_action_id,payload={action_id,products:[{path:'report.txt',role:'primary'}]};
    assert.equal((await f.controller.inspect('inspect-failed',payload)).details.ok,false);
    assert.equal((await f.controller.inspect('inspect-failed',payload)).details.ok,false);assert.equal(requests.length,1);
    const recovered=await f.controller.inspect('inspect-retry',payload);
    assert.equal(recovered.details.ok,true,JSON.stringify(recovered));
    assert.equal(controls.at(-1).requestKey,'inspect-retry');
    assert.equal(requests.length,2);assert.notEqual(requests[0].request_id,requests[1].request_id);
    assert.deepEqual(requests[0].checkpoint,requests[1].checkpoint);
    assert.deepEqual(await f.controller.inspect('inspect-retry',payload),recovered);assert.equal(requests.length,2);
  }finally{await f.controller.close();await rm(root,{recursive:true,force:true});}
});
test('delegated artifacts reject unknown or duplicate presentation roles before admission',async()=>{
  for(const roles of [[],['primary','invalid-role'],['primary','primary']]){
    const f=fixture();await f.controller.execute('plan','plan',plan([node('A')]));
    const action=f.calls[0].action;
    const product={ref:'bad-product',path:'report.md',sha256:'a'.repeat(64),bytes:30,
      status:'ready',owner,action_id:action.id,attempt_id:'attempt',roles};
    await f.settle('A','completed','Actual file',[product]);
    assert.deepEqual(JSON.parse(f.view.state.notes.at(-1).text).products,[]);
    await assert.rejects(f.controller.close({reason:'Invalid inspection must remain unconfirmed'}));
  }
});
test('a sibling artifact grant cannot substitute for a selected result lineage',async()=>{
  const outputs=[{slot:'value',kind:'artifact',description:'Actual file'}],prior=fixture();
  await prior.controller.execute('plan','plan',plan([node('X',{outputs})]));
  const oldAction=prior.calls[0].action;
  const artifact={ref:'shared',path:'report.md',sha256:'a'.repeat(64),bytes:30,status:'ready',owner,
    action_id:oldAction.id,attempt_id:'attempt',roles:['support']};
  await prior.settle('X','completed','Actual file',[artifact]);
  const original=record(oldAction.id);original.outputs[0].observation_refs=['obs-X'];original.outputs[0].artifact_refs=['shared'];
  assert.equal((await prior.controller.execute('record','record-X',original)).details.ok,true);
  assert.equal((await prior.controller.execute('assess','assess-X',{
    action_id:(await prior.controller.readState()).graph.nodes[0].assess_action_id,outcome:'success',
    checks:[{description:'Verify X',status:'passed',refs:['obs-X'],explanation:'Observed'}],summary:'Accepted'})).details.ok,true);
  const external=JSON.parse(prior.view.state.notes.at(-1).text).snapshot.results[0];await prior.controller.close();
  const f=fixture({config:{researchTaskId:'task',researchOwner:owner,researchAttemptId:'attempt',researchResults:[external],
    researchRuntime:{graphLimits:limits,delegation:{concurrency:2}}},
    ports:{resolveInputs:async action=>({manifests:action.input_bindings.map(()=>external),handles:[]})}});
  await f.controller.execute('plan','plan',plan([node('B',{outputs}),node('S',{outputs,mode:'synthesis',
    inputs:[{name:'old',result_ref:external.result_ref}]})]));
  for(const id of ['B','S']){
    const action=f.calls.find(call=>call.node.id===id).action;
    await f.settle(id,'completed','Actual output',id==='B'?[{...artifact,action_id:action.id}]:[]);
    const payload=record(action.id);payload.outputs[0].observation_refs=['obs-'+id];payload.outputs[0].artifact_refs=['shared'];
    assert.equal((await f.controller.execute('record','record-'+id,payload)).details.ok,true);
    assert.equal((await f.controller.execute('assess','assess-'+id,{
      action_id:(await f.controller.readState()).graph.nodes.find(item=>item.id===id).assess_action_id,
      outcome:'success',checks:[{description:'Verify '+id,status:'passed',refs:['obs-'+id],explanation:'Observed'}],summary:'Accepted'})).details.ok,true);
  }
  const selected=(await f.controller.readState()).graph.results.find(item=>item.producer.step_id==='S').result_ref;
  assert.equal((await f.controller.finish('finish',{outcome:'success',delivery_result_refs:[selected],
    delivery_product_refs:['shared'],limitations:[],summary:'Delivered'})).details.ok,false);
  await f.controller.close();
});
test('commits A/B starts before concurrent dispatch and releases C only after model acceptance',async()=>{
  const f=fixture();const reply=await f.controller.execute('plan','plan',plan(graph()));assert.equal(reply.details.ok,true);
  assert.deepEqual(f.calls.map(item=>item.node.id),['A','B']);
  for(const call of f.calls){const saved=JSON.parse(f.view.state.notes.find(item=>item.note_id===call.checkpoint.ref).text);
    assert.equal(saved.snapshot.node_states[call.node.id].phase,'executing');assert.ok(saved.dispatches.some(item=>item.action_id===call.action.id&&item.status==='intent'));}
  await f.settle('A');assert.equal(f.calls.length,2);await accept(f,'A');
  assert.deepEqual(f.calls.map(item=>item.node.id),['A','B','C']);
  assert.ok(!f.calls.some(item=>item.node.id==='D'));
  const c=f.calls[2];assert.equal(c.inputs.manifests[0].result_ref,c.action.input_bindings[0].result_ref);
  assert.ok(Object.isFrozen(c.inputs.manifests[0]));assert.equal(c.inputs.handles[0].immutable,true);
  await f.settle('B');await accept(f,'B');assert.equal(f.calls.at(-1).node.id,'D');
  await f.controller.close({reason:'Test finished'});
});
test('definite start rejection emits no start and does not dispatch',async()=>{
  let f;f=fixture({ports:{onProgress:event=>{f.events.push(event);if(event.events.some(item=>item.kind==='graph_committed'))f.reject();}}});
  await f.controller.execute('plan','plan',plan([node('A')]));
  assert.equal(f.calls.length,0);assert.equal(f.events.filter(event=>event.events.some(item=>item.kind==='node_started')).length,0);
});
test('unknown start ack retains the exact request and dispatches at most once after recovery',async()=>{
  let f;f=fixture({ports:{onProgress:event=>{f.events.push(event);if(event.events.some(item=>item.kind==='graph_committed'))f.lose();}}});
  await f.controller.execute('plan','plan',plan([node('A')]));assert.equal(f.calls.length,0);
  assert.equal((await f.controller.readState()).update_pending,true);
  const request=f.requests.at(-1);await f.controller.recoverPending();
  assert.deepEqual(f.requests.at(-1),request);assert.equal(f.calls.length,1);
  await f.controller.recoverPending();assert.equal(f.calls.length,1);await f.controller.close({reason:'Test finished'});
});
test('restored executing intent becomes unknown and is never dispatched again',async()=>{
  const f=fixture();await f.controller.execute('plan','plan',plan([node('A')]));
  const restored=createEnterpriseGraphController({...f.ports,dispatchNode:async()=>{throw Error('Must not restart');}});
  const state=await restored.readState();assert.equal(state.graph.nodes[0].settled_status,'unknown');assert.equal(state.graph.nodes[0].phase,'executed');
  assert.equal((await restored.execute('plan','plan',plan([node('A')]))).details.ok,true);
  await restored.close({reason:'Restored test finished'});await f.controller.close({reason:'Test finished'});
});
test('lost restore acknowledgement cannot relaunch another old executing branch',async()=>{
  const f=fixture();await f.controller.execute('plan','plan',plan([node('A'),node('B')]));
  const reruns=[];
  const restored=createEnterpriseGraphController({...f.ports,dispatchNode:async request=>{
    reruns.push(request.node.id);return {status:'unknown',receipts:[],products:[],output:'Must not replay'};
  }});
  f.lose();await assert.rejects(restored.readState(),{code:'research_update_not_confirmed'});
  await restored.recoverPending();await tick();
  assert.deepEqual(reruns,[]);
  assert.deepEqual((await restored.readState()).graph.nodes.map(item=>item.settled_status),['unknown','unknown']);
  await restored.close({reason:'Restored test finished'});await f.controller.close({reason:'Test finished'});
});
test('parent tools keep exact action across sibling commits and failed tools cannot settle as success',async()=>{
  const f=fixture();await f.controller.execute('plan','plan',plan([node('parent',{execution:'parent'}),node('B')]));
  await f.controller.execute('start','parent-start',{step_id:'parent'});
  const token=await f.controller.beginTool({toolCallId:'read-parent',toolName:'read'});await f.settle('B');
  await f.controller.completeTool(token,{content:[],details:{native_research_source:{source_ref:'parent-source'}}});
  const state=await f.controller.readState(),action=state.graph.nodes.find(item=>item.id==='parent').execute_action_id;
  const payload=record(action);payload.outputs[0].observation_refs=['parent-source'];
  assert.equal((await f.controller.execute('record','parent-record',payload)).details.ok,true);
  const saved=JSON.parse(f.view.state.notes.at(-1).text);assert.equal(saved.receipts.find(item=>item.ref==='parent-source').action_id,action);
  await assert.rejects(()=>f.controller.beginTool({toolCallId:'manual',toolName:'agent_delegate'}));await f.controller.close({reason:'Test finished'});
});
test('commands replay the original committed output without another transition',async()=>{
  const f=fixture();const payload=plan([node('parent',{execution:'parent'})]);const first=await f.controller.execute('plan','same',payload);
  const count=f.requests.length;assert.deepEqual(await f.controller.execute('plan','same',payload),first);assert.equal(f.requests.length,count);
  assert.equal((await f.controller.execute('plan','same',{...payload,goal:'Changed'})).details.ok,false);await f.controller.close({reason:'Test finished'});
});
test('progress binds only committed exact public projection and hides private output',async()=>{
  const f=fixture();await f.controller.execute('plan','plan',plan([node('A')]));await f.settle('A','completed','/private/SECRET '+ 'x'.repeat(10000));
  for(const event of f.events){const note=f.view.state.notes.find(item=>item.note_id===event.checkpoint.ref),saved=JSON.parse(note.text),{checkpoint,...payload}=event;
    assert.deepEqual(saved.public_progress,payload);assert.equal(event.type,'enterprise_graph_progress');assert.equal(event.task_id,'task');
    assert.ok(!JSON.stringify(event).includes('SECRET'));assert.ok(!JSON.stringify(event.graph).includes('runtime.checkpoint.'));}
  const state=await f.controller.readState();assert.ok(!JSON.stringify(state).includes('SECRET'));assert.ok(Buffer.byteLength(JSON.stringify(state))<=limits.publicBytes);
  await f.controller.close({reason:'Test finished'});
});
test('close cancels and drains all owned jobs',async()=>{
  let settled=false;const f=fixture({ports:{dispatchNode:async(_,{signal})=>new Promise(resolve=>signal.addEventListener('abort',()=>{settled=true;resolve({status:'cancelled',receipts:[],products:[],output:''});},{once:true}))}});
  await f.controller.execute('plan','plan',plan([node('A')]));await f.controller.close({reason:'Stop'});assert.equal(settled,true);
  assert.equal((await f.controller.readState()).graph.nodes[0].settled_status,'cancelled');
});
test('a direct answer without an accepted task graph needs no organization continuation',async()=>{
  for(const goalDrivenExecution of [false,true]){
    const f=fixture({config:{researchTaskId:'task',researchOwner:owner,researchAttemptId:'attempt',researchSources:[],researchRuntime:{graphLimits:limits,delegation:{concurrency:3},isolatedTaskExecution:true,lightweightTaskNodes:true,nodeReviewMode:'advisory',goalDrivenExecution}}});
    assert.equal(await f.controller.continuationState(),null);
    assert.equal(f.requests.length,0);
    assert.equal(f.calls.length,0);
    await f.controller.close();
  }
});
test('no accepted graph outcome is terminal until an explicit finish commits',async()=>{
  const f=fixture();await f.controller.execute('plan','plan',plan([node('A')]));await f.settle('A');await accept(f,'A');
  assert.notEqual(f.controller.status.phase,'done');assert.ok(await f.controller.continuationState());
  const state=await f.controller.readState();const resultRef=state.graph.results[0].result_ref;
  const result=await f.controller.finish('finish',{outcome:'success',delivery_result_refs:[resultRef],delivery_product_refs:[],limitations:[],summary:'Actual final answer'});
  assert.equal(result.details.ok,true);assert.equal(f.controller.status.phase,'done');assert.equal(await f.controller.continuationState(),null);
  await f.controller.close({reason:'Test finished'});
});
test('strict SDK tools bind operation without permitting host settlement',()=>{
  const f=fixture(),tools=[];f.controller.register({registerTool:tool=>tools.push(tool)});
  assert.deepEqual(tools.map(item=>item.name),['agent_research_plan','agent_research_start','agent_research_record','agent_research_assess','agent_research_revise','agent_research_resolve','agent_research_inspect','agent_research_finish']);
  assert.ok(tools.every(item=>item.parameters.additionalProperties===false));
});
test('capacity queue starts an independent node when a native job returns before assessment',async()=>{
  const f=fixture({config:{researchTaskId:'task',researchOwner:owner,researchAttemptId:'attempt',researchRuntime:{graphLimits:limits,delegation:{concurrency:1}}}});
  await f.controller.execute('plan','plan',plan([node('A'),node('B')]));assert.deepEqual(f.calls.map(item=>item.node.id),['A']);
  await f.settle('A');await tick();assert.deepEqual(f.calls.map(item=>item.node.id),['A','B']);await f.controller.close({reason:'Done'});
});
test('sibling native proposals survive an unconfirmed settlement and exact recovery',async()=>{
  const f=fixture();await f.controller.execute('plan','plan',plan([node('A'),node('B')]));f.lose();
  await f.settle('A');await f.settle('B');assert.equal((await f.controller.readState()).update_pending,true);
  await f.controller.recoverPending();const state=await f.controller.readState();
  assert.deepEqual(state.graph.nodes.map(item=>item.settled_status),['completed','completed']);
  const saved=JSON.parse(f.view.state.notes.at(-1).text);assert.deepEqual(saved.receipts.map(item=>item.ref),['obs-A','obs-B']);
  await f.controller.close({reason:'Done'});
});
test('oversized native output keeps actual completed settlement and receipts with explicit capacity error',async()=>{
  const f=fixture();await f.controller.execute('plan','plan',plan([node('A')]));await f.settle('A','completed','x'.repeat(limits.resultBytes+1));
  const state=await f.controller.readState();assert.equal(state.graph.nodes[0].settled_status,'completed');
  assert.equal(state.pending_proposals[0].capacity_error.dimension,'graph_child_proposal_bytes');
  const saved=JSON.parse(f.view.state.notes.at(-1).text);assert.equal(saved.receipts[0].ref,'obs-A');
  await assert.rejects(()=>f.controller.readProposal(f.calls[0].action.id),error=>error.code==='research_capacity_exceeded');
  await f.controller.close({reason:'Done'});
});
test('private exact proposal and bounded public result preserve real output without leaking paths',async()=>{
  const f=fixture();await f.controller.execute('plan','plan',plan([node('A')]));await f.settle('A','completed','Answer at /private/internal/report.csv; Bearer synthetic-token');
  assert.equal((await f.controller.readProposal(f.calls[0].action.id)).output,'Answer at /private/internal/report.csv; Bearer synthetic-token');
  const publicValue=JSON.stringify(await f.controller.readState());assert.ok(!publicValue.includes('/private/'));assert.ok(!publicValue.includes('synthetic-token'));
  assert.ok(publicValue.includes('Answer at'));await f.controller.close({reason:'Done'});
});
test('continuation waits for one owned durable job rather than returning a polling prompt',async()=>{
  const f=fixture();await f.controller.execute('plan','plan',plan([node('A'),node('B')]));let resumed=false;
  const wait=f.controller.continuationState().then(value=>{resumed=true;return value;});await tick();assert.equal(resumed,false);
  await f.settle('A');assert.ok((await wait).prompt.includes('obs-A'));assert.equal((await f.controller.readState()).graph.nodes[1].phase,'executing');
  await f.controller.close({reason:'Done'});
});
test('checkpoint wakes do not resume the planner while only children remain actionable',async()=>{
  const f=fixture();await f.controller.execute('plan','plan',plan([node('A')]));let resumed=false;
  const wait=f.controller.continuationState().then(value=>{resumed=true;return value;});await tick();
  const added=await f.controller.execute('revise','independent',{nodes:[node('A'),node('B')],reason:'Independent work',rerun:[]});
  assert.equal(added.details.ok,true,JSON.stringify(added));await tick();
  assert.equal(resumed,false,'a checkpoint pulse is not a settled child result');
  await f.settle('A');assert.ok((await wait).prompt.includes('obs-A'));
  await f.controller.close({reason:'Done'});
});
test('planner overview waits for an actionable return and remains cancellable',async()=>{
  const f=fixture();await f.controller.execute('plan','plan',plan([node('A')]));
  try{
    let resumed=false;const abort=new AbortController();
    const cancelled=f.controller.waitForDecision({signal:abort.signal});
    abort.abort(new DOMException('Stop','AbortError'));await assert.rejects(cancelled,{name:'AbortError'});
    const pending=f.controller.waitForDecision().then(()=>{resumed=true;});await tick();
    assert.equal(resumed,false,'An overview request must not produce repeated polling responses');
    await f.settle('A');await pending;assert.equal(resumed,true);
    assert.equal((await f.controller.readState()).pending_proposals[0].step_id,'A');
  }finally{await f.controller.close({reason:'Done'});}
});
test('failed parent native work cannot be recorded completed',async()=>{
  const f=fixture();await f.controller.execute('plan','plan',plan([node('P',{execution:'parent'})]));await f.controller.execute('start','start',{step_id:'P'});
  const token=await f.controller.beginTool({toolCallId:'bad-read',toolName:'read'});f.controller.endTool(token,undefined,new Error('Actual read failed'));
  const action=(await f.controller.readState()).graph.nodes[0].execute_action_id;
  assert.equal((await f.controller.execute('record','bad-record',record(action))).details.ok,false);
  assert.equal((await f.controller.readState()).graph.nodes[0].phase,'executing');
  assert.equal((await f.controller.execute('record','failed-record',{action_id:action,outcome:'failed',outputs:[],limitations:['Native read failed']})).details.ok,true);
  assert.equal((await f.controller.readState()).graph.nodes[0].settled_status,'failed');await f.controller.close({reason:'Done'});
});
test('all mechanical record rejection preserves the executing parent lease and saved grants',async()=>{
  let product;const f=fixture({ports:{inspectProducts:async({productRefs,products})=>productRefs?{ready:true,products}:
    {ready:true,products:[product],selections:[{path:'wide.parquet',ref:product.ref}]}}});
  await f.controller.execute('plan','plan',plan([node('P',{execution:'parent',outputs:[{slot:'summary',kind:'observation',description:'Observed summary'},
    {slot:'wide',kind:'artifact',description:'Saved reusable table'}]})]));
  await f.controller.execute('start','start',{step_id:'P'});
  const token=await f.controller.beginTool({toolCallId:'native-compute',toolName:'bash'});
  await f.controller.completeTool(token,{details:{native_research_source:{source_ref:'obs-parent'}}});
  product={ref:'saved-wide',path:'context-results/wide.parquet',roles:['support'],sha256:'a'.repeat(64),bytes:593336,status:'ready',owner,attempt_id:'attempt',action_id:token.action.id};
  const inspect={action_id:token.action.id,products:[{path:'wide.parquet',role:'support'}]};
  assert.equal((await f.controller.inspect('inspect-first',inspect)).details.ok,true);
  const valid={action_id:token.action.id,outcome:'completed',outputs:[{slot:'summary',observation_refs:['obs-parent'],artifact_refs:[],summary:'Actual summary',scope:'Assigned data'},
    {slot:'wide',observation_refs:['obs-parent'],artifact_refs:[product.ref],summary:'Reusable table',scope:'Same computation'}],limitations:[]};
  const expected=[['missing_output_slots','outputs'],['missing_output_slots','outputs'],['duplicate_output_slot','outputs[1].slot'],
    ['missing_kind_content','outputs[1].artifact_refs'],['unadmitted_reference','outputs[0].observation_refs'],
    ['unadmitted_reference','outputs[1].artifact_refs'],['duplicate_reference','outputs[1].artifact_refs']];let rejectedIndex=0;
  for(const change of [item=>item.outputs.pop(),item=>item.outputs[1].slot='undeclared',item=>item.outputs[1].slot='summary',
    item=>item.outputs[1].artifact_refs=[],item=>item.outputs[0].observation_refs=['foreign-observation'],
    item=>item.outputs[1].artifact_refs=['foreign-product'],item=>item.outputs[1].artifact_refs.push(product.ref)]){
    const wrong=structuredClone(valid);change(wrong);const before=f.view,events=f.events.length,requests=f.requests.length;
    const reply=await f.controller.execute('record','rejected-'+requests+'-'+JSON.stringify(wrong).length,wrong);
    assert.equal(reply.details.ok,false);const diagnostic=reply.details.error.record_feedback;
    const [code,field]=expected[rejectedIndex++];assert.equal(diagnostic.code,code);assert.equal(diagnostic.field,field);
    assert.equal(diagnostic.action_id,token.action.id);assert.equal(reply.details.error.category,'rejected');
    if(code==='missing_output_slots')assert.deepEqual(diagnostic.missing_slots,{values:['wide'],total:1,omitted:0});
    if(diagnostic.valid_refs)assert.deepEqual(diagnostic.valid_refs,{observation_refs:{values:['obs-parent'],total:1,omitted:0},
      artifact_refs:{values:['saved-wide'],total:1,omitted:0}});
    assert.doesNotMatch(JSON.stringify(reply),/foreign-observation|foreign-product|private\/|undeclared/);
    assert.deepEqual(f.view,before);assert.equal(f.events.length,events);assert.equal(f.requests.length,requests);
    const current=(await f.controller.readState()).graph.nodes[0];assert.equal(current.phase,'executing');assert.equal(current.execute_action_id,token.action.id);assert.deepEqual(current.output_bindings,[]);
  }
  assert.equal((await f.controller.inspect('inspect-after-rejection',inspect)).details.ok,true);
  assert.equal((await f.controller.execute('record','record-corrected',valid)).details.ok,true);
  const saved=JSON.parse(f.view.state.notes.at(-1).text);assert.equal(saved.snapshot.executions.length,1);assert.equal(saved.snapshot.executions[0].execution_revision,1);
  assert.deepEqual(saved.snapshot.executions[0].record,valid);assert.equal(saved.snapshot.results.length,2);assert.deepEqual(saved.products,[product]);assert.equal(f.calls.length,0);
  await f.controller.close();
});
test('parent record preview detaches command and unknown real writes recover their exact identity',async()=>{
  for(const mode of ['detached','settlement-unknown','record-unknown']){
    const f=fixture();await f.controller.execute('plan','plan',plan([node('P',{execution:'parent'})]));await f.controller.execute('start','start',{step_id:'P'});
    const token=await f.controller.beginTool({toolCallId:'native',toolName:'read'});await f.controller.completeTool(token,{details:{native_research_source:{source_ref:'obs-parent'}}});
    const payload=record(token.action.id);payload.outputs[0].observation_refs=['obs-parent'];const original=structuredClone(payload);
    let reply;
    if(mode==='detached'){
      const gate=f.hold(),run=f.controller.execute('record','record-parent',payload);await gate.entered.promise;
      payload.outputs[0].observation_refs=['foreign-after-await'];payload.outputs[0].summary='Mutated caller text';gate.release.resolve();reply=await run;
    }else{
      if(mode==='settlement-unknown')f.lose();else f.loseCommand('record-parent');
      reply=await f.controller.execute('record','record-parent',payload);assert.equal(reply.details.ok,false);assert.equal(reply.details.error.category,'unknown');
      assert.equal(reply.details.error.record_feedback,undefined);assert.equal(reply.details.error.recovery,'recover_exact_request');
      const requests=f.requests.length;await tick();assert.equal(f.requests.length,requests);assert.equal(f.calls.length,0);
      await f.controller.recoverPending();reply=await f.controller.execute('record','record-parent',payload);
    }
    assert.equal(reply.details.ok,true,JSON.stringify(reply));const saved=JSON.parse(f.view.state.notes.at(-1).text);
    assert.deepEqual(saved.snapshot.executions[0].record,original);assert.equal(saved.snapshot.executions.length,1);assert.equal(saved.snapshot.results.length,1);
    assert.equal(f.events.flatMap(item=>item.events).filter(item=>item.kind==='node_execution_settled').length,1);
    assert.equal(f.events.flatMap(item=>item.events).filter(item=>item.kind==='node_output_committed').length,1);
    const count=f.requests.length;assert.deepEqual(await f.controller.execute('record','record-parent',original),reply);assert.equal(f.requests.length,count);
    if(mode!=='detached'){
      const identity=f.requests.find(item=>{const id=JSON.parse(item.request.changes.notes.at(-1).text).command_id;
        return mode==='record-unknown'?id==='record-parent':id.startsWith('parent-settle-');}).id;
      const attempts=f.requests.filter(item=>item.id===identity);assert.equal(attempts.length,2);assert.deepEqual(attempts[0].request,attempts[1].request);
    }
    await f.controller.close();
  }
});
test('record correction hints count omitted refs without widening the public reply budget',async()=>{
  const f=fixture({config:{researchRuntime:{graphLimits:{...limits,publicBytes:4000},delegation:{concurrency:2}}}});
  await f.controller.execute('plan','plan',plan([node('P',{execution:'parent'})]));
  await f.controller.execute('start','start',{step_id:'P'});let action;
  for(let index=0;index<20;index++){
    const token=await f.controller.beginTool({toolCallId:'native-'+index,toolName:'read'});action=token.action;
    await f.controller.completeTool(token,{details:{native_research_source:{source_ref:'obs-'+index+'-'+ 'x'.repeat(180)}}});
  }
  const before=f.view,count=f.requests.length,payload=record(action.id);payload.outputs[0].observation_refs=['foreign-observation'];
  const reply=await f.controller.execute('record','invalid-bounded',payload),feedback=reply.details.error.record_feedback;
  assert.equal(reply.details.ok,false);assert.equal(feedback.code,'unadmitted_reference');
  const refs=feedback.valid_refs.observation_refs;assert.equal(refs.total,20);assert.ok(refs.omitted>0);
  assert.equal(refs.values.length+refs.omitted,refs.total);assert.equal(feedback.valid_refs.artifact_refs.total,0);
  assert.ok(Buffer.byteLength(JSON.stringify(reply))<=4000);assert.match(reply.content[0].text,/omitted as counted/);
  assert.doesNotMatch(JSON.stringify(reply),/foreign-observation/);assert.deepEqual(f.view,before);assert.equal(f.requests.length,count);
  assert.equal((await f.controller.readState()).graph.nodes[0].phase,'executing');
  await f.controller.close();
});
test('restore and old or new command IDs preserve an identical retained incomplete completed record',async()=>{
  const f=fixture();await f.controller.execute('plan','plan',plan([node('P',{execution:'parent',outputs:[{slot:'value',kind:'observation',description:'Summary'},
    {slot:'wide',kind:'artifact',description:'Reusable data'}]})]));await f.controller.execute('start','start',{step_id:'P'});
  const token=await f.controller.beginTool({toolCallId:'native-old',toolName:'read'});await f.controller.completeTool(token,{details:{native_research_source:{source_ref:'obs-old'}}});
  const partial={...record(token.action.id),outcome:'limited',limitations:['Only summary retained']};partial.outputs[0].observation_refs=['obs-old'];
  assert.equal((await f.controller.execute('record','old-record',partial)).details.ok,true);await f.controller.close();
  let view=f.view;const note=view.state.notes.at(-1),saved=JSON.parse(note.text),legacy={...partial,outcome:'completed',limitations:[]};
  const canonical=value=>Array.isArray(value)?value.map(canonical):value&&typeof value==='object'?Object.fromEntries(Object.keys(value).sort().map(key=>[key,canonical(value[key])])):value;
  const digest=createHash('sha256').update(JSON.stringify(canonical(legacy))).digest('hex');
  // Representative retained shape produced by the former partial-completed rule.
  saved.snapshot.executions[0].record=structuredClone(legacy);
  saved.snapshot.history.filter(item=>item.operation==='record').at(-1).payload_digest=digest;
  const receipt=saved.commands.find(item=>item.id==='old-record');receipt.payload_hash=digest;note.text=JSON.stringify(saved);
  let commits=0;const ports={...f.ports,readResearch:async()=>structuredClone(view),dispatchNode:()=>assert.fail('Retained work must not rerun'),
    commitResearch:async(_id,request)=>{commits++;assert.equal(request.expected_revision,view.research_revision);
      view={research_revision:view.research_revision+1,state:{...request.changes,notes:[...view.state.notes,...request.changes.notes]}};
      return {details:{ok:true,result:{status:'committed',receipt:{research_revision:view.research_revision}}}};}};
  const restored=createEnterpriseGraphController(ports);assert.equal((await restored.readState()).graph.nodes[0].phase,'recorded');
  assert.deepEqual(await restored.execute('record','old-record',legacy),receipt.reply);assert.equal(commits,0);
  assert.equal((await restored.execute('record','new-call-same-record',legacy)).details.ok,true);assert.equal(commits,1);
  const latest=JSON.parse(view.state.notes.at(-1).text);assert.deepEqual(latest.snapshot.executions[0].record,legacy);assert.equal(latest.snapshot.results.length,1);
  const before=structuredClone(view);assert.equal((await restored.execute('record','new-conflicting-record',{...legacy,limitations:['Changed bytes']})).details.ok,false);assert.deepEqual(view,before);
  await restored.close();const again=createEnterpriseGraphController(ports);assert.equal((await again.readState()).graph.nodes[0].output_bindings.length,1);await again.close();
});
test('parent abort keeps a cancelled receipt on the exact action',async()=>{
  const f=fixture();await f.controller.execute('plan','plan',plan([node('P',{execution:'parent'})]));await f.controller.execute('start','start',{step_id:'P'});
  const token=await f.controller.beginTool({toolCallId:'cancelled-read',toolName:'read'});
  f.controller.endTool(token,undefined,new DOMException('Operation aborted','AbortError'));
  assert.equal((await f.controller.execute('record','bad-record',record(token.action.id))).details.ok,false);
  assert.equal((await f.controller.readState()).graph.nodes[0].phase,'executing');
  assert.equal((await f.controller.execute('record','cancelled-record',{action_id:token.action.id,outcome:'failed',outputs:[],limitations:['Native call cancelled']})).details.ok,true);
  const state=await f.controller.readState();assert.equal(state.graph.nodes[0].settled_status,'cancelled');
  const saved=JSON.parse(f.view.state.notes.at(-1).text);assert.equal(saved.receipts[0].status,'cancelled');assert.equal(saved.receipts[0].action_id,token.action.id);
  await f.controller.close({reason:'Done'});
});
test('parent corrective native call preserves failed receipt and admits only completed observations',async()=>{
  const f=fixture();await f.controller.execute('plan','plan',plan([node('P',{execution:'parent'})]));await f.controller.execute('start','start',{step_id:'P'});
  const failed=await f.controller.beginTool({toolCallId:'bad-read',toolName:'read'});f.controller.endTool(failed,undefined,new Error('ENOENT'));
  const corrected=await f.controller.beginTool({toolCallId:'valid-read',toolName:'read'});
  await f.controller.completeTool(corrected,{content:[],details:{native_research_source:{source_ref:'corrected-source'}}});
  const payload=record(corrected.action.id);payload.outputs[0].observation_refs=['corrected-source'];
  const reply=await f.controller.execute('record','corrected-record',payload);assert.equal(reply.details.ok,true,JSON.stringify(reply));
  const state=await f.controller.readState();assert.equal(state.graph.nodes[0].settled_status,'completed');
  const saved=JSON.parse(f.view.state.notes.at(-1).text);assert.deepEqual(saved.receipts.map(item=>item.status),['failed','completed']);
  const failedRef=saved.receipts[0].ref;
  assert.equal((await f.controller.execute('assess','bad-assess',{action_id:state.graph.nodes[0].assess_action_id,outcome:'success',
    checks:[{description:'Verify P',status:'passed',refs:[failedRef],explanation:'Failed read is not proof'}],summary:'Rejected success'})).details.ok,false);
  await f.controller.close({reason:'Done'});
});
test('limited finish cancels children and emits explicit committed delivery without implying success',async()=>{
  const f=fixture();await f.controller.execute('plan','plan',plan([node('A')]));
  const payload={outcome:'limited',delivery_result_refs:[],delivery_product_refs:[],limitations:['Cancelled remaining work at /private/location'],summary:'Limited actual answer'};
  const reply=await f.controller.finish('finish',payload);assert.equal(reply.details.ok,true);assert.equal(f.controller.status.phase,'limited');
  assert.equal((await f.controller.readState()).graph.nodes[0].settled_status,'cancelled');
  const event=f.events.at(-1).events.find(item=>item.kind==='graph_delivery_committed');assert.equal(event.outcome,'limited');
  assert.ok(!JSON.stringify(reply).includes('/private/'));await f.controller.close({reason:'Done'});
});
test('full event, protected request and protected response budgets fail before commit or dispatch',async()=>{
  for(const dimension of ['event_bytes','research_request_bytes','research_response_bytes']){
    const f=fixture({config:{researchTaskId:'task',researchOwner:owner,researchAttemptId:'attempt',runtimeLimits:{[dimension]:100},
      researchRuntime:{graphLimits:limits,delegation:{concurrency:2}}}});
    const reply=await f.controller.execute('plan','plan',plan([node('A')]));
    assert.equal(reply.details.ok,false,dimension);assert.equal(reply.details.error.capacity.dimension,dimension);
    assert.equal(f.requests.length,0);assert.equal(f.calls.length,0);assert.equal(f.events.length,0);
  }
});
test('debug capacity failure is a typed interruption with no truncation or checkpoint',async()=>{
  const f=fixture({config:{researchTaskId:'task',researchOwner:owner,researchAttemptId:'attempt',runtimeLimitMode:'debug',runtimeLimits:{event_bytes:100},
    researchRuntime:{graphLimits:limits,delegation:{concurrency:2}}}});
  await assert.rejects(()=>f.controller.execute('plan','plan',plan([node('A')])),error=>error.code==='capacity_exceeded'&&error.mode==='debug');
  assert.equal(f.requests.length,0);
});
test('lightweight debug capacity returns a recoverable control error without committing an oversized plan',async()=>{
  const f=fixture({config:{researchTaskId:'task',researchOwner:owner,researchAttemptId:'attempt',runtimeLimitMode:'debug',runtimeLimits:{event_bytes:100},
    researchRuntime:{lightweightTaskNodes:true,graphLimits:limits,delegation:{concurrency:2}}}});
  const reply=await f.controller.execute('plan','plan',plan([node('A')]));
  assert.equal(reply.details.ok,false);
  assert.equal(reply.details.error.capacity.dimension,'event_bytes');
  assert.equal(reply.details.error.recovery,'reduce_or_split_request');
  assert.match(reply.content[0].text,/Do not retry unchanged input/);
  assert.equal(f.requests.length,0);
  assert.equal(f.calls.length,0);
  assert.ok(await f.controller.readState());
});
test('native tool tokens retain a committed checkpoint and tools do not add a CAS round trip',async()=>{
  const f=fixture();await f.controller.execute('plan','plan',plan([node('P',{execution:'parent'})]));await f.controller.execute('start','start',{step_id:'P'});
  const count=f.requests.length,token=await f.controller.beginTool({toolCallId:'read',toolName:'read'});
  assert.ok(token.checkpoint.ref);assert.equal(token.checkpoint.revision,f.view.research_revision);
  await f.controller.completeTool(token,{details:{native_research_source:{source_ref:'real-source'}}});assert.equal(f.requests.length,count);
  await f.controller.close({reason:'Done'});assert.equal(JSON.parse(f.view.state.notes.at(-1).text).receipts[0].ref,'real-source');
});
test('rejected native settlement blocks new dispatch and can recover the retained real proposal',async()=>{
  const f=fixture({config:{researchTaskId:'task',researchOwner:owner,researchAttemptId:'attempt',researchRuntime:{graphLimits:limits,delegation:{concurrency:1}}}});
  await f.controller.execute('plan','plan',plan([node('A'),node('B')]));f.reject();await f.settle('A');await tick();
  assert.deepEqual(f.calls.map(item=>item.node.id),['A']);assert.equal(f.events.filter(event=>event.events.some(item=>item.kind==='node_execution_settled')).length,0);
  await f.controller.recoverPending();assert.deepEqual(f.calls.map(item=>item.node.id),['A','B']);await f.controller.close({reason:'Done'});
});
test('late parent receipt survives adoption of an earlier sibling unconfirmed snapshot',async()=>{
  const f=fixture();await f.controller.execute('plan','plan',plan([node('P',{execution:'parent'}),node('B')]));await f.controller.execute('start','start',{step_id:'P'});
  const token=await f.controller.beginTool({toolCallId:'late-parent-read',toolName:'read'});f.lose();await f.settle('B');
  await f.controller.completeTool(token,{details:{native_research_source:{source_ref:'late-source'}}});await f.controller.recoverPending();
  const payload=record(token.action.id);payload.outputs[0].observation_refs=['late-source'];assert.equal((await f.controller.execute('record','record-parent',payload)).details.ok,true);
  const saved=JSON.parse(f.view.state.notes.at(-1).text);assert.equal(saved.receipts.find(item=>item.ref==='late-source').action_id,token.action.id);
  await f.controller.close({reason:'Done'});
});
test('file finish selects exact inspected artifact versions and preserves presentation roles',async()=>{
  const f=fixture({config:{researchRuntime:{graphLimits:limits,delegation:{concurrency:2},isolatedTaskExecution:true}}});await f.controller.execute('plan','plan',{...plan([node('A',{outputs:[{slot:'value',kind:'artifact',description:'Saved report'}]})]),output_mode:'files'});
  const action=f.calls[0].action,product={ref:'artifact-version',path:'report.md',sha256:'a'.repeat(64),bytes:30,status:'ready',owner,action_id:action.id,attempt_id:'attempt',roles:['primary']};
  await f.settle('A','completed','Saved real report',[product]);
  const payload=record(action.id);payload.outputs[0].artifact_refs=[product.ref];payload.outputs[0].observation_refs=['obs-A'];
  assert.equal((await f.controller.execute('record','record',payload)).details.ok,true);
  const current=(await f.controller.readState()).graph.nodes[0];
  await f.controller.execute('assess','assess',{action_id:current.assess_action_id,outcome:'success',checks:[{description:'Verify A',status:'passed',refs:['obs-A'],explanation:'Observed'}],summary:'Checked actual output'});
  const compact=(await f.controller.readState({compact:true})).graph;
  const [accepted]=compact.current_results;
  assert.equal(accepted.phase,'success');assert.equal(accepted.step_id,'A');
  assert.deepEqual(accepted.artifact_refs,[product.ref]);
  assert.deepEqual(accepted.products,[{ref:product.ref,kind:'product',logical_path:product.path,sha256:product.sha256,bytes:30,roles:['primary']}]);
  assert.doesNotMatch(JSON.stringify(accepted),/Saved real report|handle-/);
  const closure={outcome:'success',delivery_result_refs:[accepted.result_ref],delivery_product_refs:accepted.artifact_refs,limitations:[],summary:'Report delivered'};
  assert.equal((await f.controller.finish('finish',closure)).details.ok,true);
  const saved=JSON.parse(f.view.state.notes.at(-1).text);assert.deepEqual(saved.delivery,closure);assert.deepEqual(saved.products,[product]);
  assert.deepEqual(saved.snapshot.results[0].artifact_refs,[product.ref]);await f.controller.close({reason:'Done'});
});
test('invalid immutable input admission never starts native work and records the known setup failure',async()=>{
  const f=fixture({ports:{resolveInputs:async action=>action.input_bindings.length?{manifests:[{result_ref:action.input_bindings[0].result_ref,summary:'Changed bytes'}],handles:[]}:{manifests:[],handles:[]}}});
  await f.controller.execute('plan','plan',plan([node('A'),node('C',{depends_on:['A'],inputs:[{name:'selected',from:{step_id:'A',slot:'value'}}]})]));
  await f.settle('A');await accept(f,'A');await tick();
  assert.deepEqual(f.calls.map(item=>item.node.id),['A']);
  assert.equal((await f.controller.readState()).graph.nodes.find(item=>item.id==='C').settled_status,'failed');await f.controller.close({reason:'Done'});
});
test('inspect commits host-checked parent products and returns exact refs without creating an execution receipt',async()=>{
  let seen,product;const f=fixture({ports:{inspectProducts:async request=>{seen=request;return {ready:true,products:[product],selections:[{path:'report.md',ref:product.ref}]};}}});
  await f.controller.execute('plan','plan',plan([node('P',{execution:'parent',outputs:[{slot:'value',kind:'artifact',description:'Real file'}]})]));
  await f.controller.execute('start','start',{step_id:'P'});const current=(await f.controller.readState()).graph.nodes[0];
  product={ref:'real-product',path:'context-results/frozen/report.md',roles:['primary'],sha256:'a'.repeat(64),bytes:30,status:'ready',owner,attempt_id:'attempt',action_id:current.execute_action_id};
  const payload={action_id:current.execute_action_id,products:[{path:'report.md',role:'primary'}]};
  const reply=await f.controller.inspect('inspect',payload);assert.equal(reply.details.ok,true);
  assert.equal(reply.details.result.products[0].ref,'real-product');assert.deepEqual(seen.products,payload.products);assert.equal(seen.action.id,payload.action_id);
  const saved=JSON.parse(f.view.state.notes.at(-1).text);assert.deepEqual(saved.products,[product]);assert.deepEqual(saved.receipts,[]);
  assert.deepEqual(await f.controller.inspect('inspect',payload),reply);
  const unsupported=record(current.execute_action_id);unsupported.outputs[0].artifact_refs=[product.ref];
  assert.equal((await f.controller.execute('record','unexecuted-record',unsupported)).details.ok,false);
  await f.controller.close({reason:'Done'});
});
test('inspect rejects traversals, extra fields, sibling grants and unconfirmed inspection before admission',async()=>{
  let calls=0;const f=fixture({ports:{inspectProducts:async()=>{calls++;return {ready:false,products:[]};}}});
  await f.controller.execute('plan','plan',plan([node('P',{execution:'parent'})]));await f.controller.execute('start','start',{step_id:'P'});
  const action=(await f.controller.readState()).graph.nodes[0].execute_action_id;
  for(const entry of [{path:'../escape',role:'primary'},{path:'report.md',role:'primary',ref:'invented'},{path:'/private/report',role:'primary'}])
    assert.equal((await f.controller.inspect('bad-'+calls,{action_id:action,products:[entry]})).details.ok,false);
  assert.equal(calls,0);
  const before=f.requests.length;assert.equal((await f.controller.inspect('unconfirmed',{action_id:action,products:[{path:'report.md',role:'primary'}]})).details.ok,false);
  assert.equal(f.requests.length,before);assert.deepEqual(JSON.parse(f.view.state.notes.at(-1).text).products,[]);await f.controller.close({reason:'Done'});
});
test('committed command replay remains exact while a different automatic start awaits acknowledgement',async()=>{
  let f;f=fixture({ports:{onProgress:event=>{f.events.push(event);if(event.events.some(item=>item.kind==='graph_committed'))f.lose();}}});
  const payload=plan([node('A')]),first=await f.controller.execute('plan','plan',payload);
  assert.equal((await f.controller.readState()).update_pending,true);
  assert.deepEqual(await f.controller.execute('plan','plan',payload),first);
  await f.controller.recoverPending();await f.controller.close({reason:'Done'});
});
test('failed assessments can deliver only explicitly marked diagnostic support or reproduction files',async()=>{
  for(const outcome of ['limited','failure'])for(const role of ['primary','support','reproduction']){
    const f=fixture();await f.controller.execute('plan','plan',{...plan([node('A',{outputs:[{slot:'value',kind:'artifact',description:'Saved diagnostic'}]})]),output_mode:'files'});
    const action=f.calls[0].action,product={ref:'diagnostic',path:'diagnostic.txt',sha256:'a'.repeat(64),bytes:30,status:'ready',owner,action_id:action.id,attempt_id:'attempt',roles:[role]};
    await f.settle('A','completed','Actual diagnostic',[product]);
    const recorded=record(action.id);recorded.outputs[0].artifact_refs=[product.ref];recorded.outputs[0].observation_refs=['obs-A'];
    await f.controller.execute('record','record',recorded);
    const state=await f.controller.readState();await f.controller.execute('assess','assess',{action_id:state.graph.nodes[0].assess_action_id,
      outcome:'failure',checks:[{description:'Verify A',status:'failed',refs:['obs-A'],explanation:'Actual discrepancy'}],summary:'Output failed its declared quality check'});
    const resultRef=(await f.controller.readState()).graph.results[0].result_ref;
    const response=await f.controller.finish('finish',{outcome,delivery_result_refs:[resultRef],delivery_product_refs:[product.ref],limitations:['The output is a diagnostic only and failed its quality check'],summary:'Diagnostic only; the requested report was not delivered'});
    assert.equal(response.details.ok,outcome==='failure'&&role!=='primary',outcome+' '+role);await f.controller.close({reason:'Done'});
  }
});
test('file delivery cannot claim success from only checked support files',async()=>{
  const f=fixture();await f.controller.execute('plan','plan',{...plan([node('A',{outputs:[{slot:'value',kind:'artifact',description:'Support file'}]})]),output_mode:'files'});
  const action=f.calls[0].action,product={ref:'support',path:'support.txt',sha256:'a'.repeat(64),bytes:30,status:'ready',owner,action_id:action.id,attempt_id:'attempt',roles:['support']};
  await f.settle('A','completed','Actual support',[product]);const payload=record(action.id);payload.outputs[0].observation_refs=['obs-A'];payload.outputs[0].artifact_refs=[product.ref];
  await f.controller.execute('record','record',payload);await f.controller.execute('assess','assess',{action_id:(await f.controller.readState()).graph.nodes[0].assess_action_id,
    outcome:'success',checks:[{description:'Verify A',status:'passed',refs:['obs-A'],explanation:'Observed'}],summary:'Support passed'});
  const resultRef=(await f.controller.readState()).graph.results[0].result_ref;
  assert.equal((await f.controller.finish('finish',{outcome:'success',delivery_result_refs:[resultRef],delivery_product_refs:[product.ref],limitations:[],summary:'Requested report'})).details.ok,false);
  await f.controller.close({reason:'Done'});
});
test('byte-identical recomputation keeps separate action grants and distinct result versions',async()=>{
  const nodes=[node('A',{outputs:[{slot:'value',kind:'artifact',description:'Saved result'}]})];
  const f=fixture({config:{researchTaskId:'task',researchOwner:owner,researchAttemptId:'attempt',researchSources:['diagnostic'],researchRuntime:{graphLimits:limits,delegation:{concurrency:1},isolatedTaskExecution:true}}});
  await f.controller.execute('plan','plan',{...plan(nodes),output_mode:'files'});
  const save=async suffix=>{
    const action=f.calls.at(-1).action,product={ref:'same-bytes',path:'output.txt',sha256:'a'.repeat(64),bytes:30,status:'ready',owner,action_id:action.id,attempt_id:'attempt',roles:[suffix==='one'?'primary':'support']};
    await f.settle('A','completed','Same actual bytes',[product]);const payload=record(action.id);payload.outputs[0].observation_refs=['obs-A'];payload.outputs[0].artifact_refs=[product.ref];
    assert.equal((await f.controller.execute('record','record-'+suffix,payload)).details.ok,true);
    assert.equal((await f.controller.execute('assess','assess-'+suffix,{action_id:(await f.controller.readState()).graph.nodes[0].assess_action_id,
      outcome:'success',checks:[{description:'Verify A',status:'passed',refs:['obs-A'],explanation:'Observed'}],summary:'Accepted actual bytes'})).details.ok,true);
  };
  await save('one');const first=(await f.controller.readState()).graph.results[0];
  assert.equal((await f.controller.execute('revise','revise',{nodes,reason:'Observed discrepancy needs a new execution',rerun:[{step_id:'A',reason:{kind:'discrepancy',refs:['diagnostic']},supersedes:[first.result_ref]}]})).details.ok,true);
  assert.deepEqual((await f.controller.readState({compact:true})).graph.current_results,[]);
  await save('two');const state=await f.controller.readState();assert.equal(state.graph.results.length,2);assert.notEqual(state.graph.results[0].result_ref,state.graph.results[1].result_ref);
  const current=(await f.controller.readState({compact:true})).graph.current_results;
  assert.deepEqual(current.map(item=>item.result_ref),[state.graph.results[1].result_ref]);
  assert.deepEqual(current[0].products[0].roles,['support']);
  const saved=JSON.parse(f.view.state.notes.at(-1).text);assert.equal(saved.products.length,2);assert.equal(saved.receipts.length,2);
  assert.deepEqual(saved.products.map(item=>item.ref),['same-bytes','same-bytes']);assert.notEqual(saved.products[0].action_id,saved.products[1].action_id);
  assert.equal((await f.controller.readProposal(f.calls.at(-1).action.id)).products.length,1);
  assert.equal((await f.controller.finish('finish',{outcome:'success',delivery_result_refs:[state.graph.results[1].result_ref],delivery_product_refs:['same-bytes'],limitations:[],summary:'Current report'})).details.ok,false,
    'Historical primary grant must not override current support role');await f.controller.close({reason:'Done'});
});
test('selected failed artifact cannot inherit primary through another selected successful result',async()=>{
  const outputs=[{slot:'value',kind:'artifact',description:'Real shared bytes'}],f=fixture();
  await f.controller.execute('plan','plan',{...plan([node('A',{outputs}),node('B',{outputs})]),output_mode:'files'});
  for(const id of ['A','B']){
    const action=f.calls.find(item=>item.node.id===id).action,product={ref:'shared',path:'shared.txt',sha256:'a'.repeat(64),bytes:30,status:'ready',owner,action_id:action.id,attempt_id:'attempt',roles:[id==='A'?'support':'primary']};
    await f.settle(id,'completed','Actual bytes',[product]);const payload=record(action.id);payload.outputs[0].artifact_refs=['shared'];payload.outputs[0].observation_refs=['obs-'+id];
    await f.controller.execute('record','record-'+id,payload);const current=(await f.controller.readState()).graph.nodes.find(item=>item.id===id);
    await f.controller.execute('assess','assess-'+id,{action_id:current.assess_action_id,outcome:id==='A'?'failure':'success',
      checks:[{description:'Verify '+id,status:id==='A'?'failed':'passed',refs:['obs-'+id],explanation:'Actual check'}],summary:'Actual assessment'});
  }
  const state=await f.controller.readState(),common={delivery_product_refs:['shared'],limitations:['Failed selected output is diagnostic only'],summary:'Diagnostic'};
  assert.equal((await f.controller.finish('bad-finish',{outcome:'limited',delivery_result_refs:state.graph.results.map(item=>item.result_ref),...common})).details.ok,false);
  assert.equal((await f.controller.finish('failure-finish',{outcome:'failure',delivery_result_refs:[state.graph.results[0].result_ref],...common})).details.ok,true,
    'An unrelated historical primary grant must not override the selected diagnostic grant');await f.controller.close({reason:'Done'});
});
