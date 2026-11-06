import test from 'node:test';
import assert from 'node:assert/strict';
import {createToolCallScheduler} from '../../src/capstone_agent/resources/tool-call-scheduler.mjs';

test('FIFO exclusive lease waits for readers and blocks later readers',async()=>{
 const gate=createToolCallScheduler(2),order=[];
 const a=await gate.acquire(),b=await gate.acquire();
 const writer=gate.acquire({exclusive:true}).then(release=>{order.push('writer');return release;});
 const reader=gate.acquire().then(release=>{order.push('reader');return release;});
 a();await Promise.resolve();assert.deepEqual(order,[]);
 b();const w=await writer;assert.deepEqual(order,['writer']);
 w();const r=await reader;assert.deepEqual(order,['writer','reader']);r();r();
 const done=await gate.acquire({exclusive:true});done();
});

test('aborting a queued waiter removes it without releasing an active lease',async()=>{
 const gate=createToolCallScheduler(1),active=await gate.acquire();
 const controller=new AbortController();
 const cancelled=gate.acquire({signal:controller.signal});
 const rejected=assert.rejects(cancelled,/cancelled/);controller.abort(Error('cancelled'));await rejected;
 let started=false;const next=gate.acquire().then(release=>{started=true;return release;});
 await Promise.resolve();assert.equal(started,false);active();(await next)();
 assert.throws(()=>gate.acquire({signal:controller.signal}),/cancelled/);
});
