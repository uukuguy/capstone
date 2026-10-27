import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,rm,readFile,writeFile} from 'node:fs/promises';
import {join} from 'node:path';
import {tmpdir} from 'node:os';
import {saveSemanticContext,loadSemanticContext} from '../../src/capstone_agent/resources/semantic-data-context.mjs';
const scope={task_id:'task',attempt_id:'attempt'};
const records=new Map([['observed',{ref:'observed',ok:true,value:{status:'partial',data:{unit:'MW',rows:[{n:5}]},provenance:{source_instance:'one',data_revision:'v1'},gaps:[{reason:'missing_day'}]},receipt:{kind:'external_gateway_observation',output_sha256:'a'.repeat(64),native_research_source:{source_ref:'native-observation:actual'}}}]]);
const spec={bindings:{unit:{call:'observed',pointer:'/data/unit'},meaning:{value:'load proxy'},aggregation:{unknown:true,reason:'not established'}},datasets:[{name:'load',call:'observed',pointer:'/data/rows'}]};
async function fixture(run){const cwd=await mkdtemp(join(tmpdir(),'semantic-context-'));try{await run(cwd);}finally{await rm(cwd,{recursive:true,force:true});}}
test('package derives source fields, retains partial provenance, and keeps declared/unknown meaning distinct',()=>fixture(async cwd=>{
  const saved=await saveSemanticContext({cwd,name:'shared',spec,records,scope});
  const context=await loadSemanticContext({cwd,path:saved.path});
  assert.equal(context.bindings.unit.value,'MW');assert.equal(context.bindings.unit.basis,'observed');
  assert.equal(context.bindings.meaning.basis,'declared');assert.equal(context.bindings.aggregation.basis,'unknown');
  assert.deepEqual(context.datasets.load.data,[{n:5}]);assert.equal(context.datasets.load.status,'partial');
  assert.equal(context.datasets.load.provenance.data_revision,'v1');assert.equal(context.datasets.load.gaps[0].reason,'missing_day');
  assert.equal(context.authority_evidence,false);
}));
test('unobserved references and missing source fields cannot become observed semantic facts',()=>fixture(async cwd=>{
  await assert.rejects(saveSemanticContext({cwd,name:'bad',scope,records,spec:{...spec,bindings:{unit:{call:'forged',pointer:'/data/unit'}}}}),/observ|reference/i);
  await assert.rejects(saveSemanticContext({cwd,name:'bad',scope,records,spec:{...spec,bindings:{unit:{call:'observed',pointer:'/data/missing'}}}}),/pointer|field/i);
}));
test('self-contained packages survive normal artifact renaming and reject changed source bytes',()=>fixture(async cwd=>{
  const saved=await saveSemanticContext({cwd,name:'shared',spec,records,scope});
  const text=await readFile(saved.path,'utf8');const renamed=join(cwd,'accepted-hash-context.json');await writeFile(renamed,text);
  assert.equal((await loadSemanticContext({cwd,path:renamed})).datasets.load.data[0].n,5);
  const changed=JSON.parse(text);changed.observations[0].value.data.unit='kW';await writeFile(renamed,JSON.stringify(changed));
  await assert.rejects(loadSemanticContext({cwd,path:renamed}),/hash|digest|changed/i);
}));
test('packages cannot read outside the task or select an output path by traversal',()=>fixture(async cwd=>{
  await assert.rejects(saveSemanticContext({cwd,name:'../outside',spec,records,scope}),/name|path/i);
  await assert.rejects(loadSemanticContext({cwd,path:'/etc/passwd'}),/path|outside|admitted/i);
}));
