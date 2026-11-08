import test from 'node:test';
import assert from 'node:assert/strict';
import {applicationToolOptions} from '../src/capstone_agent/resources/general-sdk.mjs';
import {applicationToolDispatcher,createToolBatchObserver} from '../src/capstone_agent/resources/tool-call-scheduler.mjs';
import {createToolCompositionTool} from '../src/capstone_agent/resources/tool-composition.mjs';
import {createDomainTools} from '../src/capstone_agent/resources/general-domain-tools.mjs';
import {createDataGatewayTools} from '../src/capstone_agent/resources/general-data-gateway.mjs';
import {mkdtemp,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';

const deferred=()=>{let resolve;const promise=new Promise(r=>resolve=r);return {promise,resolve};};
test('launcher measures one whole batch independently from per-tool durations',()=>{
  const events=[];let now=0;
  const observe=createToolBatchObserver({taskId:'task',emit:event=>events.push(event),clock:()=>now});
  observe({type:'message_end',message:{role:'assistant',content:[{type:'toolCall',id:'a'},{type:'toolCall',id:'b'}]}});
  now=10;observe({type:'tool_execution_start',toolCallId:'a'});
  now=20;observe({type:'tool_execution_start',toolCallId:'b'});
  now=100;observe({type:'tool_execution_end',toolCallId:'b'});
  assert.equal(events.length,0);
  now=120;observe({type:'tool_execution_end',toolCallId:'a'});
  observe({type:'turn_end'});
  assert.equal(events.length,1);assert.equal(events[0].tool_batch.elapsed_ms,110);
  assert.deepEqual(events[0].tool_batch.call_ids,['a','b']);
  assert.equal(events[0].tool_batch.mode,'parallel');
});
test('independent chains overlap while each dependent call waits for its input',async()=>{
  const dispatch=applicationToolDispatcher({},8),ready=deferred(),release=deferred();
  const started=[],finished=[];
  const source=dispatch.wrap({async execute(id){
    started.push(id);if(started.length===2)ready.resolve();
    await release.promise;finished.push(id);return id+'-result';
  }});
  const dependent=dispatch.wrap({async execute(id,{input}){
    assert.ok(finished.includes(id));assert.equal(input,id+'-result');
    return input;
  }});
  const chains=['a','b'].map(async id=>{
    const input=await source.execute(id,{});
    return dependent.execute(id,{input});
  });
  try{
    await Promise.race([ready.promise,new Promise((_,reject)=>setTimeout(()=>reject(Error('independent chains serialized')),1000))]);
    assert.deepEqual(started,['a','b']);assert.deepEqual(finished,[]);
  }finally{release.resolve();}
  assert.deepEqual(await Promise.all(chains),['a-result','b-result']);
});
test('actual parallel invocations share an owner clock and record whole batch time',async()=>{
  const config={taskId:'native-task'},records=[],entered=deferred(),finish=deferred();let active=0;
  const dispatch=applicationToolDispatcher(config,8,{observe:(receipt,name)=>records.push({receipt,name})});
  const tool=dispatch.wrap({name:'independent',async execute(){active++;if(active===2)entered.resolve();await finish.promise;active--;return 'done';}});
  const first=tool.execute('one',{}),second=tool.execute('two',{});
  try{await Promise.race([entered.promise,new Promise((_,reject)=>setTimeout(()=>reject(Error('calls did not overlap')),1000))]);}
  finally{finish.resolve();await Promise.all([first,second]);}
  assert.equal(records.length,2);
  assert.equal(records[0].receipt.schema,'capstone-tool-dispatch/1');
  assert.equal(records[0].receipt.owner_id,records[1].receipt.owner_id);
  assert.ok(records.every(r=>r.receipt.task_id==='native-task'));
  for(const {receipt}of records){
    assert.deepEqual(receipt.events.map(e=>e.phase),['submitted','queued','acquired','invocation_started','invocation_settled','released']);
    assert.ok(receipt.events.every(e=>e.provenance==='native_dispatch'));
    assert.ok(receipt.events.every((e,i,a)=>i===0||e.elapsed_ms>=a[i-1].elapsed_ms));
  }
  const [a,c]=records.map(r=>Object.fromEntries(r.receipt.events.map(e=>[e.phase,e.elapsed_ms])));
  assert.ok(Math.max(a.invocation_started,c.invocation_started)<Math.min(a.invocation_settled,c.invocation_settled));
});
test('mixed application leaves and separate entry wrappers share eight rolling slots',async()=>{
  const config={applicationPolicy:{allowed_tools:['a','b']}};
  const gates=Array.from({length:16},deferred),entered=[],filled=deferred(),refilled=deferred();
  const make=name=>({name,async execute(id){entered.push(Number(id));if(entered.length===8)filled.resolve();if(entered.length===9)refilled.resolve();await gates[Number(id)].promise;return {content:[]};}});
  const direct=applicationToolOptions(config,[make('a')],undefined,null).customTools[0];
  const other=applicationToolOptions(config,[make('b')],undefined,null).customTools[0];
  const calls=Array.from({length:16},(_,i)=>(i%2?direct:other).execute(String(i),{}));
  try{
    await filled.promise;await new Promise(r=>setImmediate(r));assert.equal(entered.length,8);
    gates[entered[0]].resolve();await refilled.promise;assert.equal(entered.length,9);
  }finally{gates.forEach(g=>g.resolve());await Promise.all(calls);}
});

test('composition outer role does not take a leaf slot and wrapping is idempotent',async()=>{
  const dispatch=applicationToolDispatcher({},1);
  const leaf=dispatch.wrap({name:'leaf',async execute(){return 'observed';}});
  assert.equal(dispatch.wrap(leaf),leaf);
  const composition=createToolCompositionTool({catalog:{tools:{}},invoke:()=>{},cwd:process.cwd()});
  assert.equal(composition.executionRole,'orchestrator');
  const outer=dispatch.wrap({...composition,execute:()=>leaf.execute('nested',{})});
  assert.equal(await outer.execute('outer',{}),'observed');
});

test('direct and orchestration nested leaves share budget; cancelled queued leaf never executes',async()=>{
  const dispatch=applicationToolDispatcher({},1),gate=deferred(),entered=deferred();let calls=0;
  const leaf=dispatch.wrap({name:'leaf',async execute(){calls++;entered.resolve();await gate.promise;return 'observed';}});
  const first=leaf.execute('direct',{});await entered.promise;
  const abort=new AbortController();
  const cancelled=leaf.execute('cancelled',{},abort.signal);abort.abort(new Error('cancelled'));
  await assert.rejects(cancelled,/cancelled/);assert.equal(calls,1);
  const outer=dispatch.wrap({executionRole:'orchestrator',execute:()=>leaf.execute('nested',{})});
  const pending=outer.execute('outer',{});await new Promise(r=>setImmediate(r));assert.equal(calls,1);
  gate.resolve();await Promise.all([first,pending]);assert.equal(calls,2);
});

test('running cancellation retains the slot until its promise settles',async()=>{
  const dispatch=applicationToolDispatcher({},1),gate=deferred(),entered=deferred();let calls=0;
  const leaf=dispatch.wrap({async execute(){calls++;entered.resolve();await gate.promise;}});
  const abort=new AbortController(),running=leaf.execute('first',{},abort.signal);await entered.promise;
  abort.abort();const pending=leaf.execute('second',{});await new Promise(r=>setImmediate(r));assert.equal(calls,1);
  gate.resolve();await Promise.all([running,pending]);assert.equal(calls,2);
});

test('remote catalog cannot declare executable orchestration roles',()=>{
  const catalog={tools:{external:{executionRole:'orchestrator',description:'External',inputSchema:{type:'object'}}}};
  const domain=createDomainTools({domainTools:{catalog}});
  const gateway=createDataGatewayTools({dataGateway:{catalog}});
  assert.equal(domain[0].executionRole,undefined);
  assert.equal(gateway[0].executionRole,undefined);
});

test('real composition nested calls and direct leaves use one rolling budget',async()=>{
  const cwd=await mkdtemp(join(tmpdir(),'dispatch-'));
  const dispatch=applicationToolDispatcher({},8),gate=deferred(),filled=deferred();let active=0,peak=0;
  const leaf=dispatch.wrap({async execute(_id,args){
    active++;peak=Math.max(peak,active);if(active===8)filled.resolve();
    try{await gate.promise;return {content:[{type:'text',text:JSON.stringify({value:args.i})}]};}
    finally{active--;}
  }});
  const composition=dispatch.wrap(createToolCompositionTool({cwd,validateCalls:async()=>{},
    catalog:{revision:'test',tool_hashes:{external:'a'.repeat(64)},tools:{external:{name:'external',description:'Read',inputSchema:{type:'object'},annotations:{readOnlyHint:true,idempotentHint:true}}}},
    invoke:(_name,args,{callId,signal})=>leaf.execute(callId,args,signal)}));
  const direct=Array.from({length:7},(_,i)=>leaf.execute('direct-'+i,{i}));
  const nested=composition.execute('composition',{calls:Array.from({length:9},(_,i)=>({id:String(i),tool:'external',arguments:{i:i+7}}))});
  try{
    await filled.promise;await new Promise(r=>setTimeout(r,20));assert.equal(active,8);assert.equal(peak,8);
  }finally{gate.resolve();await Promise.all(direct);}
  try{assert.equal((await nested).isError,false);assert.equal(peak,8);}
  finally{await rm(cwd,{recursive:true,force:true});}
});
