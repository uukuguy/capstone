import test from 'node:test';
import assert from 'node:assert/strict';
import {taskTurnGuidance} from '../../src/capstone_agent/resources/task-turn-guidance.mjs';

test('draft guidance changes work depth without cancelling execution or declaring completion',()=>{
  const policy={mode:'usable_draft',target_seconds:240,integration_reserve_seconds:60};
  const start=100000;
  const first=taskTurnGuidance(policy,start,start+30000);
  assert.equal(first.phase,'work');assert.equal(first.remaining_seconds,210);
  const integrate=taskTurnGuidance(policy,start,start+181000);
  assert.equal(integrate.phase,'integration');
  const expired=taskTurnGuidance(policy,start,start+301000);
  assert.equal(expired.phase,'deliver_available');assert.equal(expired.remaining_seconds,0);
  assert.equal(expired.advisory_only,true);
  assert.match(expired.instruction,/not.*cancel|not.*failure/i);
  assert.doesNotMatch(JSON.stringify(expired),/abort_signal|cancel_at|outcome|goal_completed/);
});
test('guidance is explicit and preserves the host origin across consumers',()=>{
  assert.equal(taskTurnGuidance(undefined,100,200),undefined);
  const policy={mode:'usable_draft',target_seconds:240,integration_reserve_seconds:60};
  const shared=taskTurnGuidance(policy,100000,120000);
  assert.equal(taskTurnGuidance(shared,shared.started_at_ms,180000).elapsed_seconds,80);
  assert.throws(()=>taskTurnGuidance({...policy,integration_reserve_seconds:240},100000,120000),/guidance/i);
});
