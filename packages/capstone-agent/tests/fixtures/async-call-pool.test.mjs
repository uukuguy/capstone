import test from 'node:test';
import assert from 'node:assert/strict';
import {createAsyncCallPool} from '../../src/capstone_agent/resources/async-call-pool.mjs';

const gate=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};};
const tick=()=>new Promise(setImmediate);
const done=value=>({status:'completed',value});
const state=(pool,id)=>pool.snapshot().jobs.find(job=>job.id===id);

test('independent completions are consumed while a slow call runs and slots refill',async()=>{
  const slow=gate(),started=[];
  const pool=createAsyncCallPool({concurrency:2,maxJobs:5,run:async job=>{
    started.push(job.id);if(job.id==='slow')await slow.promise;return done(job.id);
  }});
  pool.submit([{id:'slow',input:{}},{id:'fast',input:{}},{id:'next',input:{}}]);
  await tick();assert.deepEqual(started,['slow','fast','next']);
  assert.deepEqual(pool.drainReady().map(job=>job.id),['fast','next']);
  assert.deepEqual(pool.drainReady(),[]);assert.equal(state(pool,'slow').status,'running');
  assert.equal((await pool.waitForCompletion({waitMs:1})).reason,'timeout');
  slow.resolve();await tick();assert.equal((await pool.waitForCompletion()).reason,'completion');
  await pool.close();
});

test('dependencies may refer to prior submissions; failures block only descendants',async()=>{
  const hold=gate(),seen=[];
  const pool=createAsyncCallPool({concurrency:2,maxJobs:8,run:async(job,{dependencyResults})=>{
    seen.push([job.id,dependencyResults]);if(job.id==='a')await hold.promise;
    return job.id==='bad'?{status:'failed',code:'source_missing'}:done(job.id);
  }});
  pool.submit([{id:'a'},{id:'bad'},{id:'blocked',depends_on:['bad']},{id:'ok'}]);
  pool.submit([{id:'dependent',depends_on:['a']}]);
  assert.equal(state(pool,'dependent').status,'waiting_dependencies');
  await tick();assert.equal(state(pool,'blocked').status,'blocked');assert.equal(state(pool,'ok').status,'completed');
  hold.resolve();await tick();assert.deepEqual(seen.find(([id])=>id==='dependent')[1],[done('a')]);
  assert.equal(state(pool,'dependent').status,'completed');await pool.close();
});

test('submission is atomic for cycles, duplicate identities and total host budget',async()=>{
  const hold=gate();const pool=createAsyncCallPool({concurrency:1,maxJobs:3,run:()=>hold.promise});
  pool.submit([{id:'a',attemptKey:'exact-request'}]);
  for(const jobs of [[{id:'b'},{id:'a'}],[{id:'b',depends_on:['c']},{id:'c',depends_on:['b']}],
    [{id:'b',depends_on:['missing']}],[{id:'b',attemptKey:'exact-request'}],
    [{id:'b',attemptKey:'new'},{id:'c',attemptKey:'new'}],[{id:'b'},{id:'c'},{id:'d'}]]){
    assert.throws(()=>pool.submit(jobs));assert.equal(pool.snapshot().jobs.length,1);
  }
  pool.cancel(['a']);assert.throws(()=>pool.submit([{id:'retry',attemptKey:'exact-request'}]));
  hold.resolve(done('a'));await tick();
  pool.submit([{id:'retry',attemptKey:'exact-request'}]);await tick();await pool.close();
});

test('cancel and per-call timeout reserve slots until actual cleanup settles',async()=>{
  let clock=10;const timers=new Map();let sequence=0;const signals=[],started=[];const hold=gate();
  const pool=createAsyncCallPool({concurrency:1,maxJobs:3,now:()=>clock,
    setTimer:(fn,ms)=>{const id=++sequence;timers.set(id,{fn,ms});return id;},clearTimer:id=>timers.delete(id),
    run:async(job,{signal})=>{started.push(job.id);signals.push(signal);if(job.id==='a')await hold.promise;return done(job.id);}});
  pool.submit([{id:'a',timeoutMs:25},{id:'b',timeoutMs:25}]);await tick();
  assert.equal(timers.size,1);assert.equal([...timers.values()][0].ms,25);
  clock=35;[...timers.values()][0].fn();
  assert.equal(signals[0].aborted,true);assert.equal(state(pool,'a').status,'cancelling');
  assert.deepEqual(started,['a']);assert.equal(state(pool,'b').status,'queued');
  pool.cancel(['a']);hold.resolve();await tick();
  assert.deepEqual(started,['a','b']);assert.equal(state(pool,'a').status,'cancelled');
  assert.equal(state(pool,'a').cancelReason,'timeout');assert.equal(state(pool,'b').startedAt,35);
  await pool.close();assert.equal(timers.size,0);
});

