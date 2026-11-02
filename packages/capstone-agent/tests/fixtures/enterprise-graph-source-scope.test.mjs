import test from 'node:test';
import assert from 'node:assert/strict';
import {reduceEnterpriseGraph,graphAction,projectEnterpriseGraph} from '../../src/capstone_agent/resources/enterprise-graph-state.mjs';
const limits={maxNodes:16,maxItems:64,maxText:4096,maxExecutions:64,snapshotBytes:500000,publicBytes:100000};
const owner={thread_id:'thread',work_id:'work',research_id:'research',goal_revision:1};
const sources=[{ref:'raw-A',revision:'v1'},{ref:'raw-B',revision:'v1'},{ref:'outside-plan',revision:'v1'}];
const host=(extra={})=>({owner,attempt_id:'attempt',sources,receipts:[],products:[],...extra});
const node=(id,extra={})=>({id,purpose:id,questions:['Question'],checks:[],depends_on:[],expected_outputs:['Finding'],
  mode:'execute',execution:'delegated',instruction:'Inspect selected inputs',source_refs:[],outputs:[{slot:'finding',kind:'observation',description:'Finding'}],inputs:[],...extra});
const run=(state,op,payload,extra={})=>reduceEnterpriseGraph(state,op,payload,host(extra),limits).state;
const plan=nodes=>run(null,'plan',{goal:'Compare selected inputs',output_mode:'text',source_refs:['raw-A','raw-B'],nodes});
const started=(state,id)=>run(state,'start',{step_id:id});
function finish(state,id,extra={}){
  const action_id=state.node_states[id].execute_action_id,ref='obs-'+action_id;
  state=run(state,'execution_settled',{action_id,status:'completed'});
  state=run(state,'record',{action_id,outcome:'completed',outputs:[{slot:'finding',observation_refs:[ref],artifact_refs:[],summary:'Finding',scope:'Selected inputs'}],limitations:[]},
    {receipts:[{ref,owner,attempt_id:'attempt',action_id,status:'completed'}],...extra});
  return run(state,'assess',{action_id:state.node_states[id].assess_action_id,outcome:'success',checks:[],summary:'Accepted'});
}
test('node raw source selection is explicit, unique and inside graph grants',()=>{
  for(const refs of [['unknown'],['raw-A','raw-A'],['outside-plan']])
    assert.throws(()=>plan([node('A',{source_refs:refs})]),/source/i);
  const missing=node('A');delete missing.source_refs;
  assert.throws(()=>plan([missing]),/missing|source/i);
  assert.deepEqual(plan([node('A',{source_refs:['raw-A']})]).nodes[0].source_refs,['raw-A']);
});
test('each action freezes selected raw versions and result-only lineage excludes unrelated originals',()=>{
  const nodes=[node('A',{source_refs:['raw-A']}),node('B',{source_refs:['raw-B']}),
    node('C',{mode:'synthesis',depends_on:['A'],inputs:[{name:'first',from:{step_id:'A',slot:'finding'}}]})];
  let state=started(plan(nodes),'A');const a=graphAction(state,state.node_states.A.execute_action_id);
  assert.deepEqual(a.source_refs,['raw-A']);assert.deepEqual(a.source_versions,[sources[0]]);
  state=finish(state,'A');state=started(state,'B');state=finish(state,'B');state=started(state,'C');
  const c=graphAction(state,state.node_states.C.execute_action_id);
  assert.deepEqual(c.source_refs,[]);assert.deepEqual(c.source_versions,[]);
  assert.deepEqual(c.input_bindings[0].source_versions,[sources[0]]);
  assert.throws(()=>finish(state,'C',{computation:{source_versions:[sources[1]],method:{unavailable:'No method'}}}),/source version/i);
  state=finish(state,'C');assert.deepEqual(state.results.at(-1).source_versions,[sources[0]]);
  assert.deepEqual(state.results.at(-1).consumed_results,[state.results[0].result_ref]);
  const assessment=graphAction(state,state.node_states.C.assess_action_id);
  assert.deepEqual(assessment.source_refs,[]);assert.deepEqual(assessment.source_versions,[]);
  assert.deepEqual(projectEnterpriseGraph(state,limits).nodes[0].selected_source_versions,[sources[0]]);
});
test('host computation metadata cannot erase the selected raw or upstream lineage',()=>{
  let state=started(plan([node('A',{source_refs:['raw-A']})]),'A');
  state=finish(state,'A',{computation:{source_versions:[],method:{unavailable:'No method'}}});
  assert.deepEqual(state.results[0].source_versions,[sources[0]]);
});
test('source changes require explicit settled rerun and preserve old actions, results and consumers',()=>{
  let nodes=[node('A',{source_refs:['raw-A']}),node('C',{mode:'synthesis',depends_on:['A'],inputs:[{name:'first',from:{step_id:'A',slot:'finding'}}]})];
  let state=started(plan(nodes),'A');const oldAction=graphAction(state,state.node_states.A.execute_action_id);
  state=finish(state,'A');state=started(state,'C');const oldConsumer=graphAction(state,state.node_states.C.execute_action_id);
  const oldResult=structuredClone(state.results[0]);
  nodes=[node('A',{source_refs:['raw-B']}),nodes[1]];
  assert.throws(()=>run(state,'revise',{nodes,reason:'Change selected source',rerun:[]}),/immutable|rerun/i);
  state=run(state,'revise',{nodes,reason:'Observed source change',rerun:[{step_id:'A',reason:{kind:'source_changed',refs:['raw-B']},supersedes:[oldResult.result_ref]}]},
    {sources:[sources[0],{ref:'raw-B',revision:'v2'}]});
  state=started(state,'A');const replacement=graphAction(state,state.node_states.A.execute_action_id);
  assert.deepEqual(replacement.source_versions,[{ref:'raw-B',revision:'v2'}]);assert.notEqual(replacement.id,oldAction.id);
  assert.deepEqual(graphAction(state,oldAction.id),oldAction);assert.deepEqual(graphAction(state,oldConsumer.id),oldConsumer);
  assert.deepEqual(state.results[0],oldResult);
});
test('pre-field graph snapshots stay readable without implicit grant migration',()=>{
  let state=plan([node('A',{source_refs:['raw-A']})]);delete state.nodes[0].source_refs;delete state.node_states.A.selected_source_versions;
  const before=structuredClone(state);assert.equal(projectEnterpriseGraph(state,limits).nodes[0].source_refs,undefined);
  assert.throws(()=>started(state,'A'),/source selection|legacy|revis/i);assert.deepEqual(state,before);
  state=run(state,'revise',{nodes:[node('A',{source_refs:[]})],reason:'Explicitly select result-only scope',rerun:[]});
  assert.deepEqual(graphAction(started(state,'A'),started(state,'A').node_states.A.execute_action_id).source_refs,[]);
});
