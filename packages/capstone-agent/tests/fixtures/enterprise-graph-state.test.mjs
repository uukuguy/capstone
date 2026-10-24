import {test} from 'node:test';
import assert from 'node:assert/strict';

const module = await import('../../src/capstone_agent/resources/enterprise-graph-state.mjs').catch(error => {
  if (error.code === 'ERR_MODULE_NOT_FOUND') return {};
  throw error;
});
const contract = await import('../../src/capstone_agent/resources/enterprise-graph-contract.mjs').catch(error => {
  if (error.code === 'ERR_MODULE_NOT_FOUND') return {};
  throw error;
});
const {reduceEnterpriseGraph,projectEnterpriseGraph,graphAction,resolveEnterpriseGraphResultForHost}=module;
const limits={maxNodes:32,maxItems:64,maxText:4096,maxExecutions:64,snapshotBytes:500000,publicBytes:100000};
const owner={thread_id:'thread',work_id:'work',research_id:'research',goal_revision:1};
const host=(extra={})=>({owner,attempt_id:'attempt',sources:[],receipts:[],products:[],results:[],...extra});
const node=(id,extra={})=>({id,purpose:'Purpose '+id,questions:['Question '+id],checks:['Verify '+id],
  depends_on:[],expected_outputs:['Useful output'],mode:'execute',execution:'delegated',instruction:'Do the declared work '+id,
  source_refs:[],outputs:[{slot:'opaque.slot',kind:'observation',description:'Actual observation'}],inputs:[],...extra});
const plan=nodes=>({goal:'Explain observed inputs',output_mode:'text',nodes,source_refs:[]});
const apply=(state,op,payload,extra={},caps=limits)=>reduceEnterpriseGraph(state,op,payload,host(extra),caps);
const start=(state,id)=>apply(state,'start',{step_id:id}).state;
const action=(state,id)=>state.node_states[id].execute_action_id;
const receipt=(state,id,extra={})=>({owner,ref:'obs-'+id+'-'+state.node_states[id].execution_revision,
  action_id:action(state,id),attempt_id:'attempt',status:'completed',...extra});
const record=(state,id,extra={})=>({action_id:action(state,id),outcome:'completed',outputs:[{slot:'opaque.slot',
  observation_refs:[receipt(state,id).ref],artifact_refs:[],summary:'Actual result '+id,scope:'Observed scope'}],limitations:[],...extra});
function finish(state,id,{assess=true,outputs,receiptExtra={},hostExtra={}}={}) {
  const admitted=receipt(state,id,receiptExtra);
  state=apply(state,'execution_settled',{action_id:action(state,id),status:'completed'}).state;
  state=apply(state,'record',record(state,id,outputs?{outputs}:{}),{receipts:[admitted],...hostExtra}).state;
  if(!assess)return state;
  return apply(state,'assess',{action_id:state.node_states[id].assess_action_id,outcome:'success',
    checks:state.nodes.find(item=>item.id===id).checks.map(description=>({description,status:'passed',refs:[admitted.ref],explanation:'Observed'})),
    summary:'Accepted '+id}).state;
}
const graph=()=>[node('A'),node('B'),node('C',{depends_on:['A'],mode:'synthesis',inputs:[{name:'selected',from:{step_id:'A',slot:'opaque.slot'}}]}),
  node('D',{depends_on:['A','B']})];
const reason={kind:'discrepancy',refs:['diagnostic'],diagnostic:'Observed discrepancy'};

