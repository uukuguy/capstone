import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,mkdir,readdir,readFile,writeFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';import {join} from 'node:path';
import {createResourceReferenceTools} from '../../src/capstone_agent/resources/resource-reference-tools.mjs';

test('reference open reads only an exact admitted reference and keeps source identity',async()=>{
 const root=await mkdtemp(join(tmpdir(),'capstone-reference-'));
 try{
  await mkdir(join(root,'requests'));await mkdir(join(root,'responses'));await mkdir(join(root,'inputs'));
  const resource={resource_id:'resource_'+'a'.repeat(32),sha256:'b'.repeat(64),size_bytes:12,file_name:'data.csv',version:1};
  const config={resourceReferencePath:root,resourceInputRoot:join(root,'inputs'),resourceReferences:[resource],deadlineAt:Date.now()+2000,deliveryReviewSources:[]};
  const [tool]=createResourceReferenceTools(config);
  const denied=await tool.execute('foreign',{resource_id:'resource_'+'c'.repeat(32)});
  assert.equal(denied.isError,true);assert.deepEqual(await readdir(join(root,'requests')),[]);
  const pending=tool.execute('selected',{resource_id:resource.resource_id});
  let names=[];while(!names.length){names=(await readdir(join(root,'requests'))).filter(name=>name.endsWith('.json'));await new Promise(r=>setTimeout(r,1));}
  assert.deepEqual(JSON.parse(await readFile(join(root,'requests',names[0]),'utf8')),{resource_id:resource.resource_id});
  const path=join(config.resourceInputRoot,'resources',resource.resource_id,resource.file_name);
  await mkdir(join(config.resourceInputRoot,'resources',resource.resource_id),{recursive:true});
  await writeFile(path,'source bytes');
  await writeFile(join(root,'responses',names[0]),JSON.stringify({ok:true,resource:Object.fromEntries(Object.entries(resource).reverse()),path}));
  const result=await pending;
  assert.equal(result.isError,undefined);assert.equal(result.details.result.path,path);
  assert.equal(result.details.result.preview.text,'source bytes');
  assert.equal(config.deliveryReviewSources[0].sha256,resource.sha256);
 }finally{await rm(root,{recursive:true,force:true});}
});

test('range tool returns exact protected fragment and receipt',async()=>{
 const {createHash}=await import('node:crypto');
 const {chmod}=await import('node:fs/promises');
 const root=await mkdtemp(join(tmpdir(),'capstone-range-'));
 try{
  for(const dir of ['range-requests','range-responses','inputs/ranges'])await mkdir(join(root,dir),{recursive:true});
  const data=Buffer.from('sample'),resource={thread_id:'thr_test',resource_id:'resource_'+'a'.repeat(32),sha256:'b'.repeat(64),size_bytes:100,file_name:'data.csv',version:1};
  const config={taskId:'task',resourceAttemptId:'attempt',resourceReadBytes:1024,resourceReferencePath:root,resourceInputRoot:join(root,'inputs'),resourceReferences:[resource],deadlineAt:Date.now()+2000};
  const tool=createResourceReferenceTools(config).find(item=>item.name==='agent_resource_read');
  const pending=tool.execute('selected',{resource_id:resource.resource_id,offset:10,length:data.length});
  let names=[];while(!names.length){names=await readdir(join(root,'range-requests'));await new Promise(r=>setTimeout(r,1));}
  const request=JSON.parse(await readFile(join(root,'range-requests',names[0]),'utf8'));
  const path=join(root,'inputs/ranges',request.request_id);
  await writeFile(path,data);await chmod(path,0o440);
  const receipt={schema:'capstone-resource-read/1',read_id:'read_test',thread_id:'thr_test',attempt_id:'attempt',task_id:'task',request_id:request.request_id,resource,offset:10,length:data.length,sha256:createHash('sha256').update(data).digest('hex'),preview:{status:'text',text:'sample',bytes_read:6,truncated:false}};
  await writeFile(join(root,'range-responses',names[0]),JSON.stringify({ok:true,path,receipt}));
  const result=await pending;
  assert.deepEqual(result.details.result.receipt,receipt);
  assert.equal((await readdir(root)).includes('requests'),false);
  await assert.rejects(()=>tool.execute('selected',{resource_id:resource.resource_id,offset:11,length:6}));
 }finally{await rm(root,{recursive:true,force:true});}
});
