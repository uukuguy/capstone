import test from 'node:test';
import assert from 'node:assert/strict';
import {runProcessCapability} from '../src/process-transport.mjs';
import {CapacityExceeded} from '../src/runtime-limits.mjs';

const payload={request_id:'capacity-test'};
const runtime=source=>({executable:process.execPath,executableArgs:['-e',source],protocol:'test',protocolVersion:'1'});
test('normal observation overage is a graded response; debug rejects typed without resolving a tool result',async()=>{
  const result=await runProcessCapability(payload,runtime('process.stdout.write("1234")'),
    {timeoutMs:1000,maxOutputBytes:3},process.env);
  assert.equal(result.error.code,'capability_transport_output_limit');
  await assert.rejects(runProcessCapability(payload,runtime('process.stdout.write("1234")'),
    {timeoutMs:1000,maxOutputBytes:3,runtimeLimitMode:'debug'},process.env),error=>
      error instanceof CapacityExceeded&&error.mode==='debug'&&error.dimension==='tool_observation_bytes'&&error.limit===3);
});
test('debug time budget rejects typed instead of returning normal transport timeout',async()=>{
  await assert.rejects(runProcessCapability(payload,runtime('setTimeout(()=>{},10000)'),
    {timeoutMs:20,maxOutputBytes:100,runtimeLimitMode:'debug'},process.env),error=>
      error instanceof CapacityExceeded&&error.mode==='debug'&&error.dimension==='tool_timeout_seconds'&&error.limit===.02);
});
