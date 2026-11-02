import test from 'node:test';
import assert from 'node:assert/strict';
import * as capacity from '../src/runtime-limits.mjs';

test('zero MCP total budget permits sequential calls and positive budget is exact',()=>{
  const unlimited=capacity.runtimeLimits({mcp_call_count:0});
  assert.equal(capacity.observeCapacity(unlimited,'mcp_call_count',1025,'items','mcp_call'),false);
  const stream=capacity.runtimeLimits({provider_stream_bytes:0});
  capacity.checkCapacity(stream,'provider_stream_bytes',100000000,'bytes','provider');
  assert.equal(capacity.observeCapacity(stream,'provider_stream_bytes',100000000,'bytes','provider'),false);
  for(let count=1;count<=1025;count++)capacity.checkCapacity(unlimited,'mcp_call_count',count,'items','mcp_call');
  const bounded=capacity.runtimeLimits({mcp_call_count:2});
  capacity.checkCapacity(bounded,'mcp_call_count',2,'items','mcp_call');
  assert.throws(()=>capacity.checkCapacity(bounded,'mcp_call_count',3,'items','mcp_call'),capacity.CapacityExceeded);
});

test('debug soft exceedance permits recovery and hard checks remain typed',()=>{
  const normal=capacity.runtimeLimits({answer_summary_chars:5});
  assert.equal(capacity.observeCapacity(normal,'answer_summary_chars',6,'characters','summary'),true);
  assert.equal(capacity.observeCapacity(normal,'answer_summary_chars',5,'characters','summary'),false);
  const debug=capacity.runtimeLimits({answer_summary_chars:5},{mode:'debug'});
  assert.equal(capacity.runtimeLimitMode(capacity.runtimeLimits(debug)),'debug');
  assert.equal(capacity.runtimeLimitMode(normal),'normal');
  assert.ok(Object.values(debug).every(Number.isSafeInteger));
  assert.equal(capacity.observeCapacity(debug,'answer_summary_chars',6,'characters','summary'),true);
  assert.throws(()=>capacity.checkCapacity(debug,'answer_summary_chars',6,'characters','summary'),error=>
    error instanceof capacity.CapacityExceeded&&error.mode==='debug'&&error.capacity.actual===6&&error.capacity.limit===5);
  assert.throws(()=>capacity.checkCapacity(normal,'answer_summary_chars',6,'characters','summary'),capacity.CapacityExceeded);
  assert.throws(()=>capacity.runtimeLimits({}, {mode:'silent'}),/mode/);
  assert.throws(()=>capacity.checkCapacity(normal,'missing_dimension',100,'items','test'),/unknown|invalid/);
});

test('debug fatal subscriber receives original typed cause synchronously even when caller catches it',()=>{
  const events=[],debug=capacity.runtimeLimits({answer_summary_chars:1},{mode:'debug'});
  const unsubscribe=capacity.onDebugCapacityExceeded(error=>events.push(error));
  let caught;
  try{capacity.checkCapacity(debug,'answer_summary_chars',2,'characters','test');}catch(error){caught=error;}
  assert.equal(events.length,1);assert.equal(events[0],caught);
  unsubscribe();
  assert.throws(()=>capacity.checkCapacity(debug,'answer_summary_chars',3,'characters','test'),capacity.CapacityExceeded);
  assert.equal(events.length,1);
});
