import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {setTimeout as delay} from 'node:timers/promises';
import {createToolCompositionTool,compositionPolicy} from '../../src/capstone_agent/resources/tool-composition.mjs';

const schema={name:'read',description:'Read',inputSchema:{type:'object'},annotations:{readOnlyHint:true,idempotentHint:true,destructiveHint:false}};
const catalog={revision:'test',tools:{data_gateway_read:schema}};
const native=n=>({content:[{type:'text',text:JSON.stringify({status:'ok',data:{n}})}]});
const calls=Array.from({length:8},(_,n)=>({id:`item-${n}`,tool:'read',arguments:{n}}));
const body=result=>{assert.equal(result.isError,false,JSON.stringify(result));return JSON.parse(result.content[0].text);};
async function fixture(run){const cwd=await mkdtemp(join(tmpdir(),'structured-batch-'));try{await run(cwd);}finally{await rm(cwd,{recursive:true,force:true});}}
const tool=(cwd,invoke,extra={})=>createToolCompositionTool({cwd,catalog,invoke,validateCalls:async()=>{},deadlineAt:Date.now()+10000,...extra});

test('structured calls overlap within the published capacity and preserve IDs, order and readable refs',()=>fixture(async cwd=>{
 let active=0,peak=0;const finished=[];
 const t=tool(cwd,async(_name,{n})=>{active++;peak=Math.max(peak,active);await delay((8-n)*3);active--;finished.push(n);return native(n);});
 const result=body(await t.execute('direct',{calls}));
 assert.equal(peak,Math.min(calls.length,compositionPolicy.concurrency));assert.notDeepEqual(finished,[0,1,2,3,4,5,6,7]);
 assert.deepEqual(result.result.map(r=>r.id),calls.map(r=>r.id));
 assert.deepEqual(result.result.map(r=>r.data.n),[0,1,2,3,4,5,6,7]);
 assert.ok(result.result.every(r=>r.ok&&r.ref));
 const ref=result.result[1].ref;
 const next=body(await t.execute('dependent',{tools:[],program:`return tools.read(${JSON.stringify(ref)},'/data/n');`}));
 assert.equal(next.result,1);
}));

test('invalid, ambiguous or duplicate structured inputs invoke nothing',()=>fixture(async cwd=>{
 let invoked=0;const t=tool(cwd,async()=>{invoked++;return native(1);},{validateCalls:async list=>{if(list.some(c=>typeof c.arguments.n!=='number'))throw Error('integer required');}});
 for(const input of [{calls:[]},{calls:[calls[0],calls[0]]},{calls:[calls[0]],program:'return 1;',tools:[]},
 {calls:[{...calls[0],arguments:{n:'bad'}}]},{calls:[{...calls[0],tool:'foreign'}]},
 {calls:[{...calls[0],id:''}]},{calls:[{...calls[0],unexpected:true}]}]){
  const result=await t.execute('invalid',input);assert.equal(result.isError,true,JSON.stringify(input));
 }
 assert.equal(invoked,0);
}));

test('one transport failure preserves the successful items without retry or false unexecuted claims',()=>fixture(async cwd=>{
 const issued=[];const t=tool(cwd,async(_name,{n})=>{issued.push(n);await delay(5);if(n===2)throw Error('transport failed');return native(n);});
 const result=body(await t.execute('partial',{calls:calls.slice(0,4)}));
 assert.deepEqual(issued,[0,1,2,3]);assert.equal(result.result.length,4);
 assert.equal(result.result[2].ok,false);assert.equal(result.result[2].status,'error');
 assert.equal(result.result[2].execution_status,'unknown');assert.equal(result.failed_call_count,1);
 assert.equal(result.result[3].data.n,3);assert.ok(result.result[3].ref);
}));

