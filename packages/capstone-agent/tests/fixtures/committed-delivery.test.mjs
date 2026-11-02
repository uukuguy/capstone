import test from 'node:test';
import assert from 'node:assert/strict';
import {configureCommittedDelivery,finalizeCommittedDelivery} from '../../src/capstone_agent/resources/committed-delivery.mjs';
import {runSettledPrompt} from '../../src/capstone_agent/resources/general-sdk.mjs';

const delivery={outcome:'limited',summary:'报告已保存；气象覆盖不完整。',delivery_result_refs:['result:one'],delivery_product_refs:['artifact:one'],limitations:['气象覆盖不完整']};
test('only a persisted successful finish stops the model loop at the tool boundary',async()=>{
  const handlers={},pi={on:(name,fn)=>{handlers[name]=fn;}},controller={readState:async()=>({delivery})};
  const state=configureCommittedDelivery(pi,controller);let stopped=0;
  const context={abort:()=>stopped++};
  await handlers.tool_result({toolName:'read'},context);assert.equal(stopped,0);
  await handlers.tool_result({toolName:'agent_research_finish',isError:true},context);assert.equal(stopped,0);
  await handlers.tool_result({toolName:'agent_research_finish',isError:false,details:{ok:true,result:{delivery}}},context);
  assert.equal(stopped,0);assert.equal(state.delivery().summary,delivery.summary);
  assert.equal(finalizeCommittedDelivery({details:{ok:true,result:{delivery}}}).terminate,true);
  assert.equal(finalizeCommittedDelivery({isError:true,details:{ok:true,result:{delivery}}}).terminate,undefined);
});
test('committed delivery preserves actual accounting without fabricating a final model response',async()=>{
  let listener,calls=0;const events=[];
  const session={subscribe:fn=>{listener=fn;return()=>{};},async prompt(){calls++;
    listener({type:'agent_end',messages:[{role:'assistant',stopReason:'toolUse',usage:{input:11,output:2},content:[]}]});}};
  await runSettledPrompt(session,{kind:'text',text:'Generate report'},null,event=>events.push(event),()=>{throw Error('No continuation after committed delivery');},{delivery:()=>delivery});
  assert.equal(calls,1);const end=events.at(-1);
  assert.deepEqual(end.committed_delivery,delivery);assert.equal(end.messages.length,1);
  assert.equal(end.messages[0].stopReason,'toolUse');assert.equal(end.messages[0].usage.input,11);
  assert.deepEqual(end.messages[0].content,[]);
});