test('parent cancellation stops queued calls and close waits for owned cleanup',async()=>{
  const parent=new AbortController(),hold=gate();let closed=false,signal;
  const pool=createAsyncCallPool({concurrency:1,maxJobs:3,signal:parent.signal,run:async(_job,control)=>{signal=control.signal;await hold.promise;return done('saved');}});
  pool.submit([{id:'a'},{id:'b'}]);await tick();parent.abort();
  assert.equal(signal.aborted,true);assert.equal(state(pool,'b').status,'cancelled');
  const closing=pool.close().then(()=>{closed=true;});await tick();assert.equal(closed,false);
  assert.throws(()=>pool.submit([{id:'c'}]));hold.resolve();await closing;
  assert.equal(pool.snapshot().active,0);assert.equal(state(pool,'a').result.value,'saved');
});

test('bounded wait cancellation removes listeners and does not cancel a running call',async()=>{
  const parent=new AbortController(),waitAbort=new AbortController(),hold=gate();
  let added=0,removed=0;const add=waitAbort.signal.addEventListener.bind(waitAbort.signal),remove=waitAbort.signal.removeEventListener.bind(waitAbort.signal);
  waitAbort.signal.addEventListener=(...args)=>{added++;return add(...args);};
  waitAbort.signal.removeEventListener=(...args)=>{removed++;return remove(...args);};
  const pool=createAsyncCallPool({concurrency:1,maxJobs:1,signal:parent.signal,run:()=>hold.promise});
  pool.submit([{id:'a'}]);const wait=pool.waitForCompletion({signal:waitAbort.signal,waitMs:50});waitAbort.abort();
  assert.equal((await wait).reason,'aborted');assert.equal(added,removed);assert.equal(state(pool,'a').status,'running');
  hold.resolve(done('a'));await tick();assert.equal((await pool.waitForCompletion()).reason,'completion');
  pool.drainReady();assert.equal((await pool.waitForCompletion()).reason,'idle');await pool.close();
});

test('thrown and invalid runner outcomes are bounded per-job diagnostics, not global abort',async()=>{
  const pool=createAsyncCallPool({concurrency:2,maxJobs:3,run:async job=>{
    if(job.id==='throws')throw Error('private credential must never escape');
    if(job.id==='invalid')return {status:'invented'};return done('ok');
  }});
  pool.submit([{id:'throws'},{id:'invalid'},{id:'ok'}]);await tick();
  assert.equal(state(pool,'throws').error.code,'call_execution_failed');
  assert.equal(state(pool,'invalid').error.code,'invalid_run_result');assert.equal(state(pool,'ok').status,'completed');
  assert.ok(!JSON.stringify(pool.snapshot()).includes('private credential'));await pool.close();
});

test('snapshots and input ownership cannot mutate internal scheduling state',async()=>{
  const hold=gate(),input={nested:{value:1}},jobs=[{id:'a',input}];
  const pool=createAsyncCallPool({concurrency:1,maxJobs:2,run:async job=>{await hold.promise;return done(job.input.nested.value);}});
  pool.submit(jobs);input.nested.value=99;const snapshot=pool.snapshot();snapshot.jobs[0].status='completed';
  assert.equal(state(pool,'a').status,'running');hold.resolve();await tick();assert.equal(state(pool,'a').result.value,1);await pool.close();
});

test('a host cancellation from the running notification cannot execute a fresh call',async()=>{
  let pool,calls=0;
  pool=createAsyncCallPool({concurrency:1,maxJobs:1,run:()=>{calls++;return done('late');},
    onState:job=>{if(job.status==='running')pool.cancel([job.id]);}});
  pool.submit([{id:'a'}]);await tick();assert.equal(calls,0);assert.equal(state(pool,'a').status,'cancelled');await pool.close();
});

test('parent listeners and wait timers are released after close, with no queued-age timeout',async()=>{
  const parent=new AbortController(),hold=gate();let added=0,removed=0,clock=1;
  const add=parent.signal.addEventListener.bind(parent.signal),remove=parent.signal.removeEventListener.bind(parent.signal);
  parent.signal.addEventListener=(...args)=>{added++;return add(...args);};
  parent.signal.removeEventListener=(...args)=>{removed++;return remove(...args);};
  const pool=createAsyncCallPool({concurrency:1,maxJobs:2,signal:parent.signal,now:()=>clock,
    run:async job=>{if(job.id==='a')await hold.promise;return done(job.id);}});
  pool.submit([{id:'a'},{id:'b',timeoutMs:100}]);await tick();clock=1_000_000;
  assert.equal(state(pool,'b').status,'queued');assert.equal(state(pool,'b').startedAt,undefined);
  hold.resolve();await tick();assert.equal(state(pool,'b').startedAt,clock);
  const closing=pool.close();assert.equal(pool.close(),closing);await closing;
  assert.equal(added,removed);
});
