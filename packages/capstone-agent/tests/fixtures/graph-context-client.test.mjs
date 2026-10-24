import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,mkdir,writeFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {createHash} from 'node:crypto';

const modulePath='../../src/capstone_agent/resources/graph-context-client.mjs';
const canonical=value=>Array.isArray(value)?value.map(canonical):value&&typeof value==='object'?Object.fromEntries(Object.keys(value).sort().map(key=>[key,canonical(value[key])])):value;
test('only known selection rejection is correctable and unknown host codes stay definite and private',async()=>{
  const {createGraphContextClient}=await import(modulePath);
  for(const code of [undefined,'','selection_invalid','action_unavailable','owner_invalid','/private/unknown-host-reason']){
    const root=await mkdtemp(join(tmpdir(),'graph-rejection-code-'));await mkdir(join(root,'responses'));let emissions=0,last;
    const client=createGraphContextClient({graphContextPath:root,researchOwner:{},researchAttemptId:'A',researchTaskId:'T'},{emit:async request=>{
      emissions++;last=request;await writeFile(join(root,'responses',request.request_id+'.json'),JSON.stringify({schema:'capstone-enterprise-graph-context/1',
        request_id:request.request_id,request_sha256:createHash('sha256').update(JSON.stringify(canonical(request))).digest('hex'),ok:false,code,error:'Raw /private/exception'}));
    }});
    try{
      const args={action:{id:'action'},checkpoint:{ref:'cp',revision:1},selection:{products:[]}};
      for(let n=0;n<2;n++)await assert.rejects(client.freeze(args),error=>{
        assert.equal(error.category,'rejected');assert.equal(error.request_id,last.request_id);assert.deepEqual(error.checkpoint,args.checkpoint);
        assert.equal(error.rejection_code,code?.startsWith('/')?'host_rejected':code||'selection_invalid');
        assert.doesNotMatch(JSON.stringify(error),/\/private\//);return true;
      });assert.equal(emissions,1);
    }finally{await rm(root,{recursive:true,force:true});}
  }
});
test('retained host rejection is definite with an exact safe request identity, including legacy receipts',async()=>{
  const {createGraphContextClient}=await import(modulePath),root=await mkdtemp(join(tmpdir(),'graph-rejected-'));
  await mkdir(join(root,'responses'));let emissions=0;
  const client=createGraphContextClient({graphContextPath:root,researchOwner:{},researchAttemptId:'A',researchTaskId:'T'},{emit:async request=>{
    emissions++;await writeFile(join(root,'responses',request.request_id+'.json'),JSON.stringify({schema:'capstone-enterprise-graph-context/1',
      request_id:request.request_id,request_sha256:createHash('sha256').update(JSON.stringify(canonical(request))).digest('hex'),ok:false,
      error:'Legacy host rejection /private/secret-source'}));
  }});
  try{
    const args={action:{id:'action'},checkpoint:{ref:'cp',revision:1},selection:{products:[{path:'report.txt',role:'primary'}]}};
    for(let i=0;i<2;i++)await assert.rejects(client.freeze(args),error=>error.category==='rejected'&&error.code==='graph_context_rejected'&&
      error.operation==='freeze'&&/^ctx-/.test(error.request_id)&&!error.message.includes('/private/'));
    assert.equal(emissions,1);
  }finally{await rm(root,{recursive:true,force:true});}
});
test('reference read client retains the exact action and byte range with an idempotent receipt',async()=>{
  const {createGraphContextClient}=await import(modulePath),root=await mkdtemp(join(tmpdir(),'graph-read-client-'));
  await mkdir(join(root,'responses'));let emissions=0;
  const result={ref:'product:exact',kind:'product',sha256:'a'.repeat(64),bytes:100,offset_bytes:12,read_bytes:4,text:'data',content_status:'text',next_offset_bytes:16};
  const args={action:{id:'execute:producer'},checkpoint:{ref:'checkpoint:exact',revision:7},selection:{ref:'product:exact',offset_bytes:12,length_bytes:4}};
  const client=createGraphContextClient({graphContextPath:root,researchOwner:{thread_id:'T'},researchAttemptId:'A',researchTaskId:'T'},{emit:async request=>{
    emissions++;assert.equal(request.operation,'read');assert.equal(request.action_id,args.action.id);assert.deepEqual(request.selection,args.selection);
    const digest=createHash('sha256').update(JSON.stringify(canonical(request))).digest('hex');
    await writeFile(join(root,'responses',request.request_id+'.json'),JSON.stringify({schema:'capstone-enterprise-graph-context/1',
      request_id:request.request_id,request_sha256:digest,ok:true,result}));
  }});
  try{assert.deepEqual(await client.read(args),result);assert.deepEqual(await client.read(args),result);assert.equal(emissions,1);}
  finally{await rm(root,{recursive:true,force:true});}
});
test('context client waits for exact host receipt and retains an identical request',async()=>{
  const {createGraphContextClient}=await import(modulePath);
  const root=await mkdtemp(join(tmpdir(),'graph-client-'));await mkdir(join(root,'responses'));
  let emissions=0,last;
  const config={graphContextPath:root,researchOwner:{thread_id:'T'},researchAttemptId:'A',researchTaskId:'task'};
  const client=createGraphContextClient(config,{emit:request=>{
    emissions++;last=request;
    const digest=createHash('sha256').update(JSON.stringify(canonical(request))).digest('hex');
    void writeFile(join(root,'responses',request.request_id+'.json'),JSON.stringify({schema:'capstone-enterprise-graph-context/1',
      request_id:request.request_id,request_sha256:digest,ok:true,result:{ready:true,products:[]}}));
  }});
  try{
    const args={action:{id:'action'},checkpoint:{ref:'cp',revision:1},selection:{products:[{path:'résumé.txt',role:'primary'}]}};
    assert.deepEqual(await client.freeze(args),{ready:true,products:[]});
    assert.deepEqual(await client.freeze(args),{ready:true,products:[]});
    assert.equal(emissions,1);assert.equal(last.action_id,'action');assert.equal(last.task_id,'task');
  }finally{await rm(root,{recursive:true,force:true});}
});
test('context client rejects a receipt with different request bytes',async()=>{
  const {createGraphContextClient}=await import(modulePath);
  const root=await mkdtemp(join(tmpdir(),'graph-client-'));await mkdir(join(root,'responses'));
  const client=createGraphContextClient({graphContextPath:root,researchOwner:{},researchAttemptId:'A',researchTaskId:'T'},{emit:request=>{
    void writeFile(join(root,'responses',request.request_id+'.json'),JSON.stringify({schema:'capstone-enterprise-graph-context/1',request_id:request.request_id,request_sha256:'forged',ok:true,result:{}}));
  }});
  try{await assert.rejects(client.resolve({action:{id:'action'},checkpoint:{ref:'cp',revision:1},selection:{result_refs:[],product_refs:[]}}),/identity/);}
  finally{await rm(root,{recursive:true,force:true});}
});
test('context wait aborts and does not reissue the host operation',async()=>{
  const {createGraphContextClient}=await import(modulePath);
  const root=await mkdtemp(join(tmpdir(),'graph-client-'));await mkdir(join(root,'responses'));
  let emits=0;const abort=new AbortController();
  const client=createGraphContextClient({graphContextPath:root,researchOwner:{},researchAttemptId:'A',researchTaskId:'T'},{emit:()=>emits++});
  try{const promise=client.freeze({action:{id:'action'},checkpoint:{ref:'cp',revision:1},selection:{products:[]}},{signal:abort.signal});
    abort.abort();await assert.rejects(promise,{name:'AbortError'});assert.equal(emits,1);}
  finally{await rm(root,{recursive:true,force:true});}
});

test('explicit call keys distinguish failed retries and retain exact replay identity',async()=>{
  const {createGraphContextClient}=await import(modulePath);
  const root=await mkdtemp(join(tmpdir(),'graph-call-retry-'));await mkdir(join(root,'responses'));
  const requests=[];
  const client=createGraphContextClient({graphContextPath:root,researchOwner:{},researchAttemptId:'A',researchTaskId:'T'},{emit:async request=>{
    requests.push(request);
    const digest=createHash('sha256').update(JSON.stringify(canonical(request))).digest('hex');
    await writeFile(join(root,'responses',request.request_id+'.json'),JSON.stringify({schema:'capstone-enterprise-graph-context/1',
      request_id:request.request_id,request_sha256:digest,ok:requests.length>1,result:{ready:true,products:[]}}));
  }});
  const args={action:{id:'action'},checkpoint:{ref:'cp',revision:1},selection:{products:[{path:'report.txt',role:'primary'}]}};
  try{
    await assert.rejects(client.freeze(args,{requestKey:'inspect-failed'}),/Host rejected/);
    await assert.rejects(client.freeze(args,{requestKey:'inspect-failed'}),/Host rejected/);assert.equal(requests.length,1);
    assert.deepEqual(await client.freeze(args,{requestKey:'inspect-retry'}),{ready:true,products:[]});
    assert.notEqual(requests[0].request_id,requests[1].request_id);
    assert.deepEqual(await client.freeze(args,{requestKey:'inspect-retry'}),{ready:true,products:[]});assert.equal(requests.length,2);
    const changed={...args,selection:{products:[{path:'changed.txt',role:'primary'}]}};
    await assert.rejects(client.freeze(changed,{requestKey:'inspect-retry'}),/identity changed/);
    assert.equal(requests.length,2);
  }finally{await rm(root,{recursive:true,force:true});}
});