test('repeated structured reads reuse refs and cannot overwrite caller IDs',()=>fixture(async cwd=>{
 let invoked=0;const t=tool(cwd,async()=>{invoked++;return {content:[{type:'text',text:JSON.stringify({status:'ok',id:'source-id',index:99,data:{n:7}})}]};});
 const first=body(await t.execute('first',{calls:[calls[0]]}));
 const second=body(await t.execute('reuse',{calls:[calls[0]]}));
 assert.equal(invoked,1);assert.equal(second.reused_call_count,1);
 assert.equal(second.result[0].ref,first.result[0].ref);
 assert.equal(first.result[0].id,'item-0');assert.equal(first.result[0].index,0);
 assert.equal(first.completed_calls[0].index,0);
 assert.ok(Date.parse(first.completed_calls[0].queued_at)<=Date.parse(first.completed_calls[0].started_at));
 assert.ok(Date.parse(first.completed_calls[0].started_at)<=Date.parse(first.completed_calls[0].ended_at));
}));

test('dependent next stage uses the returned observation without replaying the first batch',()=>fixture(async cwd=>{
 const invoked=[];const t=tool(cwd,async(_name,{n})=>{invoked.push(n);return native(n);});
 const first=body(await t.execute('known',{calls:calls.slice(0,2)}));
 const sum=first.result.reduce((total,r)=>total+r.data.n,0);
 const second=body(await t.execute('dependent',{calls:[{id:'sum',tool:'read',arguments:{n:sum+10}}]}));
 assert.equal(second.result[0].data.n,11);assert.deepEqual(invoked,[0,1,11]);
}));

test('lower per-program concurrency remains effective and business failures remain explicit',()=>fixture(async cwd=>{
 let active=0,peak=0;const t=tool(cwd,async(_name,{n})=>{active++;peak=Math.max(peak,active);await delay(3);active--;
 return n===1?{isError:true,content:[{type:'text',text:JSON.stringify({status:'denied',gaps:[{reason:'unavailable'}]})}]}:native(n);});
 const result=body(await t.execute('lower',{calls:calls.slice(0,4),concurrency:2}));
 assert.equal(peak,2);assert.equal(result.failed_call_count,1);assert.equal(result.result[1].ok,false);
 assert.ok(result.result[1].ref);assert.equal(result.result[3].data.n,3);
}));

test('concurrent programs share the session limit',()=>fixture(async cwd=>{
 let active=0,peak=0;
 const t=tool(cwd,async(_name,{n})=>{active++;peak=Math.max(peak,active);await delay(8);active--;return native(n);});
 const result=await Promise.all([t.execute('first',{calls}),t.execute('second',{calls:calls.map(c=>({...c,arguments:{n:c.arguments.n+20}}))})]);
 result.forEach(body);assert.equal(peak,Math.min(2*calls.length,compositionPolicy.concurrency));
}));

test('unknown or mutating tools execute exclusively between read groups',()=>fixture(async cwd=>{
 let active=0;const observed=[];
 const tools={...catalog.tools,data_gateway_write:{...schema,name:'write',annotations:{readOnlyHint:false}},data_gateway_unknown:{...schema,name:'unknown',annotations:{}}};
 const t=tool(cwd,async(name,{n})=>{active++;observed.push({name,active});await delay(5);active--;return native(n);},{catalog:{...catalog,tools}});
 body(await t.execute('mixed',{calls:[...calls.slice(0,2),{id:'w',tool:'write',arguments:{n:9}},{id:'u',tool:'unknown',arguments:{n:10}},...calls.slice(2,4)]}));
 assert.ok(observed.some(r=>r.name==='data_gateway_read'&&r.active===2));
 assert.ok(observed.filter(r=>r.name!=='data_gateway_read').every(r=>r.active===1));
}));

test('cancellation removes waiting calls and releases shared capacity for the next program',()=>fixture(async cwd=>{
 const controller=new AbortController();let entered;const started=new Promise(r=>{entered=r;});let invoked=0;
 const t=tool(cwd,async(_name,{n},{signal})=>{invoked++;entered();await delay(100,undefined,{signal});return native(n);});
 const pending=t.execute('cancel',{calls},controller.signal);await Promise.race([started,pending.then(r=>assert.fail(JSON.stringify(r)))]);controller.abort(Error('user cancelled'));
 await assert.rejects(pending,/cancelled/);assert.ok(invoked<=compositionPolicy.concurrency);
 const result=body(await t.execute('next',{calls:[calls[0]]}));assert.equal(result.result[0].data.n,0);
}));

