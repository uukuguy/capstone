import test from 'node:test';
import assert from 'node:assert/strict';
import {createModelRequestPool} from '../../src/capstone_agent/resources/model-request-pool.mjs';
const gate=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};};
const tick=()=>new Promise(setImmediate);
const model={id:'model',provider:'private'};
const context=text=>({messages:[{role:'user',content:text}],tools:[]});
function source(hold,{failure,result={role:'assistant',content:[{type:'text',text:'actual'}],stopReason:'stop'}}={}){
 return {async *[Symbol.asyncIterator](){yield {type:'text_delta',delta:'actual'};await hold.promise;if(failure)throw failure;yield {type:'done',message:result};},result:async()=>{await hold.promise;if(failure)throw failure;return result;}};
}
async function consume(stream){const events=[];for await(const event of stream)events.push(event);return {events,result:await stream.result()};}
test('returns an immediate stream and bounds actual runtime calls across independent chains',async()=>{
 const held=[gate(),gate(),gate()],calls=[],events=[];
 const runtime={tag:'runtime',getModel(){return this.tag;},streamSimple(...args){calls.push(args);return source(held[calls.length-1]);}};
 const dispatcher=createModelRequestPool({runtime,concurrency:2,maxRequests:5,emit:event=>events.push(event)});
 const a=dispatcher.runtime.streamSimple(model,context('main'));
 const b=dispatcher.forChain('analysis:b',{kind:'analysis',child_id:'b',parent_tool_call_id:'submit'}).streamSimple(model,context('B'));
 const c=dispatcher.forChain('analysis:c',{kind:'analysis',child_id:'c',parent_tool_call_id:'submit'}).streamSimple(model,context('C'));
 assert.equal(typeof a[Symbol.asyncIterator],'function');assert.equal(typeof a.result,'function');assert.equal(calls.length,0);
 const results=[consume(a),consume(b),consume(c)];await tick();assert.equal(calls.length,2);assert.equal(dispatcher.runtime.getModel(),'runtime');
 held[1].resolve();await tick();assert.equal(calls.length,3);assert.equal(dispatcher.snapshot().active,2);
 held[0].resolve();held[2].resolve();const actual=await Promise.all(results);assert.equal(actual[0].result.content[0].text,'actual');
 assert.ok(events.every(event=>!JSON.stringify(event).includes('private')&&!('messages' in event)));
 await dispatcher.close();
});
test('snapshots queued contexts/models/options while retaining callback references',async()=>{
 const hold=gate(),calls=[],fn=()=>{};
 const runtime={streamSimple(...args){calls.push(args);return source(calls.length===1?hold:{promise:Promise.resolve()});}};
 const dispatcher=createModelRequestPool({runtime,concurrency:1,maxRequests:3});
 const a=dispatcher.runtime.streamSimple(model,context('block'));
 const mutableModel={...model},ctx=context('original'),options={headers:{name:'original'},onPayload:fn};
 const b=dispatcher.forChain('analysis:b',{child_id:'b',parent_tool_call_id:'submit'}).streamSimple(mutableModel,ctx,options);
 mutableModel.id='mutated';ctx.messages[0].content='mutated';options.headers.name='mutated';await tick();assert.equal(calls.length,1);
 hold.resolve();await Promise.all([a.result(),b.result()]);
 assert.equal(calls[1][0].id,'model');assert.equal(calls[1][1].messages[0].content,'original');assert.equal(calls[1][2].headers.name,'original');assert.equal(calls[1][2].onPayload,fn);
 await dispatcher.close();
});
test('same-chain requests wait for predecessor cleanup even when a provider returns an error message',async()=>{
 const hold=gate(),calls=[];const failed={role:'assistant',stopReason:'error',content:[],errorMessage:'actual failure'};
 const dispatcher=createModelRequestPool({runtime:{streamSimple(...args){calls.push(args);return source(calls.length===1?hold:{promise:Promise.resolve()},{result:calls.length===1?failed:undefined});}},concurrency:2,maxRequests:3});
 const first=dispatcher.runtime.streamSimple(model,context('one')),second=dispatcher.runtime.streamSimple(model,context('two'));
 await tick();assert.equal(calls.length,1);hold.resolve();assert.equal((await first.result()).stopReason,'error');await second.result();assert.equal(calls.length,2);
 assert.deepEqual(dispatcher.snapshot().jobs[1].depends_on,['request-1']);await dispatcher.close();
});
test('provider throws reach both consumers without a fabricated message and do not retry or poison a chain',async()=>{
 let calls=0;const failure=Error('actual transport failure');
 const dispatcher=createModelRequestPool({runtime:{streamSimple(){calls++;if(calls===1)throw failure;return source({promise:Promise.resolve()});}},concurrency:1,maxRequests:3});
 const first=dispatcher.runtime.streamSimple(model,context('one'));
 await assert.rejects(first.result(),/actual transport failure/);await assert.rejects(consume(first),/actual transport failure/);
 const second=dispatcher.runtime.streamSimple(model,context('two'));await second.result();assert.equal(calls,2);await dispatcher.close();
});
test('queued caller abort never invokes runtime; running cancellation holds capacity until source drains',async()=>{
 const hold=gate(),calls=[],firstAbort=new AbortController(),queuedAbort=new AbortController();
 const dispatcher=createModelRequestPool({runtime:{streamSimple(...args){calls.push(args);return source(calls.length===1?hold:{promise:Promise.resolve()});}},concurrency:1,maxRequests:5});
 const first=dispatcher.runtime.streamSimple(model,context('active'),{signal:firstAbort.signal});
 const queued=dispatcher.forChain('analysis:q',{child_id:'q',parent_tool_call_id:'submit'}).streamSimple(model,context('never'),{signal:queuedAbort.signal});
 queuedAbort.abort();await assert.rejects(queued.result(),{name:'AbortError'});await assert.rejects(consume(queued),{name:'AbortError'});
 await tick();firstAbort.abort();await tick();assert.equal(calls.length,1);assert.equal(calls[0][2].signal.aborted,true);assert.equal(dispatcher.snapshot().active,1);
 const later=dispatcher.forChain('analysis:later',{child_id:'later',parent_tool_call_id:'submit'}).streamSimple(model,context('later'));
 await tick();assert.equal(calls.length,1);hold.resolve();await assert.rejects(first.result(),{name:'AbortError'});await later.result();assert.equal(calls.length,2);await dispatcher.close();
});
test('timeout begins at execution, closes drain real sources, and request budget never resets by chain name',async()=>{
 const hold=gate(),events=[];let actualSignal;
 const dispatcher=createModelRequestPool({runtime:{streamSimple(_m,_c,options){actualSignal=options.signal;return source(hold);}},concurrency:1,maxRequests:1,requestTimeoutMs:10,emit:event=>events.push(event)});
 const stream=dispatcher.runtime.streamSimple(model,context('one'));await new Promise(resolve=>setTimeout(resolve,25));
 assert.equal(actualSignal.aborted,true);assert.equal(dispatcher.snapshot().active,1);assert.ok(events.some(e=>e.status==='cancelling'));
 assert.throws(()=>dispatcher.forChain('analysis:new',{child_id:'new',parent_tool_call_id:'submit'}).streamSimple(model,context('extra')),/budget/);
 let closed=false;const closing=dispatcher.close().then(()=>{closed=true;});await tick();assert.equal(closed,false);
 hold.resolve();await closing;await assert.rejects(stream.result(),{name:'AbortError'});
 assert.equal(dispatcher.snapshot().active,0);
});
test('iterator failure alone retains a slot until the provider result has also drained',async()=>{
 const hold=gate(),failure=Error('stream interrupted');let calls=0;
 const dispatcher=createModelRequestPool({runtime:{streamSimple(){calls++;return calls===1?{
  async *[Symbol.asyncIterator](){throw failure;},result:()=>hold.promise,
 }:source({promise:Promise.resolve()});}},concurrency:1,maxRequests:2});
 const first=dispatcher.runtime.streamSimple(model,context('first'));
 const next=dispatcher.forChain('analysis:next',{child_id:'next',parent_tool_call_id:'submit'}).streamSimple(model,context('next'));
 await tick();assert.equal(calls,1);assert.equal(dispatcher.snapshot().active,1);
 hold.resolve({role:'assistant',content:[],stopReason:'error'});
 await assert.rejects(first.result(),/stream interrupted/);await assert.rejects(consume(first),/stream interrupted/);
 await next.result();assert.equal(calls,2);await dispatcher.close();
});
test('caller listeners are released and close cannot relabel a returned success as cancelled',async()=>{
 const controller=new AbortController(),events=[];let added=0,removed=0;
 const add=controller.signal.addEventListener.bind(controller.signal),remove=controller.signal.removeEventListener.bind(controller.signal);
 controller.signal.addEventListener=(...args)=>{added++;return add(...args);};controller.signal.removeEventListener=(...args)=>{removed++;return remove(...args);};
 const dispatcher=createModelRequestPool({runtime:{streamSimple(){return source({promise:Promise.resolve()});}},concurrency:1,maxRequests:2,emit:event=>events.push(event)});
 const stream=dispatcher.runtime.streamSimple(model,context('one'),{signal:controller.signal});await stream.result();await dispatcher.close();
 assert.equal(added,removed);assert.equal(events.at(-1).status,'completed');assert.ok(!events.some(event=>event.status==='cancelling'));
});
test('captures host SDK turn identity at submission without publishing callbacks or context',async()=>{
 const events=[];let turn=3;
 const dispatcher=createModelRequestPool({runtime:{streamSimple(){return source({promise:Promise.resolve()});}},concurrency:2,maxRequests:4,emit:event=>events.push(event)});
 const main=dispatcher.forChain('main',{kind:'main',getModelTurnNumber:()=>turn});
 await main.streamSimple(model,context('secret')).result();await main.streamSimple(model,context('retry same SDK turn')).result();
 turn=4;await main.streamSimple(model,context('next SDK turn')).result();
 const analysis=dispatcher.forChain('analysis:a',{kind:'analysis',child_id:'a',parent_tool_call_id:'submit',title:'Inspect supplied numbers',getModelTurnNumber:()=>1});
 await analysis.streamSimple(model,context('private')).result();await dispatcher.close();
 const queued=events.filter(event=>['queued','waiting_dependencies'].includes(event.status));
 assert.deepEqual([...new Map(queued.map(event=>[event.request_id,event.model_turn_number])).values()],[3,3,4,1]);
 assert.equal(events.find(e=>e.chain_id==='main').title,'LLM 3');assert.equal(events.find(e=>e.chain_id==='analysis:a').title,'Inspect supplied numbers');
 assert.ok(events.every(event=>!('getModelTurnNumber' in event)&&!('context' in event)));
});
test('chain-local debug wrappers cannot mutate the provider or recursively requeue actual execution',async()=>{
 let actual=0,wrapped=0;const original=function(){actual++;return source({promise:Promise.resolve()});};
 const runtime={streamSimple:original};
 const dispatcher=createModelRequestPool({runtime,concurrency:2,maxRequests:4});
 const main=dispatcher.runtime,child=dispatcher.forChain('analysis:child',{child_id:'child',parent_tool_call_id:'submit'});
 const before=main.streamSimple;assert.equal(main.streamSimple,before);
 main.streamSimple=(...args)=>{wrapped++;return before(...args);};
 assert.equal(runtime.streamSimple,original);assert.notEqual(child.streamSimple,main.streamSimple);
 await Promise.all([main.streamSimple(model,context('main')).result(),child.streamSimple(model,context('child')).result()]);
 assert.equal(actual,2);assert.equal(wrapped,1);main.streamSimple=before;assert.equal(main.streamSimple,before);
 await dispatcher.close();
});
test('snapshots actual SDK tool definitions with trusted functions rather than rejecting the whole request',async()=>{
 const execute=()=>{},prepareArguments=value=>value,seen=[];
 const tool={name:'read',parameters:{type:'object',properties:{path:{type:'string'}}},execute,prepareArguments};
 const ctx={messages:[{role:'user',content:'read the file'}],tools:[tool]};
 const dispatcher=createModelRequestPool({runtime:{streamSimple(_model,context){seen.push(context);return source({promise:Promise.resolve()});}},concurrency:1,maxRequests:2});
 const stream=dispatcher.runtime.streamSimple(model,ctx);tool.parameters.properties.path.type='number';ctx.messages[0].content='changed';
 await stream.result();assert.equal(seen[0].messages[0].content,'read the file');assert.equal(seen[0].tools[0].execute,execute);
 assert.equal(seen[0].tools[0].prepareArguments,prepareArguments);assert.equal(seen[0].tools[0].parameters.properties.path.type,'string');await dispatcher.close();
});
test('chain drain remains pending after consumer cancellation until provider cleanup, without blocking other chains',async()=>{
 const hold=gate(),cancel=new AbortController();let calls=0;
 const dispatcher=createModelRequestPool({runtime:{streamSimple(){calls++;return source(calls===1?hold:{promise:Promise.resolve()});}},concurrency:2,maxRequests:4});
 const child=dispatcher.forChain('analysis:child',{child_id:'child',parent_tool_call_id:'submit'});
 const stream=child.streamSimple(model,context('uncertain'),{signal:cancel.signal});await tick();cancel.abort();
 await assert.rejects(stream.result(),{name:'AbortError'});
 let drained=false;const draining=dispatcher.drainChain('analysis:child').then(()=>{drained=true;});await tick();assert.equal(drained,false);
 await dispatcher.runtime.streamSimple(model,context('independent')).result();assert.equal(calls,2);assert.equal(drained,false);
 hold.resolve();await draining;assert.equal(drained,true);await dispatcher.close();
});
test('close drains chain barriers only after active sources settle and idle chains need no polling',async()=>{
 const hold=gate();const dispatcher=createModelRequestPool({runtime:{streamSimple(){return source(hold);}},concurrency:1,maxRequests:2});
 const stream=dispatcher.runtime.streamSimple(model,context('one'));await tick();let drained=false;
 const draining=dispatcher.drainChain('main').then(()=>{drained=true;});const closing=dispatcher.close();await tick();assert.equal(drained,false);
 await assert.rejects(stream.result(),{name:'AbortError'});hold.resolve();await Promise.all([draining,closing]);assert.equal(drained,true);
 await dispatcher.drainChain('main');await dispatcher.drainChain('analysis:never-created');
});
test('never-started cancellation drains its chain without waiting on an unrelated active provider',async()=>{
 const hold=gate(),abort=new AbortController();let calls=0;
 const dispatcher=createModelRequestPool({runtime:{streamSimple(){calls++;return source(calls===1?hold:{promise:Promise.resolve()});}},concurrency:1,maxRequests:4});
 const main=dispatcher.runtime.streamSimple(model,context('held'));await tick();
 const child=dispatcher.forChain('analysis:child',{child_id:'child',parent_tool_call_id:'submit'});
 const queued=child.streamSimple(model,context('never executed'),{signal:abort.signal});abort.abort();
 await assert.rejects(queued.result(),{name:'AbortError'});
 let drained=false;const barrier=dispatcher.drainChain('analysis:child').then(()=>{drained=true;});await tick();
 assert.equal(drained,true);assert.equal(calls,1);await barrier;
 const explicit=child.streamSimple(model,context('explicit new request'),{signal:new AbortController().signal});await tick();
 assert.equal(calls,1);assert.equal(dispatcher.snapshot().jobs.at(-1).status,'queued');
 assert.deepEqual(dispatcher.snapshot().jobs.at(-1).depends_on,['request-2']);
 hold.resolve();await Promise.all([main.result(),explicit.result()]);assert.equal(calls,2);await dispatcher.close();
});
