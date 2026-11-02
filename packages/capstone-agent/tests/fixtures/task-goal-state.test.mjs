import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createTaskGoal,reviewTaskGoal,validateTaskGoalFinish} from '../../src/capstone_agent/resources/task-goal-state.mjs';
const requirements=[{id:'finding',description:'Answer the substantive question',kind:'finding'},
  {id:'report',description:'Deliver the requested document',kind:'artifact'}];
const context={basis:'basis:1',review_ref:'review:1',hard_deadline_reached:false,
  results:[{result_ref:'result:1',kind:'observation',artifact_refs:[],phase:'success'},
    {result_ref:'result:2',kind:'artifact',artifact_refs:['file:1'],phase:'success'}]};
const item=(id,status,result_refs=[],extra={})=>({id,status,result_refs,explanation:'Actual coverage',...extra});
test('a research turn can explicitly deliver limited findings while keeping unmet requirements visible',()=>{
  const goal=reviewTaskGoal(createTaskGoal(requirements),{decision:'limited',requirements:[
    item('finding','satisfied',['result:1']),item('report','open')],summary:'Useful analysis; requested document remains open for follow-up'},context);
  const delivery={outcome:'limited',goal_review_ref:'review:1',delivery_result_refs:['result:1'],delivery_product_refs:[],limitations:['The requested document is not included']};
  assert.doesNotThrow(()=>validateTaskGoalFinish(goal,delivery,context));
  assert.throws(()=>validateTaskGoalFinish(goal,{...delivery,outcome:'success'},context),/limited/);
  assert.throws(()=>validateTaskGoalFinish(goal,{...delivery,limitations:[]},context),/limitations/);
  assert.throws(()=>validateTaskGoalFinish(goal,{...delivery,delivery_result_refs:[]},context),/retained/);
});
test('partial task success cannot close the whole goal; a current full review can',()=>{
  const goal=createTaskGoal(requirements);
  assert.throws(()=>validateTaskGoalFinish(goal,{outcome:'limited',goal_review_ref:'review:1'},context),/review/);
  const partial=reviewTaskGoal(goal,{decision:'continue',requirements:[item('finding','satisfied',['result:1']),item('report','open')],summary:'More work needed'},context);
  assert.throws(()=>validateTaskGoalFinish(partial,{outcome:'limited',goal_review_ref:'review:1'},context),/unfinished/);
  const complete=reviewTaskGoal(partial,{decision:'complete',requirements:[item('finding','satisfied',['result:1']),item('report','satisfied',['result:2'])],summary:'All required outputs accepted'},context);
  assert.doesNotThrow(()=>validateTaskGoalFinish(complete,{outcome:'success',goal_review_ref:'review:1',delivery_result_refs:['result:1','result:2'],delivery_product_refs:['file:1']},context));
  assert.throws(()=>validateTaskGoalFinish(complete,{outcome:'success',goal_review_ref:'review:1'}, {...context,basis:'basis:2'}),/stale/);
});
test('coverage cannot omit requirements, invent refs, replace artifacts or claim a soft timeout',()=>{
  const goal=createTaskGoal(requirements);
  const assess=items=>reviewTaskGoal(goal,{decision:'complete',requirements:items,summary:'Claim'},context);
  assert.throws(()=>assess([item('finding','satisfied',['result:1'])]),/unfinished/);
  assert.throws(()=>assess([item('finding','satisfied',['unknown']),item('report','satisfied',['result:2'])]),/current/);
  assert.throws(()=>assess([item('finding','satisfied',['result:1']),item('report','satisfied',['result:1'])]),/artifact/);
  assert.throws(()=>reviewTaskGoal(goal,{decision:'blocked',requirements:[item('finding','satisfied',['result:1']),item('report','blocked',[],{blocker:{kind:'hard_limit',explanation:'Estimated time is insufficient'}})],summary:'Stop'},context),/deadline/);
  const blocked=reviewTaskGoal(goal,{decision:'blocked',requirements:[item('finding','satisfied',['result:1']),item('report','blocked',[],{blocker:{kind:'missing_input',explanation:'Required source absent'}})],summary:'Need input'},context);
  assert.throws(()=>validateTaskGoalFinish(blocked,{outcome:'limited',goal_review_ref:'review:1'},context),/failure/);
  assert.doesNotThrow(()=>validateTaskGoalFinish(blocked,{outcome:'failure',goal_review_ref:'review:1'},context));
});
test('incremental coverage retains current prior support and keeps unreviewed requirements open',()=>{
  const first=reviewTaskGoal(createTaskGoal(requirements),{decision:'continue',requirements:[item('finding','satisfied',['result:1'])],summary:'Finding ready'},context);
  assert.equal(first.review.requirements.find(item=>item.id==='report').status,'open');
  const update={decision:'complete',requirements:[item('report','satisfied',['result:2'])],summary:'Document ready'};
  const final=reviewTaskGoal(first,update,{...context,basis:'basis:2',review_ref:'review:2'});
  assert.equal(final.review.requirements.find(item=>item.id==='finding').status,'satisfied');
  assert.deepEqual(final.review.requirements.find(item=>item.id==='finding').result_refs,['result:1']);
  assert.throws(()=>reviewTaskGoal(first,update,{...context,results:context.results.filter(item=>item.result_ref!=='result:1')}),/unfinished/);
  assert.throws(()=>reviewTaskGoal(first,{...update,requirements:[item('unknown','open')]},context),/registered/);
});
