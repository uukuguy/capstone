import test from 'node:test';
import assert from 'node:assert/strict';
import {scheduleDelegation} from '../src/capstone_agent/resources/delegation-scheduler.mjs';

const gate=()=>{let resolve;const promise=new Promise(r=>{resolve=r;});return {promise,resolve};};
const done=answer=>({status:'completed',answer});

test('ready work overlaps, queued work fills a released slot, dependencies wait',async()=>{
  const gates=Object.fromEntries(['a','b','c'].map(id=>[id,gate()])),started=[];
  const work=scheduleDelegation({jobs:[{id:'a'},{id:'b'},{id:'c'},{id:'d',depends_on:['a','b']}],concurrency:2,
    run:async(job,dependencies)=>{started.push(job.id);if(gates[job.id])await gates[job.id].promise;
      if(job.id==='d')assert.deepEqual(dependencies.map(x=>x.answer),['a','b']);return done(job.id);}});
  await new Promise(setImmediate);assert.deepEqual(started,['a','b']);
  gates.a.resolve();await new Promise(setImmediate);assert.deepEqual(started,['a','b','c']);
  gates.b.resolve();await new Promise(setImmediate);assert.deepEqual(started,['a','b','c','d']);
  gates.c.resolve();assert.deepEqual((await work).map(x=>x.answer),['a','b','c','d']);
});
test('failed prerequisites block descendants but independent work completes',async()=>{
  const started=[];
  const results=await scheduleDelegation({jobs:[{id:'a'},{id:'b',depends_on:['a']},{id:'c',depends_on:['b']},{id:'d'}],concurrency:2,
    run:async job=>{started.push(job.id);return job.id==='a'?{status:'failed'}:done(job.id);}});
  assert.deepEqual(started,['a','d']);assert.deepEqual(results.map(x=>x.status),['failed','blocked','blocked','completed']);
  assert.deepEqual(results[1].blocked_by,['a']);
});
test('invalid graphs fail before execution',async()=>{
  for(const jobs of [[{id:'a'},{id:'a'}],[{id:'a',depends_on:['x']}],[{id:'a',depends_on:['b']},{id:'b',depends_on:['a']}],
    [{id:'a',depends_on:['a']}],[{id:'a',depends_on:['b','b']},{id:'b'}]]){
    await assert.rejects(scheduleDelegation({jobs,concurrency:2,run:()=>assert.fail('must not start')}),TypeError);
  }
});
test('cancellation does not launch queued nodes and drains active work',async()=>{
  const abort=new AbortController(),hold=gate(),started=[];let settled=false;
  const work=scheduleDelegation({jobs:[{id:'a'},{id:'b'}],concurrency:1,signal:abort.signal,
    run:async job=>{started.push(job.id);await hold.promise;return done(job.id);}}).then(r=>{settled=true;return r;});
  await new Promise(setImmediate);abort.abort();await new Promise(setImmediate);assert.equal(settled,false);
  hold.resolve();const results=await work;assert.deepEqual(started,['a']);assert.equal(results[1].status,'cancelled');
});
test('runner exceptions drain siblings and prevent dependent work',async()=>{
  const hold=gate();let siblingSettled=false;
  const work=scheduleDelegation({jobs:[{id:'a'},{id:'b'},{id:'c',depends_on:['a']}],concurrency:2,
    run:async job=>{if(job.id==='a')throw Error('transport');if(job.id==='c')assert.fail('dependent started');
      await hold.promise;siblingSettled=true;return done('b');}});
  await new Promise(setImmediate);hold.resolve();await assert.rejects(work,/transport/);assert.equal(siblingSettled,true);
});