test('call identities are host-owned for new and reused observations',()=>fixture(async cwd=>{
 const t=tool(cwd,async()=>({content:[{type:'text',text:JSON.stringify({status:'ok',tool:'untrusted',data:{rows:[{n:3}]}})}]}));
 const first=body(await t.execute('identity',{tools:['read'],program:`return tools.call('read',{});`}));
 const second=body(await t.execute('reuse-identity',{tools:['read'],program:`return tools.call('read',{});`}));
 assert.equal(first.result.tool,'data_gateway_read');assert.equal(second.result.tool,'data_gateway_read');
 assert.equal(second.result.ref,first.result.ref);
}));

test('helper namespace and global context functions share the same exact contract',()=>fixture(async cwd=>{
 const t=tool(cwd,async()=>({content:[{type:'text',text:JSON.stringify({status:'ok',data:{rows:[{n:3}]}})}]}));
 const result=body(await t.execute('helpers',{tools:['read'],program:`
 const r=await tools.call('read',{});
 const saved=await tools.saveContext('sample',{bindings:{},datasets:[{name:'rows',call:r.ref,pointer:'/data/rows'}]});
 const loaded=await tools.loadContext(saved.path);
 return {aliases:tools.saveContext===saveContext&&tools.loadContext===loadContext,rows:loaded.datasets.rows.data,help:tools.help()};`}));
 assert.equal(result.result.aliases,true);assert.deepEqual(result.result.rows,[{n:3}]);
 assert.match(result.result.help.map,/concurrency/);assert.match(result.result.help.read,/full_result/);
}));

test('independent paginated chains overlap while each cursor remains sequential',()=>fixture(async cwd=>{
 let active=0,peak=0;const pages=new Map();
 const t=tool(cwd,async(_name,{chain,cursor})=>{
  assert.equal(cursor,pages.get(chain)??0);pages.set(chain,cursor+1);active++;peak=Math.max(peak,active);
  await delay(4);active--;return {content:[{type:'text',text:JSON.stringify({status:'ok',data:{next:cursor<2?cursor+1:null}})}]};
 });
 const result=body(await t.execute('chains',{tools:['read'],program:`
 return tools.map([0,1,2,3,4,5],async chain=>{
  const refs=[];let cursor=0;
  do {const r=await tools.call('read',{chain,cursor});refs.push(r.ref);cursor=r.data.next;}while(cursor!==null);
  return {chain,refs};
 });`}));
 assert.equal(peak,Math.min(6,compositionPolicy.concurrency));assert.equal(result.calls,18);assert.deepEqual(result.result.map(x=>x.chain),[0,1,2,3,4,5]);
 assert.ok(result.result.every(x=>x.refs.length===3));assert.equal(pages.size,6);
}));

test('map rejects invalid limits and drains active mappers before surfacing failure',()=>fixture(async cwd=>{
 let active=0;const t=tool(cwd,async(_name,{n})=>{active++;await delay(5);active--;return native(n);});
 for(const limit of [0,compositionPolicy.concurrency+1,1.5]){
  const result=await t.execute('bad-map',{tools:['read'],program:`return tools.map([1,2],n=>tools.call('read',{n}),{concurrency:${limit}});`});
  assert.equal(result.isError,true);assert.equal(active,0);
 }
 const result=await t.execute('map-failed',{tools:['read'],program:`
 return tools.map([0,1,2,3,4],async n=>{const r=await tools.call('read',{n});if(n===0)throw Error('mapper failed');return r;},{concurrency:2});`});
 assert.equal(result.isError,true);assert.equal(active,0);
 const failed=JSON.parse(result.content[0].text);assert.match(failed.message,/mapper failed/);assert.ok(failed.completed_calls.length>=1);
}));
