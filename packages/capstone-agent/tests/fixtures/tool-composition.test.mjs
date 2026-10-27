import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,rm,readFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {createToolCompositionTool,compositionPolicy} from '../../src/capstone_agent/resources/tool-composition.mjs';

const catalog={revision:'catalog',tools:{data_gateway_read:{name:'read',inputSchema:{type:'object'},description:'Read selected data'}},tool_hashes:{data_gateway_read:'a'.repeat(64)}};
const native=value=>({content:[{type:'text',text:JSON.stringify({structuredContent:{status:'ok',data:value,provenance:{source_instance:'test',revision:'one'},gaps:[]}})}],details:{kind:'external_gateway_observation',tool:'data_gateway_read',catalog_revision:'catalog',output_sha256:'b'.repeat(64)}});
async function fixture(run){const cwd=await mkdtemp(join(tmpdir(),'tool-composition-'));try{await run(cwd);}finally{await rm(cwd,{recursive:true,force:true});}}
function tool(cwd,invoke,extras={}){return createToolCompositionTool({policy:compositionPolicy,cwd,catalog,invoke,scope:{task_id:'task',attempt_id:'attempt'},deadlineAt:Date.now()+10000,...extras});}
function value(result){assert.equal(result.isError,true,JSON.stringify(result));}

test('one real program overlaps independent calls then passes observed data to a dependent call',()=>fixture(async cwd=>{
  let active=0,peak=0,release;const ready=new Promise(resolve=>{release=resolve;});const calls=[];
  const t=tool(cwd,async(name,args,{callId})=>{
    calls.push({name,args,callId});active++;peak=Math.max(peak,active);if(active===2)release();
    if(args.value<3)await ready;active--;return native({value:args.value});
  });
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
  }).execute('queue',{tools:['data_gateway_read'],concurrency:2,program:`return await Promise.all(Array.from({length:9},(_,i)=>tools.call('data_gateway_read',{i})));`},new AbortController().signal);
  assert.equal(result.isError,false);assert.equal(ids.length,9);assert.equal(new Set(ids).size,9);assert.equal(peak,2);assert.equal(active,0);
}));
