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
  await writeFile(join(root,'responses',names[0]),JSON.stringify({ok:true,resource:Object.fromEntries(Object.entries(resource).reverse()),path}));
  const result=await pending;
  assert.equal(result.isError,undefined);assert.equal(result.details.result.path,path);
  assert.equal(config.deliveryReviewSources[0].sha256,resource.sha256);
 }finally{await rm(root,{recursive:true,force:true});}
});
