import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,mkdir,writeFile,rm,realpath} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {configureResearchTools} from '../../../pi-capability-tools/src/research-tools.mjs';
const {windowResearchContext}=await import('../../src/capstone_agent/resources/research-context-window.mjs').catch(e=>{
  if(e.code==='ERR_MODULE_NOT_FOUND')return {};throw e;
});
test('oversized model context becomes an explicit recoverable window without altering the ledger',()=>{
  assert.equal(typeof windowResearchContext,'function');
  const value={research_id:'research',research_revision:5,goal:'Deliver all findings',cycle:{checkpoint:{ref:'checkpoint',revision:5},
    organization:{requirements:[{id:'report',kind:'artifact',description:'Deliver report'}],review:{decision:'continue'}},
    graph:{schema:'capstone-enterprise-graph/2',graph_ref:'graph:current',graph_revision:3,
      nodes:Array.from({length:12},(_,i)=>({id:'task-'+i,phase:'success',purpose:'Inspect source'})),
      current_results:Array.from({length:12},(_,i)=>({result_ref:'result-'+i,summary:'事实'.repeat(18000),scope:'Observed'}))}}};
  const before=JSON.stringify(value);
  const page=windowResearchContext(value,{limit:4000,offset:0,pageSize:4});
  assert.ok(Array.from(JSON.stringify(page)).length<=4000);
  assert.equal(page.goal,value.goal);assert.equal(page.cycle.organization.requirements[0].id,'report');
  assert.equal(page.cycle.graph.graph_ref,'graph:current');
  assert.equal(page.coverage.context_window.complete,false);
  assert.equal(page.coverage.context_window.next_offset,4);
  assert.equal(page.coverage.context_window.collections['cycle.graph.current_results'].total,12);
  assert.match(page.coverage.context_window.recovery,/overview/);
  const next=windowResearchContext(value,{limit:4000,offset:4,pageSize:4});
  assert.equal(next.cycle.graph.current_results[0].result_ref,'result-4');
  assert.equal(JSON.stringify(value),before);
});
test('small context remains exact and later pages retain exact identities',()=>{
  const value={goal:'Goal',cycle:{graph:{graph_ref:'graph:exact',nodes:[{id:'one'},{id:'two'}]}}};
  assert.deepEqual(windowResearchContext(value,{limit:65536}),value);
  const page=windowResearchContext(value,{limit:65536,offset:1,pageSize:1});
  assert.deepEqual(page.cycle.graph.nodes,[{id:'two'}]);
  assert.equal(page.coverage.context_window.next_offset,null);
});

test('minimal recovery context preserves the retained goal scope',()=>{
  const value={goal:'Old request',goal_scope:'retained_work_background',scope_notice:'The current user instruction controls this turn.',
    state_scope:{kind:'research_bookkeeping',attempt_id:'current',live_environment_observation:false},
    cycle:{graph:{nodes:[{id:'x'.repeat(8000)}]}}};
  const page=windowResearchContext(value,{limit:1500});
  assert.equal(page.goal_scope,value.goal_scope);
  assert.equal(page.scope_notice,value.scope_notice);
  assert.deepEqual(page.state_scope,value.state_scope);
});

test('debug mode oversized graph context keeps the request guard ready and supports overview pages',async()=>{
  const root=await realpath(await mkdtemp(join(tmpdir(),'research-window-'))),hooks={},tools={};
  const identity={run_id:'run',turn_id:'turn',attempt_id:'attempt',research_id:'research'};
  try{
    await mkdir(join(root,'requests'));await mkdir(join(root,'receipts'));
    await writeFile(join(root,'binding.json'),JSON.stringify({schema_version:'capability-research-channel/1.0',...identity,
      read_tool_schema:{type:'object',additionalProperties:false,properties:{section:{type:'string'},offset:{type:'integer'},limit:{type:'integer'}}},
      update_tool_schema:{type:'object',additionalProperties:false,properties:{changes:{},expected_revision:{}}}}));
    await writeFile(join(root,'view.json'),JSON.stringify({schema_version:'capability-research-view/1.0',...identity,research_revision:1,
      state:{research_id:'research',revision:1,goal:'Whole goal',claims:[],notes:[],open_questions:[]}}));
    const cycle={organization:{requirements:[{id:'required',description:'Required work',kind:'finding'}]},
      graph:{schema:'capstone-enterprise-graph/2',graph_ref:'graph:one',current_results:Array.from({length:20},(_,i)=>({result_ref:'result-'+i,summary:'a'.repeat(10000)}))}};
    configureResearchTools({on:(name,fn)=>{hooks[name]=fn;},registerTool:tool=>{tools[tool.name]=tool;}},root,
      {runtimeLimitMode:'debug',runtimeLimits:{research_summary_chars:4000},boundedGraphContext:true,retainedWorkBackground:true,
        getControllerState:async()=>structuredClone(cycle),fatal:message=>assert.fail(message)});
    const prepared=await hooks.context({messages:[]});assert.ok(prepared.messages[0].content.length<=4000);
    const projected=JSON.parse(prepared.messages[0].content.split('\n').slice(1).join('\n'));
    assert.equal(projected.goal_scope,'retained_work_background');
    assert.deepEqual(projected.state_scope,{kind:'research_bookkeeping',turn_id:'turn',attempt_id:'attempt',
      research_id:'research',live_environment_observation:false});
    assert.match(projected.scope_notice,/current user instruction/);
    await hooks.before_model_request({context:{messages:[{role:'user',content:prepared.messages[0].content}]}});
    const page=await tools.agent_research_read.execute('page',{section:'overview',offset:8,limit:4});
    assert.equal(page.details.ok,true);assert.equal(page.details.result.cycle.graph.current_results[0].result_ref,'result-8');
    assert.deepEqual(page.details.result.state_scope,projected.state_scope);
  }finally{await rm(root,{recursive:true,force:true});}
});
