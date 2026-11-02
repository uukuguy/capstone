import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,rm,readFile,readdir,symlink} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {prepareObservationTable} from '../../src/capstone_agent/resources/observation-data.mjs';

const spec={name:'comparison',sources:[{ref:'issued',pointer:'/data/rows'}],columns:[
 {name:'day',pointer:'/day',type:'date'}, {name:'value',pointer:'/reading',type:'number'}],minimum_rows:1};
test('table preparation validates all source rows before publishing a reusable CSV',async()=>{
 const cwd=await mkdtemp(join(tmpdir(),'observation-data-'));
 try{
  const record={ref:'issued',ok:true,value:{status:'ok',data:{rows:[{day:'2025-06-15',reading:3}]}}};
  const result=await prepareObservationTable({cwd,spec,resolveRecord:async ref=>ref==='issued'?record:undefined});
  assert.equal(result.rows,1);assert.equal(result.authority_evidence,false);
  assert.match(await readFile(result.path,'utf8'),/day,value\n2025-06-15,3/);
  record.value.data.rows=[{day:'2025-02-30',reading:null},{day:'NaT',other:5}];
  const before=await readdir(join(cwd,'out'));
  await assert.rejects(prepareObservationTable({cwd,spec,resolveRecord:async()=>record}),e=>{
   const d=JSON.parse(e.message);assert.equal(d.code,'dataset_validation_failed');assert.ok(d.issues.length>=4);assert.equal(d.sources[0].ref,'issued');return true;
  });
  assert.deepEqual(await readdir(join(cwd,'out')),before);
 }finally{await rm(cwd,{recursive:true,force:true});}
});

test('table preparation rejects missing grants, wrong types, duplicate slices and escaped output paths',async()=>{
 const cwd=await mkdtemp(join(tmpdir(),'observation-guard-')),outside=await mkdtemp(join(tmpdir(),'observation-outside-'));
 try{
  const resolveRecord=async()=>({ok:true,value:{status:'ok',data:{rows:[{day:'2025-06-15',reading:'4'}]}}});
  await assert.rejects(prepareObservationTable({cwd,spec,resolveRecord}),/invalid_value/);
  await assert.rejects(prepareObservationTable({cwd,spec,resolveRecord:async()=>undefined}),/successful_source_required/);
  await assert.rejects(prepareObservationTable({cwd,spec:{...spec,sources:[...spec.sources,...spec.sources]},resolveRecord}),/duplicate source slice/);
  const good=async()=>({ok:true,value:{data:{rows:[{day:'2025-06-15',reading:4}]}}});
  await assert.rejects(prepareObservationTable({cwd,spec,resolveRecord:good,maxBytes:1}),/processing_budget_exceeded/);
  await symlink(outside,join(cwd,'out'));
  await assert.rejects(prepareObservationTable({cwd,spec,resolveRecord:good}),/Output directory outside task/);
  assert.deepEqual(await readdir(outside),[]);
 }finally{await rm(cwd,{recursive:true,force:true});await rm(outside,{recursive:true,force:true});}
});
