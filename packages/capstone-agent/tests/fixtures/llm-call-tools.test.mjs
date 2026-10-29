import test from 'node:test';
import assert from 'node:assert/strict';
import {createLlmCallTools,buildLlmCallPrompt} from '../../src/capstone_agent/resources/llm-call-tools.mjs';
const policy={schema:'capstone-llm-call-pool/1',concurrency:2,max_jobs:12,max_input_chars:16000,max_output_chars:8000,call_timeout_ms:120000,max_wait_ms:30000};
const tick=()=>new Promise(resolve=>setImmediate(resolve));
const parse=result=>JSON.parse(result.content[0].text);
test('assembled dependency answers are included in the context budget before any model invocation',()=>{
  const input={instruction:'Integrate observed results',input:'Facts'};
  assert.throws(()=>buildLlmCallPrompt(input,Array.from({length:11},()=>({answer:'x'.repeat(8000)})),policy),/input budget/);
  const prompt=buildLlmCallPrompt(input,[{answer:'Limited observation',answer_truncated:true}],policy);
  assert.equal(JSON.parse(prompt).prerequisites[0].answer_truncated,true);
  assert.ok(prompt.length<=policy.max_input_chars);
});
test('submission returns before child completion and only actual completed output is delivered',async()=>{
  let finish;const messages=[];
  const pool=createLlmCallTools({policy,run:()=>new Promise(resolve=>{finish=resolve})});
  pool.setCompletionSink(async result=>messages.push(result));
  const receipt=parse(await pool.tools[0].execute('submit',{calls:[{id:'a',instruction:'Analyze supplied facts',input:'Known observations'}]}));
  assert.equal(receipt.results.length,0);assert.equal(receipt.pool.jobs[0].status,'running');
  await tick();assert.equal(messages.length,0);
  finish({status:'completed',answer:'Observed result'});await tick();await pool.flush();
  assert.equal(messages[0].results[0].result.answer,'Observed result');
  assert.ok(await pool.continuation(),'a result arriving during the final answer still needs integration');
  pool.acknowledge(['a']);assert.equal(await pool.continuation(),undefined);await pool.close();
});
test('identical unresolved requests cannot be relaunched under another ID',async()=>{
  let finish;const pool=createLlmCallTools({policy,run:()=>new Promise(resolve=>{finish=resolve})});
  const call={instruction:'Compute interpretation',input:'Supplied facts'};
  await pool.tools[0].execute('one',{calls:[{id:'a',...call}]});await tick();
  await assert.rejects(pool.tools[0].execute('two',{calls:[{id:'b',...call}]}),/duplicate/i);
  finish({status:'completed',answer:'Done'});await tick();await pool.close();
});
test('uncollected jobs prevent silent finalization and explicit collection retains failed observations',async()=>{
  const pool=createLlmCallTools({policy,run:async()=>({status:'failed',error:{code:'provider_rejected'}})});
  await pool.tools[0].execute('s',{calls:[{id:'a',instruction:'Analyze facts',input:'facts'}]});await tick();
  assert.match((await pool.continuation()).prompt,/collect|cancel/i);
  const result=parse(await pool.tools[1].execute('c',{wait_ms:0}));
  assert.equal(result.results[0].status,'failed');assert.equal(result.results[0].result.error.code,'provider_rejected');
  pool.acknowledge(['a']);assert.equal(await pool.continuation(),undefined);await pool.close();
});
test('caller cannot select endpoints, extra capabilities or exceed text budgets',async()=>{
  let starts=0;const pool=createLlmCallTools({policy,run:async()=>{starts++;return {status:'completed',answer:'x'}}});
  for(const calls of [[{id:'a',instruction:'x',input:'x',model:'other'}],[{id:'b',instruction:'x',input:'x'.repeat(16001)}]])
    await assert.rejects(pool.tools[0].execute('bad',{calls}),/Invalid|budget/);
  assert.equal(starts,0);await pool.close();
});
