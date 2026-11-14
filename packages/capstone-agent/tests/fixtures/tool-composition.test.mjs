import test from 'node:test';

test('composition reports completed dispatches across success, reuse and local failure',()=>fixture(async cwd=>{
 const declared=structuredClone(catalog);declared.tools.data_gateway_read.annotations={readOnlyHint:true,idempotentHint:true};
 const t=tool(cwd,async()=>native({status:'ok',rows:[1]}),{catalog:declared});
 const call={tools:['read'],program:`await tools.call('read',{id:1});return 'ok';`};
 const first=await t.execute('first',call);
 assert.equal(first.details.completed_leaf_calls,1);
 const reuse=await t.execute('reuse',call);
 assert.equal(reuse.details.completed_leaf_calls,0);
 const failed=await t.execute('failure',{tools:['read'],program:`await tools.call('read',{id:2});throw Error('processing');`});
 assert.equal(failed.isError,true);
 assert.equal(failed.details.kind,'capstone-tool-composition/1');
 assert.equal(failed.details.completed_leaf_calls,1);
}));
import assert from 'node:assert/strict';
import {mkdtemp,rm,readFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {createToolCompositionTool,compositionPolicy} from '../../src/capstone_agent/resources/tool-composition.mjs';
import {rpcEvent} from '../../src/capstone_agent/resources/general-sdk.mjs';
import {boundToolResult} from '../../src/capstone_agent/resources/tool-result-context.mjs';
import {createGatewayUseLedger} from '../../src/capstone_agent/resources/gateway-tool-use.mjs';
import {createHash} from 'node:crypto';

const catalog={revision:'catalog',tools:{data_gateway_read:{name:'read',inputSchema:{type:'object'},description:'Read selected data'}},tool_hashes:{data_gateway_read:'a'.repeat(64)}};

for(const local of ['return {index:tools.inspect(r.ref)};',
 'return {text:JSON.stringify(tools.read(r.ref,"/data"))};',
 'const fields=tools.read(r.ref,"/data");return Object.keys(fields);']){
 test('unawaited observation helpers fail explicitly and retain completed source calls: '+local,()=>fixture(async cwd=>{
  let calls=0;const t=tool(cwd,async()=>{calls++;return native({value:7});});
  const result=await t.execute('forgot-await',{tools:['read'],program:`const r=await tools.call('read',{});${local}`});
  assert.equal(result.isError,true);
  const body=JSON.parse(result.content[0].text);
  assert.match(body.message,/composition_unawaited_helper/);assert.match(body.message,/await/);
  assert.equal(body.completed_calls.length,1);assert.equal(calls,1);
  const restored=await t.execute('recover-await',{tools:[],program:`return await tools.read(${JSON.stringify(body.completed_calls[0].ref)},'/data/value');`});
  assert.equal(restored.isError,false);assert.equal(JSON.parse(restored.content[0].text).result,7);
  assert.equal(calls,1);
 }));
}

test('discarded source handles drain before failure and remain recoverable',()=>fixture(async cwd=>{
 let calls=0;const t=tool(cwd,async()=>{calls++;await new Promise(resolve=>setTimeout(resolve,10));return native({value:7});});
 const result=await t.execute('discarded',{tools:['read'],program:`tools.call('read',{});return 'finished';`});
 assert.equal(result.isError,true);const body=JSON.parse(result.content[0].text);
 assert.match(body.message,/composition_unawaited_helper/);assert.equal(body.completed_calls.length,1);assert.equal(calls,1);
}));

test('unawaited batches drain issued calls without claiming success or retrying',()=>fixture(async cwd=>{
 let calls=0;const t=tool(cwd,async()=>native({value:++calls}));
 const result=await t.execute('batch-discarded',{tools:['read'],program:`tools.batch([{tool:'read',arguments:{i:1}},{tool:'read',arguments:{i:2}}]);return 'finished';`});
 assert.equal(result.isError,true);const body=JSON.parse(result.content[0].text);
 assert.match(body.message,/composition_unawaited_helper/);assert.equal(body.completed_calls.length,2);assert.equal(calls,2);
}));

test('Promise combinators and progress prints keep their supported behavior',()=>fixture(async cwd=>{
 const progress=[];const t=tool(cwd,async()=>native({value:7}),{onProgress:text=>progress.push(text)});
 const result=await t.execute('awaited',{tools:['read'],program:`
 const values=await Promise.all([tools.call('read',{}).then(r=>r.data.value).finally(()=>{}),
  tools.python('import json,sys;print(json.load(sys.stdin))',8)]);
 print('bounded progress');return values;`});
 assert.equal(result.isError,false);assert.deepEqual(JSON.parse(result.content[0].text).result,[7,'8\n']);
 assert.deepEqual(progress,['bounded progress']);
}));

test('private Python helper has identical global/tools entry points and discoverable contracts',()=>fixture(async cwd=>{
 let upstream=0;
 const t=tool(cwd,async()=>{upstream++;return native({});});
 const result=await t.execute('python-alias',{tools:[],program:`
 const answer=await tools.python('import json,sys; print(json.dumps(json.load(sys.stdin)))',{items:[1,2,3]});
 return {same:tools.python===python,answer:JSON.parse(answer),help:tools.help()};`});
 assert.equal(result.isError,false,JSON.stringify(result));
 const value=JSON.parse(result.content[0].text).result;
 assert.equal(value.same,true);assert.deepEqual(value.answer,{items:[1,2,3]});
 assert.match(value.help.python,/JSON stdin/);
 assert.match(value.help.describe,/exact/);
 assert.match(value.help.follow,/issued/);
 assert.equal(upstream,0);
}));

test('application selects eight rolling composition slots',()=>{
 assert.equal(compositionPolicy.concurrency,8);
});

test('reference pipeline fetches once and analyzes remotely without returning source rows',()=>fixture(async cwd=>{
 const declared=structuredClone(catalog);let fetches=0;const analyses=[];
 const rows=[2,4,6]; // Test server-owned data, never returned by its tools.
 const t=tool(cwd,async(_name,args)=>{
  if(args.operation==='fetch'){fetches++;return native({dataset_ref:'dataset:one'});}
  assert.equal(args.dataset_ref,'dataset:one');analyses.push(args.operation);
  return native({result_ref:'result:'+args.operation,summary:args.operation==='sum'?rows.reduce((a,b)=>a+b,0):rows.length});
 },{catalog:declared});
 const response=await t.execute('reference-chain',{tools:['read'],program:`
 const source=await tools.call('read',{operation:'fetch'});
 return tools.map(['sum','count'],async operation=>{
  const result=await tools.call('read',{operation,dataset_ref:source.data.dataset_ref});
  return result.data;
 });`});
 assert.equal(response.isError,false,JSON.stringify(response));
 const body=JSON.parse(response.content[0].text);
 assert.equal(fetches,1);assert.deepEqual(analyses.sort(),['count','sum']);
 assert.deepEqual(body.result,[{result_ref:'result:sum',summary:12},{result_ref:'result:count',summary:3}]);
 assert.equal(body.completed_calls.length,3);
 assert.equal(response.content[0].text.includes('"rows"'),false);
}));

test('one pipeline plans exact calls, reuses observations, validates mappings and publishes only valid tables',()=>fixture(async cwd=>{
 const declared=structuredClone(catalog);declared.tools.data_gateway_read.annotations={readOnlyHint:true,idempotentHint:true};let count=0;
 const t=tool(cwd,async()=>{count++;return native({rows:[{day:'2025-06-15',reading:4}]});},{catalog:declared});
 const plan=[{tool:'read',arguments:{}}];
 const first=await t.execute('pipeline',{tools:['read'],program:`
 const plan=await tools.plan(${JSON.stringify(plan)},{purpose:'Compare observed rows',output:'comparison table',basis_refs:[]});
 const [r]=await tools.batch(${JSON.stringify(plan)});
 try{await tools.table({name:'comparison',sources:[{ref:r.ref,pointer:'/data/rows'}],columns:[{name:'value',pointer:'/missing',type:'number'}]});}catch(e){return {plan,ref:r.ref,error:JSON.parse(e.message)};}`});
 const initial=JSON.parse(first.content[0].text).result;assert.equal(count,1);assert.equal(initial.plan.requested_calls,1);
 assert.equal(initial.error.code,'dataset_validation_failed');assert.equal(initial.error.published,false);
 const next=await t.execute('repair',{tools:['read'],program:`
 const plan=await tools.plan(${JSON.stringify(plan)},{purpose:'Repair mapping from prior source',output:'comparison table',basis_refs:[${JSON.stringify(initial.ref)}]});
 const [r]=await tools.batch(${JSON.stringify(plan)});
 const saved=await tools.table({name:'comparison',sources:[{ref:r.ref,pointer:'/data/rows'}],columns:[{name:'value',pointer:'/reading',type:'number'}]});return {plan,saved};`});
 const result=JSON.parse(next.content[0].text);assert.equal(next.isError,false,JSON.stringify(next));assert.equal(count,1);
 assert.equal(result.result.plan.existing_observations[0].ref,initial.ref);
 assert.match(await readFile(result.result.saved.path,'utf8'),/value\n4/);
 const bad=await t.execute('foreign-plan',{tools:['read'],program:`return tools.plan(${JSON.stringify(plan)},{purpose:'Read',output:'table',basis_refs:['foreign']});`});
 assert.equal(bad.isError,true);assert.equal(count,1);
}));

test('35 successful reads are reused after local processing failure and outer native reference exposes the manifest',()=>fixture(async cwd=>{
 const declared=structuredClone(catalog);declared.tools.data_gateway_read.annotations={readOnlyHint:true,idempotentHint:true};
 const ledger=createGatewayUseLedger();let count=0;
 const t=tool(cwd,async(_name,args)=>{count++;return native({rows:[{n:args.n}]});},{catalog:declared,useLedger:ledger});
 const plan=`Array.from({length:35},(_,n)=>({tool:'read',arguments:{n}}))`;
 const failed=await t.execute('processing',{tools:['read'],program:`await tools.batch(${plan});throw Error('local table mapping failed');`});
 assert.equal(failed.isError,true);assert.equal(count,35);
 const repaired=await t.execute('repair',{tools:['read'],program:`return (await tools.batch(${plan})).map(r=>r.data.rows[0].n);`});
 const result=JSON.parse(repaired.content[0].text);assert.equal(result.calls,0);assert.equal(result.reused_call_count,35);assert.equal(count,35);
 const outer='native-observation:task:'+createHash('sha256').update('repair').digest('hex');
 const read=await t.execute('inspect',{tools:[],program:`return tools.read(${JSON.stringify(outer)},'/completed_calls',{offset:0,limit:2});`});
 assert.equal(read.isError,false,JSON.stringify(read));assert.equal(JSON.parse(read.content[0].text).result.total_items,35);assert.equal(count,35);
}));

test('failed explicit refresh invalidates the older reusable snapshot and batches retain the refresh reason',()=>fixture(async cwd=>{
 const declared=structuredClone(catalog);declared.tools.data_gateway_read.annotations={readOnlyHint:true,idempotentHint:true};let count=0;
 const t=tool(cwd,async()=>{count++;return count===2?{isError:true,content:[{type:'text',text:JSON.stringify({status:'error'})}]}:native({n:count});},{catalog:declared});
 await t.execute('first',{tools:['read'],program:`return tools.call('read',{});`});
 const refresh=await t.execute('refresh',{tools:['read'],program:`return tools.batch([{tool:'read',arguments:{}}],{refresh_reason:'New source version requested'});`});
 assert.equal(JSON.parse(refresh.content[0].text).completed_calls[0].refresh_reason,'New source version requested');
 const next=await t.execute('next',{tools:['read'],program:`return tools.call('read',{});`});
 assert.equal(count,3);assert.equal(JSON.parse(next.content[0].text).result.data.n,3);
}));

test('successful readonly observations survive processing failures and repeated batches reuse exact references',()=>fixture(async cwd=>{
 let count=0;
 const declared=structuredClone(catalog);declared.tools.data_gateway_read.annotations={readOnlyHint:true,idempotentHint:true};
 const t=tool(cwd,async(_name,args)=>{count++;await new Promise(r=>setTimeout(r,5));return native({rows:[{n:args.n}]});},{catalog:declared});
 const program=`return tools.batch([{tool:'read',arguments:{n:1}},{tool:'read',arguments:{n:1}},{tool:'read',arguments:{n:2}}]);`;
 const first=await t.execute('first',{tools:['read'],program:program.replace('return tools.batch','await tools.batch')+`throw Error('local processing failed');`});
 assert.equal(first.isError,true);assert.equal(count,2);
 const second=await t.execute('second',{tools:['read'],program});
 const body=JSON.parse(second.content[0].text);assert.equal(second.isError,false,JSON.stringify(second));
 assert.equal(count,2);assert.equal(body.calls,0);assert.equal(body.reused_call_count,3);
 assert.equal(body.completed_calls.length,3);assert.equal(body.result[0].ref,body.result[1].ref);
 assert.equal(body.result[0].reused,true);assert.ok(body.result[0].observed_at);
 const refreshed=await t.execute('refresh',{tools:['read'],program:`return tools.call('read',{n:1},{refresh_reason:'Check changed source after user update'});`});
 assert.equal(refreshed.isError,false,JSON.stringify(refreshed));assert.equal(count,3);
 const changed=await t.execute('changed',{tools:['read'],program:`return tools.call('read',{n:3});`});
 assert.equal(changed.isError,false);assert.equal(count,4);
}));

test('reuse does not include unknown semantics or failed reads; returned actions always refresh',()=>fixture(async cwd=>{
 let count=0;const declared=structuredClone(catalog);declared.tools.data_gateway_read.annotations={readOnlyHint:true,idempotentHint:true};
 const t=tool(cwd,async()=>{count++;return count===1?{isError:true,content:[{type:'text',text:JSON.stringify({status:'error'})}]}:native({next:{tool:'read',arguments:{}}});},{catalog:declared});
 const r=await t.execute('follow',{tools:['read'],program:`await tools.call('read',{});const r=await tools.call('read',{});return tools.follow(r.ref,'/data/next');`});
 assert.equal(r.isError,false,JSON.stringify(r));assert.equal(count,3);
 const unknown=tool(cwd,async()=>{count++;return native({});});
 await unknown.execute('unknown',{tools:['read'],program:`await tools.call('read',{});return tools.call('read',{});`});assert.equal(count,5);
 const invalid=await t.execute('invalid',{tools:['read'],program:`return tools.batch([{tool:'read',arguments:{}}],{refresh_reason:''});`});
 assert.equal(invalid.isError,true);assert.equal(count,5);
}));

test('batch checks every frozen argument before execution and preserves reservation on rejection',()=>fixture(async cwd=>{
 let calls=0,checked=[];
 const t=tool(cwd,async()=>{calls++;return native({n:1});},{validateCalls:async plan=>{
  checked.push(plan);if(plan.some(x=>typeof x.arguments.n!=='number'))throw Error('/calls/1/arguments/n: integer required');
 }});
 const result=await t.execute('validate',{tools:['read'],max_calls:2,program:`
 try{await tools.batch([{tool:'read',arguments:{n:1}},{tool:'read',arguments:{n:'2'}}]);}catch(e){print(e.message);}
 return tools.batch([{tool:'read',arguments:{n:1}},{tool:'read',arguments:{n:2}}]);`});
 assert.equal(result.isError,false,JSON.stringify(result));assert.equal(calls,2);assert.equal(checked.length,2);
 assert.equal(checked[0][0].name,'data_gateway_read');assert.equal(checked[0][1].arguments.n,'2');
}));

test('batch fails closed without validation and concurrent preflights cannot oversubscribe capacity',()=>fixture(async cwd=>{
 let calls=0;
 const unavailable=tool(cwd,async()=>{calls++;return native({});},{validateCalls:undefined});
 const rejected=await unavailable.execute('missing-validator',{tools:['read'],program:`return tools.batch([{tool:'read',arguments:{}}]);`});
 assert.equal(rejected.isError,true);assert.equal(calls,0);
 const t=tool(cwd,async()=>{calls++;return native({});},{validateCalls:async()=>new Promise(resolve=>setTimeout(resolve,10))});
 const result=await t.execute('race',{tools:['read'],max_calls:2,program:`const plan=[{tool:'read',arguments:{}},{tool:'read',arguments:{}}];return Promise.allSettled([tools.batch(plan),tools.batch(plan)]);`});
 assert.equal(result.isError,false,JSON.stringify(result));assert.equal(calls,2);
 assert.deepEqual(JSON.parse(result.content[0].text).result.map(r=>r.status).sort(),['fulfilled','rejected']);
}));

test('failed programs retain all completed handles and recover the earliest result without upstream calls',()=>fixture(async cwd=>{
 let calls=0;const t=tool(cwd,async()=>native({n:++calls}));
 const result=await t.execute('many',{tools:['read'],program:`for(let i=0;i<12;i++)await tools.call('read',{});throw Error('save failed');`});
 assert.equal(result.isError,true);const failure=JSON.parse(result.content[0].text);
 assert.equal(failure.completed_calls.length,12);assert.equal(failure.completed_call_count,12);
 const ref=failure.completed_calls[0].ref;
 const reused=await t.execute('recover',{tools:[],program:`return tools.read(${JSON.stringify(ref)},'/data/n');`});
 assert.equal(JSON.parse(reused.content[0].text).result,1);assert.equal(calls,12);
}));

test('inspection exposes bounded structure, and failed nested calls remain visible on program success',()=>fixture(async cwd=>{
 let calls=0;const t=tool(cwd,async()=>{calls++;return {isError:true,content:[{type:'text',text:JSON.stringify({status:'error',data:null,gaps:[{reason:'blocked'}]})}]};});
 const result=await t.execute('inspect',{tools:['read'],program:`const r=await tools.call('read',{});return tools.inspect(r.ref);`});
 const body=JSON.parse(result.content[0].text);
 assert.equal(result.isError,false);assert.equal(body.failed_call_count,1);assert.equal(body.failed_calls.length,1);
 assert.equal(body.result.type,'object');assert.ok(body.result.keys.includes('data'));assert.equal(calls,1);
}));

test('large failure manifests are paged from an issued saved reference without repeating any call',()=>fixture(async cwd=>{
 let calls=0;const t=tool(cwd,async()=>native({n:++calls}),{policy:{...compositionPolicy,output_bytes:1500}});
 const result=await t.execute('large-failure',{tools:['read'],program:`for(let i=0;i<20;i++)await tools.call('read',{});throw Error('later failure');`});
 const body=JSON.parse(result.content[0].text);assert.equal(result.isError,true);assert.ok(body.full_result);
 const page=await t.execute('manifest',{tools:[],program:`return tools.read(${JSON.stringify(body.full_result)},'/completed_calls',{offset:0,limit:2});`});
 const recovered=JSON.parse(page.content[0].text).result;
 assert.equal(recovered.total_items,20);assert.equal(recovered.next_offset,2);assert.equal(recovered.items.length,2);
 assert.equal(calls,20);
}));

test('read diagnostics locate a failed field and successful results remain directly reusable',()=>fixture(async cwd=>{
 let calls=0;const t=tool(cwd,async()=>{calls++;return native({rows:[{n:5}]});});
 const first=await t.execute('first',{tools:['read'],program:`return (await tools.call('read',{})).ref;`});
 const ref=JSON.parse(first.content[0].text).result;
 const failed=await t.execute('wrong',{tools:[],program:`return tools.read(${JSON.stringify(ref)},'/data/missing');`});
 assert.equal(failed.isError,true);assert.match(failed.content[0].text,/available_keys.*rows/);
 assert.match(failed.content[0].text,/\/data/);
 const good=await t.execute('reuse',{tools:[],program:`return (await tools.read(${JSON.stringify(ref)},'/data/rows'))[0].n;`});
 assert.equal(JSON.parse(good.content[0].text).result,5);assert.equal(calls,1);
}));

test('direct saved discovery can be paged without another upstream call',()=>fixture(async cwd=>{
 const rows=Array.from({length:500},(_,i)=>({id:i,text:'x'.repeat(100)}));
 const saved=await boundToolResult({content:[{type:'text',text:JSON.stringify({data:{rows}})}]},
  {cwd,toolName:'dynamic_discovery',callId:'discovery'});
 const ref=JSON.parse(saved.content[0].text).full_result;
 const t=tool(cwd,async()=>assert.fail('must reuse the observation'));
 const result=await t.execute('page',{tools:['read'],program:`return await tools.read(${JSON.stringify(ref)},'/data/rows',{offset:498,limit:10});`});
 assert.equal(result.isError,false,JSON.stringify(result));
 assert.deepEqual(JSON.parse(result.content[0].text).result,{items:rows.slice(498),offset:498,total_items:500,next_offset:null});
 const tooWide=await t.execute('wide',{tools:['read'],program:`return await tools.read(${JSON.stringify(ref)},'/data/rows');`});
 assert.equal(tooWide.isError,true);assert.match(tooWide.content[0].text,/read budget/);
 const recovery=await t.execute('recover-wide',{tools:[],program:`
 try{await tools.read(${JSON.stringify(ref)},'/data/rows');throw Error('expected read budget');}
 catch(error){const detail=JSON.parse(error.message);const action=detail.recovery;
 const page=await tools.read(action.ref,action.pointer,action.page);
 return {code:detail.code,page,maximum:detail.maximum_bytes};}`});
 assert.equal(recovery.isError,false,JSON.stringify(recovery));
 const repaired=JSON.parse(recovery.content[0].text).result;
 assert.equal(repaired.code,'observation_read_budget_exceeded');
 assert.ok(repaired.page.items.length>0&&repaired.page.items.length<rows.length);
 assert.deepEqual(repaired.page.items,rows.slice(0,repaired.page.items.length));
 assert.ok(Buffer.byteLength(JSON.stringify(repaired.page))<=repaired.maximum);
 const invalid=await t.execute('bad',{tools:['read'],program:`return await tools.read(${JSON.stringify(ref)},'/data/rows',{offset:-1,limit:10});`});
 assert.equal(invalid.isError,true);assert.match(invalid.content[0].text,/page/);
}));

test('compaction transport exposes lifecycle without summary or raw errors',()=>{
 assert.deepEqual(rpcEvent({type:'compaction_start',reason:'threshold',messages:['PRIVATE']}),{type:'compaction_start',reason:'threshold'});
 for(const [extra,status] of [[{result:{summary:'PRIVATE'}},'completed'],[{aborted:true},'cancelled'],[{errorMessage:'PRIVATE'},'failed'],[{},'skipped']]){
  assert.deepEqual(rpcEvent({type:'compaction_end',reason:'overflow',willRetry:true,...extra}),{type:'compaction_end',reason:'overflow',status,willRetry:true});
 }
});

test('batch preflight rejects capacity and unselected tools before any call',()=>fixture(async cwd=>{
 let issued=0;const t=tool(cwd,async()=>{issued++;return native({});});
 for(const [max_calls,program] of [
  [1,`return await tools.batch([{tool:'read',arguments:{}},{tool:'read',arguments:{}}]);`],
  [2,`return await tools.batch([{tool:'read',arguments:{}},{tool:'unknown',arguments:{}}]);`]]){
  const result=await t.execute('reject',{tools:['read'],max_calls,program});
  assert.equal(result.isError,true);assert.match(result.content[0].text,/preflight/);
 }
 assert.equal(issued,0);
}));

test('batch capacity includes earlier calls and rejection consumes no reserved capacity',()=>fixture(async cwd=>{
 let issued=0;const t=tool(cwd,async()=>{issued++;return native({});});
 const result=await t.execute('remaining',{tools:['read'],max_calls:2,program:`
 await tools.call('read',{});
 try{await tools.batch([{tool:'read',arguments:{}},{tool:'read',arguments:{}}]);throw Error('should reject');}
 catch(e){if(!e.message.includes('preflight'))throw e;}
 return await tools.batch([{tool:'read',arguments:{}}]);`});
 assert.equal(result.isError,false,JSON.stringify(result));assert.equal(issued,2);
}));

test('batch reserves capacity, preserves argument order and uses normal observation refs',()=>fixture(async cwd=>{
 const issued=[];const t=tool(cwd,async(_n,args)=>{issued.push(args);return native(args);});
 const result=await t.execute('batch',{tools:['read'],max_calls:2,program:`
 const out=await tools.batch([{tool:'read',arguments:{n:1}},{tool:'read',arguments:{n:2}}]);
 return {values:out.map(x=>x.data.n),read:await tools.read(out[1].ref,'/data/n')};`});
 assert.equal(result.isError,false,JSON.stringify(result));
 assert.deepEqual(JSON.parse(result.content[0].text).result,{values:[1,2],read:2});assert.equal(issued.length,2);
}));

test('explicit non-correctable rejection survives programs and retains its source',()=>fixture(async cwd=>{
 let issued=0;
 const t=tool(cwd,async()=>{issued++;return {isError:true,content:[{type:'text',text:JSON.stringify({status:'error',gaps:[{reason:'unavailable',scope:{executed:false,correctable:false}}]})}]};});
 const input={tools:['read'],program:`return await tools.call('read',{ref:'opaque'});`};
 const first=JSON.parse((await t.execute('first',input)).content[0].text);
 const second=JSON.parse((await t.execute('second',input)).content[0].text);
 assert.equal(issued,1);
 assert.equal(second.result.status,'not_executed');
 assert.equal(second.result.previous_call,first.result.ref);
 assert.equal(second.result.ref,null);
 await t.execute('changed',{...input,program:`return await tools.call('read',{ref:'different'});`});
 assert.equal(issued,2);
}));

test('later programs read exact saved fields without another upstream call',()=>fixture(async cwd=>{
 let issued=0;const t=tool(cwd,async()=>{issued++;return native({rows:[{name:'Exact',n:5}]});});
 const first=JSON.parse((await t.execute('first',{tools:['read'],program:`return (await tools.call('read',{})).ref;`})).content[0].text);
 const second=await t.execute('reuse',{tools:[],program:`return await tools.read(${JSON.stringify(first.result)},'/data/rows/0');`});
 assert.equal(second.isError,false,JSON.stringify(second));
 assert.deepEqual(JSON.parse(second.content[0].text).result,{name:'Exact',n:5});assert.equal(issued,1);
 const denied=await t.execute('unknown',{tools:[],program:`return await tools.read('invented','/data');`});
 assert.equal(denied.isError,true);
}));

test('unknown effects and correctable errors do not become permanent rejections',()=>fixture(async cwd=>{
 for(const scope of [{correctable:false},{executed:true,correctable:false},{executed:false,correctable:true}]){
  let issued=0;const t=tool(cwd,async()=>{issued++;return {isError:true,content:[{type:'text',text:JSON.stringify({status:'error',gaps:[{reason:'rejected',scope}]})}]};});
  for(let i=0;i<2;i++)await t.execute(String(i),{tools:['read'],program:`return await tools.call('read',{});`});
  assert.equal(issued,2);
 }
}));

test('follow copies an observed action exactly and rechecks selected task identities',()=>fixture(async cwd=>{
  const actual={tools:{random_submit:{name:'submit',inputSchema:{type:'object'}},random_read:{name:'read_action',inputSchema:{type:'object'}}}};
  const args={opaque_ref:'instance-only',field_names:['EXACT_Column'],cursor:'opaque:cursor',revision:'r2'};
  const issued=[];
  const t=tool(cwd,async(name,input)=>{issued.push([name,input]);return name==='random_submit'
    ?native({next_action:{tool:'read_action',arguments:args}}):native({done:true});},{catalog:actual});
  const result=await t.execute('follow',{tools:['submit','read_action'],program:`
    const r=await tools.call('submit',{});
    r.data.next_action.arguments.field_names[0]='WRONG';
    return await tools.follow(r.ref,'/data/next_action');`});
  assert.equal(result.isError,false);assert.deepEqual(issued,[['random_submit',{}],['random_read',args]]);
  const denied=await t.execute('denied',{tools:['submit'],program:`const r=await tools.call('submit',{});return await tools.follow(r.ref,'/data/next_action');`});
  assert.equal(denied.isError,true);assert.equal(issued.filter(([n])=>n==='random_read').length,1);
}));

test('save failure exposes completed observation references and recovers without reading again',()=>fixture(async cwd=>{
  let calls=0;const t=tool(cwd,async()=>{calls++;return native({rows:[{n:5}]});});
  const failed=await t.execute('bad-save',{tools:['read'],program:`const r=await tools.call('read',{});await saveContext('rows',{datasets:[{name:'rows',value:r.data.rows}]});`});
  assert.equal(failed.isError,true);
  const diagnostic=JSON.parse(failed.content[0].text);
  assert.match(diagnostic.message,/datasets\/0\/call/);
  assert.equal(diagnostic.completed_calls.length,1);
  const ref=diagnostic.completed_calls[0].ref;
  const recovered=await t.execute('recover',{tools:[],program:`return await saveContext('rows',{datasets:[{name:'rows',call:${JSON.stringify(ref)},pointer:'/data/rows'}]});`});
  assert.equal(recovered.isError,false);assert.equal(calls,1);
}));

test('follow rejects unknown references and cannot call an unobserved action',()=>fixture(async cwd=>{
  let calls=0;const t=tool(cwd,async()=>{calls++;return native({});});
  const r=await t.execute('forged-action',{tools:['read'],program:`return await tools.follow('forged','/data/next_action');`});
  assert.equal(r.isError,true);assert.match(r.content[0].text,/Unknown observation reference/);assert.equal(calls,0);
}));

test('follow honors returned wait and rejects actions from failed observations',()=>fixture(async cwd=>{
  const issued=[];
  const t=tool(cwd,async(_name,args)=>{issued.push(Date.now());return args.fail
    ?{isError:true,content:[{type:'text',text:JSON.stringify({structuredContent:{status:'error',data:{next_action:{tool:'read',arguments:{}}}}})}]}
    :native({poll_after_seconds:0.04,next_action:{tool:'read',arguments:{done:true}}});});
  const result=await t.execute('wait',{tools:['read'],program:`const r=await tools.call('read',{});return tools.follow(r.ref,'/data/next_action');`});
  assert.equal(result.isError,false);assert.ok(issued[1]-issued[0]>=35);
  const denied=await t.execute('failed-source',{tools:['read'],program:`const r=await tools.call('read',{fail:true});return tools.follow(r.ref,'/data/next_action');`});
  assert.equal(denied.isError,true);assert.match(denied.content[0].text,/not a successful observation/);
  assert.equal(issued.length,3);
}));

test('selection, program calls and describe share source and registration identities',()=>fixture(async cwd=>{
  const actual={revision:'identity',tools:{transport_alpha:{name:'source_alpha',inputSchema:{type:'object'},description:'Alpha',
    outputSchema:{type:'object',properties:{job_state:{type:'string'}}},
    _meta:{usage:{purpose:'Inspect saved progress',execution:'Status reads do not advance the job'}}},
    transport_beta:{name:'source_beta',inputSchema:{type:'object'},description:'Beta'}}};
  for(const selected of ['source_alpha','transport_alpha']){
    const issued=[];
    const result=await tool(cwd,async name=>{issued.push(name);return native({n:issued.length});},{catalog:actual}).execute('aliases',{
      tools:[selected,'source_alpha'],program:`
        if(tools.describe('source_alpha').name!=='source_alpha')throw Error('Source contract lost');
        if(tools.describe('transport_alpha').name!=='source_alpha')throw Error('Registered contract lost');
        if(tools.describe('source_alpha')._meta.usage.execution!=='Status reads do not advance the job')throw Error('Usage lost');
        if(tools.describe('transport_alpha').outputSchema.properties.job_state.type!=='string')throw Error('Output schema lost');
        await tools.call('source_alpha',{});return await tools.call('transport_alpha',{});`});
    assert.equal(result.isError,false,JSON.stringify(result));
    assert.deepEqual(issued,['transport_alpha','transport_alpha']);
  }
}));

test('source identities cannot bypass selected or task-admitted tool grants',()=>fixture(async cwd=>{
  const actual={tools:{transport_alpha:{name:'source_alpha',inputSchema:{type:'object'}},
    transport_beta:{name:'source_beta',inputSchema:{type:'object'}}}};
  let calls=0;
  const t=tool(cwd,async()=>{calls++;return native({});},{catalog:actual,admittedNames:['transport_alpha']});
  for(const input of [
    {tools:['source_beta'],program:'return 1;'},
    {tools:['source_alpha'],program:"return tools.describe('source_beta');"},
    {tools:['source_alpha'],program:"return await tools.call('source_beta',{});"}]){
    const r=await t.execute('deny',input);assert.equal(r.isError,true,JSON.stringify(r));
  }
  assert.equal(calls,0);
}));

test('ambiguous source selection fails before any composition call',()=>fixture(async cwd=>{
 const actual={tools:{transport_alpha:{name:'same',inputSchema:{type:'object'}},transport_beta:{name:'same',inputSchema:{type:'object'}}}};
 let calls=0;
 const result=await tool(cwd,async()=>{calls++;return native({});},{catalog:actual}).execute('ambiguous',{
  tools:['same'],program:"return await tools.call('same',{});"});
 assert.equal(result.isError,true);assert.match(result.content[0].text,/ambiguous/i);assert.equal(calls,0);
}));

test('switching source and registered names cannot reset repeated-resource failure limits',()=>fixture(async cwd=>{
 let issued=0;
 const t=tool(cwd,async name=>{assert.equal(name,'data_gateway_read');issued++;return {
  content:[{type:'text',text:JSON.stringify({structuredContent:{status:'error',gaps:[{reason:'query_timeout'}]}})}]};});
 const result=await t.execute('same-resource',{tools:['read'],program:`
  const out=[];for(let i=0;i<8;i++)out.push(await tools.call(i%2?'read':'data_gateway_read',{}));return out;`});
 assert.equal(result.isError,false,JSON.stringify(result));
 const body=JSON.parse(result.content[0].text);
 assert.equal(issued,compositionPolicy.consecutive_resource_failures);
 assert.equal(body.skipped_calls,8-issued);
}));

test('composition admits any granted tool without a toolset-specific declaration',()=>fixture(async cwd=>{
 for(const group of ['readonly_sql','renamed_relation']){
  const selected={...catalog,tools:{...catalog.tools,renamed_action:{inputSchema:{type:'object'},_meta:{'data-gateway/toolset':group}}}};
  let calls=0;
  const result=await tool(cwd,async()=>{calls++;return native({});},{catalog:selected}).execute('selected',{
   tools:['renamed_action'],program:"return await tools.call('renamed_action',{});"});
  assert.equal(result.isError,false);assert.equal(calls,1);
  assert.equal(JSON.parse(result.content[0].text).advanced_exploration,undefined);
 }
}));
test('repeated resource timeouts stop queued calls without inventing source observations',()=>fixture(async cwd=>{
  let issued=0;
  const t=tool(cwd,async()=>{issued++;await new Promise(r=>setTimeout(r,5));return {content:[{type:'text',text:JSON.stringify({structuredContent:{status:'error',data:null,gaps:[{reason:'query_timeout'}]}})}]};});
  const result=await t.execute('bounded',{tools:['data_gateway_read'],concurrency:2,program:`return await Promise.all(Array.from({length:20},()=>tools.call('data_gateway_read',{})));`});
  assert.equal(result.isError,false);const body=JSON.parse(result.content[0].text);
  assert.ok(issued<=4);assert.ok(body.skipped_calls>=16);
  for(const r of body.result.filter(r=>r.status==='not_executed'))assert.equal(r.ref,null);
}));
const native=value=>({content:[{type:'text',text:JSON.stringify({structuredContent:{status:'ok',data:value,provenance:{source_instance:'test',revision:'one'},gaps:[]}})}],details:{kind:'external_gateway_observation',tool:'data_gateway_read',catalog_revision:'catalog',output_sha256:'b'.repeat(64)}});
test('a query timeout that forbids the same request is not sent upstream again',()=>fixture(async cwd=>{
  let issued=0;
  const gap={reason:'query_timeout',scope:{executed:true,retry_same_request:false,fields:['ID','MEAS_TYPE','DATASOURCE_ID','CREATE_TIME'],suggested_request:{request:{table:'T',filters:[{field:'t.ID',op:'eq',value:'0101110000'}]}}}};
  const result=await tool(cwd,async()=>{issued++;return {content:[{type:'text',text:JSON.stringify({structuredContent:{status:'error',gaps:[gap]}})}]}}).execute('no-same-retry',{tools:['data_gateway_read'],program:`
    const first=await tools.call('data_gateway_read',{limit:5});
    const second=await tools.call('data_gateway_read',{limit:5});
    const changed=await tools.call('data_gateway_read',{limit:1});
    return {first,second,changed};`});
  assert.equal(result.isError,false);
  assert.equal(issued,2);
  const body=JSON.parse(result.content[0].text);
  assert.equal(body.result.second.status,'not_executed');
  assert.equal(body.result.second.gaps[0].scope.retry_same_request,false);
  assert.equal(body.result.second.gaps[0].scope.suggested_request.request.filters[0].field,'t.ID');
  assert.equal(body.result.first.recovery.includes('suggested_request'),true);
}));
test('changed query conditions remain callable after an unchanged condition exhausts its timeout budget',()=>fixture(async cwd=>{
  const issued=[];
  const result=await tool(cwd,async(_name,args)=>{issued.push(args.limit);return args.limit===10?native({n:1}):{content:[{type:'text',text:JSON.stringify({structuredContent:{status:'error',gaps:[{reason:'query_timeout'}]}})}]};
  }).execute('changed',{tools:['data_gateway_read'],program:`
    for(let i=0;i<4;i++)await tools.call('data_gateway_read',{limit:1000});
    return await tools.call('data_gateway_read',{limit:10});`});
  assert.equal(result.isError,false);assert.deepEqual(issued,[1000,1000,1000,10]);
  assert.equal(JSON.parse(result.content[0].text).result.ok,true);
}));
test('a resource failure limit leaves independent tools and partial quality results usable',()=>fixture(async cwd=>{
  const two={...catalog,tools:{...catalog.tools,data_gateway_other:catalog.tools.data_gateway_read}};let reads=0,others=0;
  const result=await tool(cwd,async name=>{
    if(name==='data_gateway_read'){reads++;return {content:[{type:'text',text:JSON.stringify({structuredContent:{status:'error',gaps:[{reason:'query_timeout'}]}})}]};}
    others++;return {content:[{type:'text',text:JSON.stringify({structuredContent:{status:'partial',data:{n:others},gaps:[{reason:'missing_day'}]}})}]};
  },{catalog:two}).execute('independent',{tools:['data_gateway_read','data_gateway_other'],concurrency:1,program:`
    const failed=[];for(let i=0;i<8;i++)failed.push(await tools.call('data_gateway_read',{}));
    const good=[];for(let i=0;i<8;i++)good.push(await tools.call('data_gateway_other',{}));return {failed,good};`});
  assert.equal(result.isError,false);assert.equal(reads,3);assert.equal(others,8);
  const body=JSON.parse(result.content[0].text);assert.equal(body.calls,11);assert.equal(body.skipped_calls,5);
  assert.ok(body.result.good.every(r=>r.ok&&r.status==='partial'&&r.ref));
}));
async function fixture(run){const cwd=await mkdtemp(join(tmpdir(),'tool-composition-'));try{await run(cwd);}finally{await rm(cwd,{recursive:true,force:true});}}
function tool(cwd,invoke,extras={}){return createToolCompositionTool({policy:compositionPolicy,cwd,catalog,invoke,validateCalls:async()=>{},scope:{task_id:'task',attempt_id:'attempt'},deadlineAt:Date.now()+10000,...extras});}
function value(result){assert.equal(result.isError,true,JSON.stringify(result));}

test('one real program overlaps independent calls then passes observed data to a dependent call',()=>fixture(async cwd=>{
  let active=0,peak=0,release;const ready=new Promise(resolve=>{release=resolve;});const calls=[];
  const t=tool(cwd,async(name,args,{callId})=>{
    calls.push({name,args,callId});active++;peak=Math.max(peak,active);if(active===2)release();
    if(args.value<3)await ready;active--;return native({value:args.value});
  },{catalog:{...catalog,tools:{data_gateway_read:{...catalog.tools.data_gateway_read,annotations:{readOnlyHint:true}}}}});
  const result=await t.execute('outer',{tools:['data_gateway_read'],program:`
    const [a,b]=await Promise.all([tools.call('data_gateway_read',{value:1}),tools.call('data_gateway_read',{value:2})]);
    const c=await tools.call('data_gateway_read',{value:a.data.value+b.data.value});
    return {sum:c.data.value};
  `},new AbortController().signal);
  assert.equal(result.isError,false,JSON.stringify(result));assert.equal(peak,2);
  assert.deepEqual(calls.map(c=>c.args.value),[1,2,3]);assert.equal(new Set(calls.map(c=>c.callId)).size,3);
  assert.match(result.content[0].text,/"sum":3/);
}));
test('program has no inherited credentials and can combine a call, Python and a source-backed data package',()=>fixture(async cwd=>{
  process.env.CAPSTONE_COMPOSITION_SECRET_TEST='must-not-inherit';
  try{
    const result=await tool(cwd,async()=>native({unit:'MW',rows:[{n:2},{n:3}]})).execute('outer',{tools:['data_gateway_read'],program:`
      if(process.env.CAPSTONE_COMPOSITION_SECRET_TEST)throw new Error('credential inherited');
      const data=await tools.call('data_gateway_read',{});
      const saved=await saveContext('inputs',{bindings:{unit:{call:data.ref,pointer:'/data/unit'},method:{value:'sum'}},datasets:[{name:'load',call:data.ref,pointer:'/data/rows'}]});
      const context=await loadContext(saved.path);
      const text=await python('import sys,json; d=json.load(sys.stdin); print(sum(r["n"] for r in d))',context.datasets.load.data);
      return {total:Number(text.trim()),package:saved.path};
    `},new AbortController().signal);
    assert.equal(result.isError,false,JSON.stringify(result));assert.match(result.content[0].text,/"total":5/);
    const products=JSON.parse(await readFile(join(cwd,'.capstone-products.json'),'utf8'));assert.equal(products.products[0].role,'support');
  }finally{delete process.env.CAPSTONE_COMPOSITION_SECRET_TEST;}
}));
test('selection cannot call an ungranted tool, recursively invoke composition, or exceed its call budget',()=>fixture(async cwd=>{
  let calls=0;const t=tool(cwd,async()=>{calls++;return native({});});
  value(await t.execute('a',{tools:['unknown'],program:'return 1;'},new AbortController().signal));
  value(await t.execute('b',{tools:['data_gateway_read'],program:`await tools.call('agent_tools_execute',{});`},new AbortController().signal));
  value(await t.execute('c',{tools:['data_gateway_read'],max_calls:1,program:`await tools.call('data_gateway_read',{}); await tools.call('data_gateway_read',{});`},new AbortController().signal));
  assert.equal(calls,1);
}));
test('abort interrupts the real program and pending gateway calls',()=>fixture(async cwd=>{
  const abort=new AbortController();let entered;const started=new Promise(resolve=>{entered=resolve;});
  const t=tool(cwd,async(_name,_args,{signal})=>{entered();await new Promise((resolve,reject)=>{signal.addEventListener('abort',()=>reject(signal.reason),{once:true});});});
  const promise=t.execute('abort',{tools:['data_gateway_read'],program:`await tools.call('data_gateway_read',{});`},abort.signal);
  await started;abort.abort(new Error('cancelled'));await assert.rejects(promise,/cancelled|abort/i);
}));
test('timeout terminates an otherwise non-returning program and retains an explicit failure',()=>fixture(async cwd=>{
  const result=await tool(cwd,async()=>native({})).execute('timeout',{tools:['data_gateway_read'],timeout_ms:100,program:'await new Promise(()=>{});'},new AbortController().signal);
  value(result);assert.match(result.content[0].text,/timeout/i);
}));
test('bounded concurrency assigns unique IDs to queued calls and drains them before return',()=>fixture(async cwd=>{
  const ids=[];let active=0,peak=0;
  const result=await tool(cwd,async(_name,args,{callId})=>{
    ids.push(callId);active++;peak=Math.max(peak,active);await new Promise(resolve=>setTimeout(resolve,5));active--;return native(args);
  },{catalog:{...catalog,tools:{data_gateway_read:{...catalog.tools.data_gateway_read,annotations:{readOnlyHint:true}}}}}).execute('queue',{tools:['data_gateway_read'],concurrency:2,program:`return await Promise.all(Array.from({length:9},(_,i)=>tools.call('data_gateway_read',{i})));`},new AbortController().signal);
  assert.equal(result.isError,false);assert.equal(ids.length,9);assert.equal(new Set(ids).size,9);assert.equal(peak,2);assert.equal(active,0);
}));
test('large returns spill before delivery and later programs reuse actual session observations without querying again',()=>fixture(async cwd=>{
  let count=0;const t=tool(cwd,async()=>{count++;return native({unit:'MW',rows:[1,2]});});
  const first=await t.execute('first',{tools:['data_gateway_read'],program:`return (await tools.call('data_gateway_read',{})).ref;`});
  const ref=JSON.parse(first.content[0].text).result;
  const second=await t.execute('second',{tools:[],program:`return await saveContext('reuse',{bindings:{unit:{call:${JSON.stringify(ref)},pointer:'/data/unit'}}});`});
  assert.equal(second.isError,false,JSON.stringify(second));assert.equal(count,1);
  const large=await t.execute('large',{tools:[],program:`return 'x'.repeat(100000);`});
  assert.equal(large.isError,false);const preview=JSON.parse(large.content[0].text);assert.equal(preview.preview_truncated,true);
  assert.equal(JSON.parse(await readFile(preview.full_result.path,'utf8')).result.length,100000);
  assert.ok(JSON.stringify(rpcEvent({type:'tool_execution_end',toolName:'agent_tools_execute',result:large})).length<40000);
}));
test('abort kills a real Python descendant before the next instruction can run',()=>fixture(async cwd=>{
  const abort=new AbortController();let entered;const ready=new Promise(resolve=>{entered=resolve;});
  const t=tool(cwd,async(_name,_args,{signal})=>{entered();await new Promise((resolve,reject)=>signal.addEventListener('abort',()=>reject(signal.reason),{once:true}));});
  const code="import subprocess,sys; p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); open('descendant.pid','w').write(str(p.pid)); print('ready')";
  const run=t.execute('descendant',{tools:['data_gateway_read'],program:`await python(${JSON.stringify(code)},{});await tools.call('data_gateway_read',{});`},abort.signal);
  await ready;const pid=Number(await readFile(join(cwd,'descendant.pid'),'utf8'));abort.abort(Error('cancelled'));
  await assert.rejects(run,/cancelled/);
  let active=true;
  for(let i=0;i<100;i++){
    try{process.kill(pid,0);if(process.platform==='linux'&&(await readFile(`/proc/${pid}/stat`,'utf8')).split(') ')[1].startsWith('Z')){active=false;break;}}
    catch(error){if(error.code==='ESRCH'||error.code==='ENOENT'){active=false;break;}throw error;}
    await new Promise(resolve=>setTimeout(resolve,10));
  }
  assert.equal(active,false,'Python descendant remained active after abort');
}));
