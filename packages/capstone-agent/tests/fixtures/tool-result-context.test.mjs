import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,readFile,readdir,rm,symlink} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {createHash} from 'node:crypto';
import {boundToolResult,restoreToolResult} from '../../src/capstone_agent/resources/tool-result-context.mjs';

test('large gateway data stays complete on disk and exact at the host while model content is bounded',async()=>{
  const cwd=await mkdtemp(join(tmpdir(),'bounded-observation-'));
  try{
    const data={status:'ok',data:{unit:'MW',points:Array.from({length:5000},(_,i)=>({time:i,value:i+.5}))},gaps:[]};
    const body=JSON.stringify({content:[{type:'text',text:JSON.stringify(data)}],structuredContent:data});
    const raw={content:[{type:'text',text:body}],details:{kind:'external_gateway_observation',output_sha256:'host-issued'}};
    const result=await boundToolResult(raw,{cwd,toolName:'data_gateway_series',callId:'query',maxChars:6000});
    assert.ok(JSON.stringify(result.content).length<6000);
    const projected=JSON.parse(result.content[0].text);
    assert.equal(projected.preview_truncated,true);
    assert.equal(projected.full_result.sha256,createHash('sha256').update(body).digest('hex'));
    assert.equal(await readFile(projected.full_result.path,'utf8'),body);
    assert.equal(projected.preview.data.unit,'MW');
    const observed={...result,content:[...result.content,{type:'text',text:'Host observation reference: source-exact'}],
      details:{...result.details,native_research_source:{source_ref:'source-exact'}}};
    const restored=restoreToolResult(observed);
    assert.equal(restored.content[0].text,body);
    assert.equal(restored.content[1].text,'Host observation reference: source-exact');
    assert.deepEqual(restored.details,observed.details);
    assert.equal(JSON.stringify(result).includes('Host observation reference'),false);
  }finally{await rm(cwd,{recursive:true,force:true});}
});

test('small results are unchanged and task-local paths cannot collide',async()=>{
  const small={content:[{type:'text',text:'{"status":"ok"}'}],details:{}};
  assert.equal(await boundToolResult(small,{toolName:'small',callId:'one'}),small);
  assert.equal(restoreToolResult(small),small);
  const roots=await Promise.all([mkdtemp(join(tmpdir(),'bounded-one-')),mkdtemp(join(tmpdir(),'bounded-two-'))]);
  try{
    const raw={content:[{type:'text',text:JSON.stringify({data:'x'.repeat(12000)})}],details:{}};
    const [a,b]=await Promise.all(roots.map(cwd=>boundToolResult(raw,{cwd,toolName:'same',callId:'same'})));
    assert.notEqual(JSON.parse(a.content[0].text).full_result.path,JSON.parse(b.content[0].text).full_result.path);
    assert.equal(restoreToolResult(a).content[0].text,raw.content[0].text);
  }finally{await Promise.all(roots.map(cwd=>rm(cwd,{recursive:true,force:true})));}
});
test('a native-created observation directory link cannot redirect saved results outside the task',async()=>{
  const roots=await Promise.all([mkdtemp(join(tmpdir(),'observation-owner-')),mkdtemp(join(tmpdir(),'observation-outside-'))]);
  try{
    await symlink(roots[1],join(roots[0],'.observations'));
    await assert.rejects(boundToolResult({content:[{type:'text',text:'x'.repeat(12000)}]},
      {cwd:roots[0],toolName:'query',callId:'call'}),/directory is invalid/);
    assert.deepEqual(await readdir(roots[1]),[]);
  }finally{await Promise.all(roots.map(cwd=>rm(cwd,{recursive:true,force:true})));}
});
