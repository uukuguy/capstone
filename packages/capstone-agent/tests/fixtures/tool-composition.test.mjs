import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,rm,readFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {createToolCompositionTool,compositionPolicy} from '../../src/capstone_agent/resources/tool-composition.mjs';
import {rpcEvent} from '../../src/capstone_agent/resources/general-sdk.mjs';

const catalog={revision:'catalog',tools:{data_gateway_read:{name:'read',inputSchema:{type:'object'},description:'Read selected data'}},tool_hashes:{data_gateway_read:'a'.repeat(64)}};

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
  const actual={revision:'identity',tools:{transport_alpha:{name:'source_alpha',inputSchema:{type:'object'},description:'Alpha'},
    transport_beta:{name:'source_beta',inputSchema:{type:'object'},description:'Beta'}}};
  for(const selected of ['source_alpha','transport_alpha']){
    const issued=[];
    const result=await tool(cwd,async name=>{issued.push(name);return native({n:issued.length});},{catalog:actual}).execute('aliases',{
      tools:[selected,'source_alpha'],program:`
        if(tools.describe('source_alpha').name!=='source_alpha')throw Error('Source contract lost');
        if(tools.describe('transport_alpha').name!=='source_alpha')throw Error('Registered contract lost');
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
