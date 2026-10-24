import {test} from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,writeFile,mkdir,symlink,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {inspectResearchProducts} from '../../src/capstone_agent/resources/research-products.mjs';

test('private runtime files cannot satisfy a user delivery',async t=>{
  const root=await mkdtemp(join(tmpdir(),'research-products-private-'));
  t.after(()=>rm(root,{recursive:true,force:true}));
  for(const name of ['context.json','AGENTS.md','CLAUDE.md','.research-workers/report.html','__pycache__/result.pyc','result.pyo']) {
    await mkdir(join(root,...name.split('/').slice(0,-1)),{recursive:true});
    await writeFile(join(root,name),'Private runtime content');
    const result=await inspectResearchProducts(root,[{path:name,role:'primary'}]);
    assert.equal(result.ready,false,name);
    assert.equal(result.products.length,0,name);
  }
});

test('delivery requires actual primary bytes, and revision changes their identity',async t=>{
  const root=await mkdtemp(join(tmpdir(),'research-products-'));
  t.after(()=>rm(root,{recursive:true,force:true}));
  const products=[{path:'report.html',role:'primary'},{path:'metrics.csv',role:'support'}];
  assert.equal((await inspectResearchProducts(root,products)).ready,false);
  await writeFile(join(root,'report.html'),'<html>First result</html>');
  await writeFile(join(root,'metrics.csv'),'value\n42\n');
  const first=await inspectResearchProducts(root,products);
  assert.equal(first.ready,true);
  assert.equal(first.products.length,2);
  await writeFile(join(root,'report.html'),'<html>Corrected result: 43</html>');
  const revised=await inspectResearchProducts(root,products);
  assert.notEqual(first.products[0].sha256,revised.products[0].sha256);
  assert.equal(first.products[1].sha256,revised.products[1].sha256);
});

test('scripts, empty files, escaping paths and symlinks do not satisfy delivery',async t=>{
  const root=await mkdtemp(join(tmpdir(),'research-products-'));
  t.after(()=>rm(root,{recursive:true,force:true}));
  await mkdir(join(root,'workspace'));
  await writeFile(join(root,'outside.html'),'outside');
  const workspace=join(root,'workspace');
  await writeFile(join(workspace,'empty.html'),'');
  await writeFile(join(workspace,'analysis.py'),'print(42)');
  await symlink(join(root,'outside.html'),join(workspace,'linked.html'));
  for(const products of [[],[{path:'analysis.py',role:'reproduction'}],
    [{path:'empty.html',role:'primary'}],[{path:'../outside.html',role:'primary'}],
    [{path:'linked.html',role:'primary'}]]) {
    const result=await inspectResearchProducts(workspace,products);
    assert.equal(result.ready,false);
    assert.ok(result.limitations.length);
  }
  // Code is a valid primary product when that is the requested output.
  assert.equal((await inspectResearchProducts(workspace,[{path:'analysis.py',role:'primary'}])).ready,true);
});