test('publishes the versioned pure graph interfaces',()=>{
  assert.equal(typeof reduceEnterpriseGraph,'function','graph reducer is required');
  assert.equal(typeof contract.validateGraphOperation,'function');
  assert.equal(contract.GRAPH_SCHEMA,'capstone-enterprise-graph/2');
});
test('research consumers use selected completed limited outputs and inherit their limitations',()=>{
  const context={allow_selected_limited_inputs:true},run=(s,op,payload,extra={})=>apply(s,op,payload,{...context,...extra});
  const nodes=[node('A',{outputs:[{slot:'opaque.slot',kind:'observation',description:'Retained finding'},
    {slot:'optional',kind:'artifact',description:'Unfinished extra file'}]}),
    node('C',{depends_on:['A'],mode:'synthesis',inputs:[{name:'selected',from:{step_id:'A',slot:'opaque.slot'}}]}),
    node('D',{depends_on:['A'],inputs:[{name:'missing',from:{step_id:'A',slot:'optional'}}]})];
  let state=run(null,'plan',plan(nodes)).state;
  state=run(state,'start',{step_id:'A'}).state;const observed=receipt(state,'A');
  state=run(state,'execution_settled',{action_id:action(state,'A'),status:'completed'}).state;
  state=run(state,'record',record(state,'A',{outcome:'limited',limitations:['Extra file was not produced']}),{receipts:[observed]}).state;
  state=run(state,'assess',{action_id:state.node_states.A.assess_action_id,outcome:'limited',
    checks:[{description:'Verify A',status:'not_run',refs:[],explanation:'Analytical review remains open'}],summary:'Useful retained finding'}).state;
  assert.equal(state.node_states.C.phase,'ready');assert.equal(state.node_states.D.phase,'pending');
  assert.throws(()=>apply(state,'start',{step_id:'C'}),/host policy/);
  for(const status of ['cancelled','failed','unknown']){
    const invalid=structuredClone(state);invalid.executions[0].settled_status=status;
    assert.throws(()=>run(invalid,'start',{step_id:'C'}),/not ready/);
  }
  const stale=structuredClone(state);stale.node_states.A.applicability='stale';
  assert.throws(()=>run(stale,'start',{step_id:'C'}),/not ready/);
  const ref=state.results[0].result_ref;
  const direct=node('E',{depends_on:['A'],mode:'synthesis',inputs:[{name:'selected',result_ref:ref}]});
  state=run(state,'revise',{nodes:[...nodes,direct],reason:'Compose selected retained result',rerun:[]}).state;
  assert.equal(state.node_states.E.phase,'ready');
  state=run(state,'start',{step_id:'C'}).state;
  const bound=state.node_states.C.input_bindings[0];
  assert.equal(bound.result_ref,ref);assert.deepEqual(bound.accepted_limitations.record_limitations,['Extra file was not produced']);
  assert.equal(bound.accepted_limitations.unmet_checks[0].status,'not_run');
  const own=receipt(state,'C');state=run(state,'execution_settled',{action_id:action(state,'C'),status:'completed'}).state;
  state=run(state,'record',record(state,'C'),{receipts:[own]}).state;
  assert.equal(state.results.at(-1).input_limitations[0].result_ref,ref);
  assert.equal(state.executions[0].phase,'limited');
});
test('work edition binds only explicitly accepted assessed limited versions and propagates their limitations',()=>{
  const edition='capstone-graph-work/1',context={graph_work_edition:edition};
  const run=(state,op,payload,extra={})=>apply(state,op,payload,{...context,...extra});
  const nodes=[node('A'),node('C',{depends_on:['A'],mode:'synthesis',inputs:[{name:'prior',from:{step_id:'A',slot:'opaque.slot'}}]})];
  let state=run(null,'plan',plan(nodes)).state;
  state=run(state,'start',{step_id:'A'}).state;
  const admitted=receipt(state,'A');state=run(state,'execution_settled',{action_id:action(state,'A'),status:'completed'}).state;
  state=run(state,'record',record(state,'A'),{receipts:[admitted]}).state;
  state=run(state,'assess',{action_id:state.node_states.A.assess_action_id,outcome:'limited',
    checks:[{description:'Verify A',status:'not_run',refs:[],explanation:'Optional visual review was not performed'}],summary:'Useful with explicit limits'}).state;
  assert.equal(state.node_states.C.phase,'pending');
  const producer=state.executions[0],ref=producer.output_bindings[0].result_ref;
  assert.match(producer.assessment_ref,/^assessment:/);
  const replacement=structuredClone(nodes);replacement[1].inputs=[{name:'prior',result_ref:ref,
    accept_limited:{assessment_ref:producer.assessment_ref,rationale:'The selected numeric finding is adequate; carry the unperformed review'}}];
  for(const status of ['cancelled','failed','unknown']){
    const invalid=structuredClone(state);invalid.executions[0].settled_status=status;
    assert.throws(()=>run(invalid,'revise',{nodes:replacement,reason:'Unusable native status',rerun:[]}),/assessment|acceptance/i);
  }
  const wrongAssessment=structuredClone(replacement);wrongAssessment[1].inputs[0].accept_limited.assessment_ref='assessment:other';
  assert.throws(()=>run(state,'revise',{nodes:wrongAssessment,reason:'Wrong assessment',rerun:[]}),/assessment|acceptance/i);
  const implicit=structuredClone(replacement);delete implicit[1].inputs[0].accept_limited;
  assert.equal(run(state,'revise',{nodes:implicit,reason:'No limited authorization',rerun:[]}).state.node_states.C.phase,'pending');
  const future=structuredClone(nodes);future[1].inputs[0].accept_limited=replacement[1].inputs[0].accept_limited;
  assert.throws(()=>run(state,'revise',{nodes:future,reason:'Future blanket acceptance forbidden',rerun:[]}),/binding|unexpected/i);
  const unacceptedFuture=structuredClone(replacement);
  unacceptedFuture[1].inputs.push({name:'unapproved',from:{step_id:'A',slot:'opaque.slot'}});
  assert.equal(run(state,'revise',{nodes:unacceptedFuture,reason:'One accepted edge does not authorize a future edge',rerun:[]}).state.node_states.C.phase,'pending');
  const otherDependency=structuredClone(replacement);otherDependency.push(node('B'));
  otherDependency[1].depends_on.push('B');
  assert.equal(run(state,'revise',{nodes:otherDependency,reason:'Another required dependency remains blocked',rerun:[]}).state.node_states.C.phase,'pending');
  state=run(state,'revise',{nodes:replacement,reason:'Use exact limited finding',rerun:[]}).state;
  assert.equal(state.node_states.C.phase,'ready');
  state=run(state,'start',{step_id:'C'}).state;
  assert.equal(state.node_states.C.input_bindings[0].accepted_limitations.assessment_ref,producer.assessment_ref);
  state=run(state,'execution_settled',{action_id:action(state,'C'),status:'completed'}).state;
  state=run(state,'record',record(state,'C',{outputs:[{slot:'opaque.slot',observation_refs:[admitted.ref],artifact_refs:[],summary:'Used retained finding',scope:'Selected subset'}]})).state;
  const result=state.results.find(item=>item.producer.step_id==='C');
  assert.equal(result.input_limitations[0].result_ref,ref);assert.equal(state.executions[0].phase,'limited');
  assert.equal(result.input_limitations[0].unmet_checks[0].status,'not_run');
  assert.equal(result.input_limitations[0].assessment_summary,producer.assessment.summary);
  const imported=run(null,'plan',plan([node('X',{mode:'synthesis',inputs:[{name:'retained',result_ref:result.result_ref}]})]),{results:[result]}).state;
  assert.equal(imported.external_results[0].input_limitations[0].assessment_summary,producer.assessment.summary);
  const missingSummary=structuredClone(result);delete missingSummary.input_limitations[0].assessment_summary;
  assert.throws(()=>run(null,'plan',plan([node('X')]),{results:[missingSummary]}),/limitation provenance/);
  const wrong=structuredClone(replacement);wrong[1].inputs[0].accept_limited.assessment_ref='assessment:foreign';
  assert.throws(()=>run(state,'revise',{nodes:wrong,reason:'Wrong acceptance',rerun:[]}),/immutable|assessment|accepted/i);
  assert.throws(()=>apply(null,'plan',plan(replacement)),/unexpected|binding|edition/i);
});
test('fresh record diagnostics retain exact mechanical fields and only selected inherited refs',()=>{
  let state=apply(null,'plan',plan([node('A'),node('B'),node('C',{depends_on:['A'],mode:'synthesis',
    inputs:[{name:'prior',from:{step_id:'A',slot:'opaque.slot'}}]})])).state;
  state=start(state,'A');state=finish(state,'A');state=start(state,'B');state=finish(state,'B');state=start(state,'C');
  state=apply(state,'execution_settled',{action_id:action(state,'C'),status:'completed'}).state;
  const before=structuredClone(state),payload=record(state,'C');payload.outputs[0].observation_refs=['obs-B-1'];
  assert.throws(()=>apply(state,'record',payload),error=>{
    assert.deepEqual(error.diagnostic,{operation:'record',action_id:action(state,'C'),code:'unadmitted_reference',field:'outputs[0].observation_refs',
      output_index:0,slot:'opaque.slot',valid_refs:{observation_refs:{values:['obs-A-1'],total:1,omitted:0},artifact_refs:{values:[],total:0,omitted:0}}});return true;
  });
  assert.deepEqual(state,before);
  const limited={...payload,outcome:'limited',limitations:['Unusable association']};limited.outputs[0].slot='unknown-slot';
  assert.throws(()=>apply(state,'record',limited),error=>{
    assert.equal(error.diagnostic.code,'undeclared_output_slot');assert.equal(error.diagnostic.field,'outputs[0].slot');
    assert.equal(error.diagnostic.slot,undefined);assert.doesNotMatch(JSON.stringify(error.diagnostic),/unknown-slot|obs-B-1/);return true;
  });
});
test('preserves exact definitions and exposes no synthetic ready nodes',()=>{
  const nodes=graph(),original=structuredClone(nodes);
  const committed=apply(null,'plan',plan(nodes));let state=committed.state;
  assert.deepEqual(committed.events[0].nodes,original);
  assert.ok(Buffer.byteLength(JSON.stringify(committed.events[0]))<=limits.publicBytes);
  assert.deepEqual(state.nodes,original);assert.equal(state.pending_action,undefined);
  state=finish(start(state,'A'),'A');
  assert.deepEqual(state.nodes,original);assert.deepEqual(nodes,original);
  assert.ok(state.nodes.every(item=>!item.id.startsWith('host-ready')));
  assert.equal(state.node_states.A.phase,'success');
});
test('A releases C while B runs and D waits for both accepted prerequisites',()=>{
  let state=apply(null,'plan',plan(graph())).state;
  state=start(start(state,'A'),'B');
  const bAction=graphAction(state,action(state,'B'));
  state=finish(state,'A');
  assert.equal(state.node_states.B.phase,'executing');
  assert.equal(state.node_states.C.phase,'ready');assert.equal(state.node_states.D.phase,'pending');
  assert.deepEqual(state.node_states.D.blocked_by,['B']);
  assert.deepEqual(graphAction(state,bAction.id),bAction);
  state=start(state,'C');assert.equal(state.node_states.C.input_bindings[0].result_ref,state.results[0].result_ref);
  assert.throws(()=>start(state,'D'),/ready|depend/i);
});
test('native return and recorded output cannot release dependants before successful assessment',()=>{
  let state=start(apply(null,'plan',plan(graph())).state,'A');
  state=apply(state,'execution_settled',{action_id:action(state,'A'),status:'completed'}).state;
  assert.equal(state.node_states.A.phase,'executed');assert.equal(state.node_states.C.phase,'pending');
  state=apply(state,'record',record(state,'A'),{receipts:[receipt(state,'A')]}).state;
  assert.equal(state.node_states.A.phase,'recorded');assert.equal(state.node_states.C.phase,'pending');
});
test('missing output blocks only slot consumers and cannot be assessed as complete',()=>{
  let state=start(apply(null,'plan',plan(graph())).state,'A');
  state=apply(state,'execution_settled',{action_id:action(state,'A'),status:'completed'}).state;
  const before=structuredClone(state);
  assert.throws(()=>apply(state,'record',record(state,'A',{outputs:[]}),{receipts:[receipt(state,'A')]}),/all declared output slots/i);
  assert.deepEqual(state,before);
  state=apply(state,'record',record(state,'A',{outcome:'limited',outputs:[],limitations:['The declared output was not supplied']}),{receipts:[receipt(state,'A')]}).state;
  assert.equal(state.node_states.B.phase,'ready');assert.equal(state.node_states.C.phase,'pending');
  assert.throws(()=>apply(state,'assess',{action_id:state.node_states.A.assess_action_id,outcome:'success',
    checks:[{description:'Verify A',status:'passed',refs:[receipt(state,'A').ref],explanation:'Observed'}],summary:'Done'}),/completed work/i);
});
test('retained incomplete completed record can retry without applying new completion requirements',()=>{
  let state=start(apply(null,'plan',plan(graph())).state,'A');
  state=apply(state,'execution_settled',{action_id:action(state,'A'),status:'completed'}).state;
  state=apply(state,'record',record(state,'A',{outcome:'limited',outputs:[],limitations:['Old partial output']}),{receipts:[receipt(state,'A')]}).state;
  // Shape of a previously accepted checkpoint, before complete-record admission.
  const legacy=record(state,'A',{outputs:[]});state.executions[0].record=structuredClone(legacy);
  const before=structuredClone(state);assert.doesNotThrow(()=>projectEnterpriseGraph(state,limits));
  assert.deepEqual(apply(state,'record',legacy).state,before);
  assert.throws(()=>apply(state,'record',{...legacy,limitations:['Changed retry']}),/Conflicting record retry/);
});
test('interleaved receipts and graph changes preserve action ownership and identity',()=>{
  let state=start(start(apply(null,'plan',plan(graph())).state,'A'),'B');
  const a=graphAction(state,action(state,'A')),b=graphAction(state,action(state,'B'));
  state=apply(state,'revise',{nodes:[...graph(),node('free')],reason:'Add independent question',rerun:[]}).state;
  assert.deepEqual(graphAction(state,a.id),a);assert.deepEqual(graphAction(state,b.id),b);
  const before=structuredClone(state);
  assert.throws(()=>apply(state,'record',record(state,'A'),{receipts:[receipt(state,'B')]}));
  assert.deepEqual(state,before);
  state=finish(state,'B');assert.equal(state.node_states.A.phase,'executing');
  state=finish(state,'A');assert.equal(state.node_states.A.phase,'success');
});
test('future slots freeze an immutable binding and synthesis needs no new receipt',()=>{
  let state=start(apply(null,'plan',plan(graph())).state,'A');state=finish(state,'A');state=start(state,'C');
  const binding=structuredClone(state.node_states.C.input_bindings),ref=state.results[0].result_ref;
  state=apply(state,'execution_settled',{action_id:action(state,'C'),status:'completed'}).state;
  state=apply(state,'record',record(state,'C',{outputs:[{slot:'opaque.slot',observation_refs:[receipt(state,'A').ref],artifact_refs:[],
    summary:'Synthesis from exact selected result',scope:'Selected result only'}]})).state;
  assert.deepEqual(state.node_states.C.input_bindings,binding);assert.deepEqual(state.results[1].consumed_results,[ref]);
  assert.deepEqual(state.executions.find(item=>item.step_id==='C').successful_receipts,[]);
  assert.equal(apply(state,'resolve',{result_ref:ref}).result.result_ref,state.results[0].result_ref);
  assert.equal(apply(state,'resolve',{result_ref:ref}).result.summary,state.results[0].summary);
});
test('recompute gives a new result identity, keeps prior bindings, and marks only affected work stale',()=>{
  let state=start(start(apply(null,'plan',plan(graph())).state,'A'),'B');
  const artifactOutput={slot:'opaque.slot',observation_refs:['obs-A-1'],artifact_refs:[],summary:'Same result',scope:'Same scope'};
  state=finish(state,'A',{outputs:[artifactOutput]});state=finish(start(state,'C'),'C');
  const originalResult=structuredClone(state.results[0]),oldBinding=structuredClone(state.node_states.C.input_bindings);
  const revision={nodes:graph(),reason:'Check concrete discrepancy',rerun:[{step_id:'A',reason,supersedes:[originalResult.result_ref]}]};
  state=apply(state,'revise',revision,{sources:['diagnostic']}).state;
  state=start(state,'A');state=finish(state,'A',{outputs:[{...artifactOutput,observation_refs:['obs-A-2']}]});
  assert.notEqual(state.results.at(-1).result_ref,originalResult.result_ref);
  assert.deepEqual(state.results[0],originalResult);assert.deepEqual(state.results.at(-1).supersedes,[originalResult.result_ref]);
  assert.equal(state.node_states.C.applicability,'stale');assert.equal(state.node_states.C.phase,'success');
  assert.equal(state.node_states.B.applicability,'current');assert.equal(state.node_states.B.phase,'executing');
  assert.deepEqual(state.node_states.C.input_bindings,oldBinding);
  assert.throws(()=>start(state,'C'),/revision|ready|stale/i);
  state=apply(state,'revise',{nodes:graph(),reason:'Use the replacement explicitly',rerun:[{step_id:'C',reason,supersedes:[state.results[1].result_ref]}]},
    {sources:['diagnostic']}).state;
  state=start(state,'C');assert.equal(state.node_states.C.input_bindings[0].result_ref,state.results.at(-1).result_ref);
  assert.deepEqual(state.executions.find(item=>item.step_id==='C'&&item.execution_revision===1).input_bindings,oldBinding);
});
test('rejects graph errors, missing grants, duplicate names and unknown keys before start',()=>{
  const bad=[
    [node('A',{depends_on:['absent']})],
    [node('A',{depends_on:['B']}),node('B',{depends_on:['A']})],
    [node('A'),node('C',{inputs:[{name:'x',from:{step_id:'A',slot:'opaque.slot'}}]})],
    [node('A'),node('C',{depends_on:['A'],inputs:[{name:'x',from:{step_id:'A',slot:'absent'}}]})],
    [node('A',{inputs:[{name:'x',result_ref:'invented'}]})],
    [node('A',{inputs:[{name:'x',result_ref:'admitted'},{name:'x',result_ref:'admitted'}]})],
    [node('A',{shell:'not allowed'})],
    [node('A',{id:'bad/id'})],
  ];
  for(const nodes of bad)assert.throws(()=>apply(null,'plan',plan(nodes)));
  const foreign={schema:'capstone-task-result/1',result_ref:'foreign',owner:{...owner,work_id:'other'}};
  assert.throws(()=>apply(null,'plan',plan([node('A',{inputs:[{name:'x',result_ref:'foreign'}]})]),{results:[foreign]}));
});
test('rejects invented outputs, failed observations, cross-owner admissions and started-definition changes',()=>{
  let state=start(apply(null,'plan',plan([node('A')])).state,'A');
  state=apply(state,'execution_settled',{action_id:action(state,'A'),status:'completed'}).state;
  for(const extra of [{},{receipts:[receipt(state,'A',{owner:{...owner,work_id:'other'}})]},
    {receipts:[receipt(state,'A',{status:'failed'})]}])assert.throws(()=>apply(state,'record',record(state,'A'),extra));
  assert.throws(()=>apply(state,'record',record(state,'A',{outputs:[{slot:'opaque.slot',observation_refs:[],artifact_refs:['invented'],summary:'Fake',scope:'Fake'}]})));
  assert.throws(()=>apply(state,'revise',{nodes:[node('A',{instruction:'Changed started definition'})],reason:'Changed',rerun:[]}));
});
test('retries are idempotent and issued actions retain exact execution identity',()=>{
  let state=apply(null,'plan',plan([node('opaque-step.2')])).state;
  const pending=structuredClone(state);state=start(state,'opaque-step.2');
  const repeat=start(state,'opaque-step.2');assert.deepEqual(repeat,state);assert.equal(pending.node_states['opaque-step.2'].phase,'ready');
  const settled={action_id:action(state,'opaque-step.2'),status:'completed'};
  state=apply(state,'execution_settled',settled).state;
  assert.deepEqual(apply(state,'execution_settled',settled).state,state);
  const request=record(state,'opaque-step.2'),extra={receipts:[receipt(state,'opaque-step.2')]};
  state=apply(state,'record',request,extra).state;assert.deepEqual(apply(state,'record',request,extra).state,state);
  assert.throws(()=>apply(state,'record',{...request,limitations:['Changed retry']},extra),/retry|record/i);
});
test('bounded public projections omit private host fields and reject excess input capacities',()=>{
  const state=apply(null,'plan',plan([node('A')]),{workspace:'/private/workspace',credentials:'SECRET'}).state;
  const publicGraph=projectEnterpriseGraph(state,limits),serialized=JSON.stringify(publicGraph);
  assert.ok(!serialized.includes('/private'));assert.ok(!serialized.includes('SECRET'));assert.equal(publicGraph.nodes[0].id,'A');
  assert.throws(()=>projectEnterpriseGraph(state,{...limits,publicBytes:20}),error=>error.code==='research_capacity_exceeded');
  assert.throws(()=>apply(null,'plan',plan([node('A',{purpose:'x'.repeat(4097)})])));
  assert.throws(()=>apply(null,'plan',plan([node('A'),node('B')]),{},{...limits,maxNodes:1}),error=>error.code==='research_capacity_exceeded');
});
test('artifact content can deduplicate while every computation retains a separate result version',()=>{
  const nodes=[node('make',{outputs:[{slot:'opaque.slot',kind:'artifact',description:'Inspected bytes'}]})];
  let state=start(apply(null,'plan',plan(nodes)).state,'make');
  const save=current=>{
    const product={ref:'artifact-same-hash',action_id:action(current,'make'),attempt_id:'attempt',owner,status:'ready',path:'/private/never/project'};
    return finish(current,'make',{outputs:[{slot:'opaque.slot',observation_refs:[receipt(current,'make').ref],artifact_refs:[product.ref],summary:'Same bytes',scope:'Same scope'}],hostExtra:{products:[product]}});
  };
  state=save(state);const old=structuredClone(state.results[0]),execution=structuredClone(state.executions[0]);
  state=apply(state,'revise',{nodes,reason:'Observed change needs a check',rerun:[{step_id:'make',reason,supersedes:[old.result_ref]}]},
    {sources:['diagnostic']}).state;
  state=save(start(state,'make'));
  assert.equal(state.results.length,2);assert.notEqual(state.results[1].result_ref,old.result_ref);
  assert.deepEqual(state.results[0],old);assert.deepEqual(state.executions[0],execution);
  assert.deepEqual(state.results[1].artifact_refs,old.artifact_refs);
  assert.ok(!JSON.stringify(projectEnterpriseGraph(state,limits)).includes('/private'));
});
test('source and method provenance use host versions, with unavailable fields explicit',()=>{
  let state=start(apply(null,'plan',{...plan([node('A',{source_refs:['source-v1']})]),source_refs:['source-v1']},{sources:[{ref:'source-v1',revision:'sha256-source'}]}).state,'A');
  const computation={action_id:action(state,'A'),source_versions:[{ref:'source-v1',revision:'sha256-source'}],
    method:{ref:'method-v1',revision:'git-sha',parameters_sha256:'a'.repeat(64),environment_unavailable:'Executor did not publish an environment identity'}};
  state=finish(state,'A',{hostExtra:{computation}});
  assert.deepEqual(state.results[0].source_versions,computation.source_versions);assert.deepEqual(state.results[0].method,computation.method);
  let other=start(apply(null,'plan',plan([node('A')])).state,'A');other=finish(other,'A');
  assert.deepEqual(other.results[0].source_versions,[]);assert.ok(other.results[0].method.unavailable);
  const running=start(apply(null,'plan',plan([node('A')])).state,'A');
  assert.throws(()=>finish(running,'A',{hostExtra:{computation:{...computation,action_id:action(running,'A'),source_versions:[{ref:'invented',revision:'made-up'}]}}}),/source version/i);
});
test('admitted immutable external results can drive synthesis without fresh work or invented provenance',()=>{
  let producer=start(apply(null,'plan',plan([node('external')])).state,'external');producer=finish(producer,'external');
  const manifest=producer.results[0],nodes=[node('consume',{mode:'synthesis',checks:[],inputs:[{name:'selected',result_ref:manifest.result_ref}]})];
  let state=start(apply(null,'plan',plan(nodes),{results:[manifest]}).state,'consume');
  state=apply(state,'execution_settled',{action_id:action(state,'consume'),status:'completed'}).state;
  state=apply(state,'record',record(state,'consume',{outputs:[{slot:'opaque.slot',observation_refs:manifest.observation_refs,artifact_refs:[],
    summary:'Actual synthesis',scope:'Admitted result'}]})).state;
  state=apply(state,'assess',{action_id:state.node_states.consume.assess_action_id,outcome:'success',checks:[],summary:'Accepted synthesis'}).state;
  assert.deepEqual(state.results[0].consumed_results,[manifest.result_ref]);
  assert.throws(()=>apply(state,'resolve',{result_ref:'invented'}));
  assert.throws(()=>apply(state,'resolve',{result_ref:manifest.result_ref},{results:[{...manifest,summary:'Changed immutable grant'}]}),/immutable/i);
});
test('rejects malformed external manifests and private source/method versions',()=>{
  let producer=start(apply(null,'plan',plan([node('external')])).state,'external');producer=finish(producer,'external');
  const manifest=producer.results[0],request=plan([node('consume',{mode:'synthesis',inputs:[{name:'selected',result_ref:manifest.result_ref}]})]);
  for(const result of [{...manifest,extra:'unexpected'},
    {...manifest,method:{ref:'method',revision:'v1'}},
    {...manifest,source_versions:[{ref:'/private/source',revision:'v1'}]},
    {...manifest,method:{unavailable:'x'.repeat(4097)}}]){
    assert.throws(()=>apply(null,'plan',request,{results:[result]}),/manifest|method|source|capacity|field/i);
  }
});
test('unknown native outcomes remain visible and do not permit blind replacement execution',()=>{
  let state=start(apply(null,'plan',plan([node('A')])).state,'A');
  state=apply(state,'execution_settled',{action_id:action(state,'A'),status:'unknown'}).state;
  assert.throws(()=>apply(state,'record',record(state,'A'),{receipts:[receipt(state,'A')]}),/completed execution/i);
  state=apply(state,'record',record(state,'A',{outcome:'limited',outputs:[],limitations:['Native result was lost']})).state;
  state=apply(state,'assess',{action_id:state.node_states.A.assess_action_id,outcome:'limited',checks:[],summary:'Unknown result retained'}).state;
  assert.equal(state.executions[0].settled_status,'unknown');
  assert.throws(()=>apply(state,'revise',{nodes:[node('A')],reason:'Try again',rerun:[{step_id:'A',reason,supersedes:[]}]},{sources:['diagnostic']}),/unknown|reconcil/i);
});
test('public actions expose running or assessable work while settled leases remain resolvable',()=>{
  let state=start(apply(null,'plan',plan([node('A')])).state,'A');const execute=action(state,'A');
  assert.deepEqual(projectEnterpriseGraph(state,limits).actions.map(item=>item.id),[execute]);
  state=finish(state,'A',{assess:false});const assess=state.node_states.A.assess_action_id;
  assert.deepEqual(projectEnterpriseGraph(state,limits).actions.map(item=>item.id),[assess]);
  state=apply(state,'start',{step_id:'A',kind:'assess'}).state;assert.equal(state.node_states.A.phase,'assessing');
  const assessment={action_id:assess,outcome:'success',checks:[{description:'Verify A',status:'passed',refs:[receipt(state,'A').ref],explanation:'Observed'}],summary:'Accepted'};
  state=apply(state,'assess',assessment).state;
  assert.deepEqual(projectEnterpriseGraph(state,limits).actions,[]);assert.equal(graphAction(state,execute).id,execute);
  assert.deepEqual(apply(state,'assess',assessment).state,state);
});
test('synthesis preserves distinct source versions and deduplicates identical inherited provenance',()=>{
  const makeManifest=(id,version)=>{
    let producer=start(apply(null,'plan',{...plan([node(id,{source_refs:['source']})]),source_refs:['source']},
      {sources:[{ref:'source',revision:version}]}).state,id);
    producer=finish(producer,id,{hostExtra:{sources:[{ref:'source',revision:version}],computation:{
      source_versions:[{ref:'source',revision:version}],method:{unavailable:'Method not published'}}}});
    return producer.results[0];
  };
  const left=makeManifest('left','v1');
  for(const right of [makeManifest('right','v1'),makeManifest('right','v2')]){
    const consume=node('combine',{mode:'synthesis',checks:[],inputs:[{name:'left',result_ref:left.result_ref},{name:'right',result_ref:right.result_ref}]});
    let state=start(apply(null,'plan',plan([consume]),{results:[left,right]}).state,'combine');
    state=apply(state,'execution_settled',{action_id:action(state,'combine'),status:'completed'}).state;
    state=apply(state,'record',record(state,'combine',{outputs:[{slot:'opaque.slot',observation_refs:[...left.observation_refs,...right.observation_refs],
      artifact_refs:[],summary:'Compare exact versions',scope:'Both selected versions'}]})).state;
    assert.deepEqual(state.results[0].source_versions,right.source_versions[0].revision==='v1'?[{ref:'source',revision:'v1'}]:
      [{ref:'source',revision:'v1'},{ref:'source',revision:'v2'}]);
  }
});
test('duplicate named bindings to one future slot are rejected',()=>{
  const nodes=[node('A'),node('C',{depends_on:['A'],inputs:[{name:'one',from:{step_id:'A',slot:'opaque.slot'}},
    {name:'two',from:{step_id:'A',slot:'opaque.slot'}}]})];
  assert.throws(()=>apply(null,'plan',plan(nodes)),/duplicate/i);
});
test('immutable graph identity includes the declared goal, output mode and original source context',()=>{
  const request=plan([node('A')]),baseline=apply(null,'plan',request).state.graph_ref;
  for(const payload of [{...request,goal:'A different goal'},{...request,output_mode:'files'},
    {...request,source_refs:['source']}])assert.notEqual(apply(null,'plan',payload,{sources:[{ref:'source',revision:'v1'}]}).state.graph_ref,baseline);
});
test('public graph and committed event proposals preserve every native settlement outcome after assessment and replay',()=>{
  for(const status of ['completed','failed','cancelled','unknown']){
    let state=start(apply(null,'plan',plan([node('A')])).state,'A');
    const settledPayload={action_id:action(state,'A'),status};
    const transition=apply(state,'execution_settled',settledPayload);state=transition.state;
    assert.equal(transition.graph.nodes[0].settled_status,status);
    assert.equal(transition.events.length,1);assert.equal(transition.events[0].kind,'node_execution_settled');
    assert.equal(transition.events[0].settled_status,status);assert.equal(transition.events[0].action_id,action(state,'A'));
    assert.deepEqual(apply(state,'execution_settled',settledPayload).events,[]);
    const completed=status==='completed';
    state=apply(state,'record',record(state,'A',completed?{}:{outcome:'limited',outputs:[],limitations:['Native outcome: '+status]}),
      completed?{receipts:[receipt(state,'A')]}:{}).state;
    const assessed=apply(state,'assess',{action_id:state.node_states.A.assess_action_id,outcome:completed?'success':'limited',
      checks:completed?[{description:'Verify A',status:'passed',refs:[receipt(state,'A').ref],explanation:'Observed'}]:[],summary:'Assessed'});
    assert.equal(assessed.graph.nodes[0].settled_status,status);assert.equal(assessed.events[0].settled_status,status);
    assert.deepEqual(projectEnterpriseGraph(structuredClone(assessed.state),limits),assessed.graph);
    assert.ok(Buffer.byteLength(JSON.stringify(transition.events))<=limits.publicBytes);
  }
});
test('resolve returns approved public result fields while private host resolution preserves the exact manifest',()=>{
  assert.equal(typeof resolveEnterpriseGraphResultForHost,'function');
  let state=start(apply(null,'plan',plan([node('A')])).state,'A');
  state=finish(state,'A',{outputs:[{slot:'opaque.slot',observation_refs:[receipt(state,'A').ref],artifact_refs:[],
    summary:'Saved at /private/workspace/internal.csv',scope:'Bearer synthetic-secret'}]});
  const manifest=structuredClone(state.results[0]),resolved=apply(state,'resolve',{result_ref:manifest.result_ref});
  assert.equal(resolved.result.summary,'Saved at [private reference]');assert.equal(resolved.result.scope,'[protected]');
  assert.deepEqual(resolved.result,resolved.graph.results[0]);assert.equal(resolved.result.owner,undefined);
  assert.deepEqual(Object.keys(resolved.result).sort(),['schema','result_ref','producer','slot','kind','source_versions','method','consumed_results',
    'observation_refs','artifact_refs','summary','scope','supersedes','recompute_reason'].sort());
  assert.deepEqual(resolveEnterpriseGraphResultForHost(state,manifest.result_ref,limits),manifest);
  assert.deepEqual(state.results[0],manifest);assert.deepEqual(resolved.state.results[0],manifest);
  assert.ok(!JSON.stringify(resolved.result).includes('/private/'));assert.ok(!JSON.stringify(resolved.result).includes('synthetic-secret'));
});
test('external result resolution has an independent public budget and explicit private host budget',()=>{
  assert.equal(typeof resolveEnterpriseGraphResultForHost,'function');
  let producer=start(apply(null,'plan',plan([node('external')])).state,'external');producer=finish(producer,'external');
  const manifest={...producer.results[0],summary:'x'.repeat(4000)};
  const state=apply(null,'plan',plan([node('A')]),{results:[manifest]}).state;
  assert.deepEqual(projectEnterpriseGraph(state,limits).results,[]);
  const bytes=Buffer.byteLength(JSON.stringify(manifest));
  assert.throws(()=>apply(state,'resolve',{result_ref:manifest.result_ref},{},{...limits,resultBytes:1024}),
    error=>error.code==='research_capacity_exceeded'&&error.capacity.dimension==='graph_public_result_bytes');
  assert.throws(()=>resolveEnterpriseGraphResultForHost(state,manifest.result_ref,{...limits,resultBytes:1024}),
    error=>error.code==='research_capacity_exceeded'&&error.capacity.dimension==='graph_private_result_bytes');
  assert.deepEqual(resolveEnterpriseGraphResultForHost(state,manifest.result_ref,{...limits,resultBytes:bytes}),manifest);
  assert.throws(()=>apply(state,'resolve',{result_ref:manifest.result_ref},{},{...limits,publicBytes:2048}),
    error=>error.code==='research_capacity_exceeded'&&error.capacity.dimension==='graph_public_result_bytes');
  assert.throws(()=>apply(state,'resolve',{result_ref:manifest.result_ref},{},{...limits,resultBytes:0}));
});
