import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,readFile,readdir,rm,symlink} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {createHash} from 'node:crypto';
import {boundToolResult,restoreToolResult} from '../../src/capstone_agent/resources/tool-result-context.mjs';

test('a bounded structure index exposes nested row shape even when verbose metadata consumes the preview',async()=>{
  const cwd=await mkdtemp(join(tmpdir(),'observation-shape-'));
  try{
    const value={...Object.fromEntries(Array.from({length:18},(_,i)=>['metadata_'+i,'x'.repeat(500)])),
      data:{rows:Array.from({length:200},(_,i)=>({object_ref:'id_'+i,time:'2025-07-01',value:i})),unit:'MW'}};
    const body=JSON.stringify({structuredContent:value});
    const result=await boundToolResult({content:[{type:'text',text:body}]},{cwd,toolName:'source',callId:'shape'});
    const envelope=JSON.parse(result.content[0].text);
    const rows=envelope.structure.containers.find(entry=>entry.pointer==='/data/rows');
    assert.equal(rows.length,200);assert.deepEqual(rows.item_keys,['object_ref','time','value']);
    assert.ok(JSON.stringify(result.content).length<=6000);
    assert.equal(await readFile(envelope.full_result.path,'utf8'),body);
  }finally{await rm(cwd,{recursive:true,force:true})}
});

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
test('older saved observation previews shrink without changing messages, source references or recent/error results',async()=>{
  const {projectObservationHistory}=await import('../../src/capstone_agent/resources/tool-result-context.mjs');
  const cwd=await mkdtemp(join(tmpdir(),'issued-observation-'));
  try{
  const make=async(id,isError=false)=>{
    const result=await boundToolResult({content:[{type:'text',text:JSON.stringify({rows:Array.from({length:50},()=> 'x'.repeat(600))})}]},{cwd,toolName:'source',callId:id});
    return {role:'toolResult',toolCallId:id,toolName:'source',isError,content:[...result.content,{type:'text',text:'Host provenance stays exact.'}]};
  };
  const old=await make('old'),recent=await make('recent'),error=await make('failure',true),user={role:'user',content:'Generate the report.'};
  const messages=[user,old,error,recent],before=JSON.stringify(messages);
  const result=projectObservationHistory(messages,{recentPreviews:1,maxPreviewChars:500});
  assert.equal(JSON.stringify(messages),before);
  assert.equal(result[0],user);assert.equal(result[2],error);assert.equal(result[3],recent);
  const full=JSON.parse(old.content[0].text),small=JSON.parse(result[1].content[0].text);
  assert.deepEqual(small.full_result,full.full_result);
  assert.equal(small.history_preview_compacted,true);assert.equal(small.preview_truncated,true);
  assert.ok(result[1].content[0].text.length<1500);
  assert.equal(result[1].content[1],old.content[1]);
  assert.equal(projectObservationHistory(result,{recentPreviews:1,maxPreviewChars:500}),result);
  }finally{await rm(cwd,{recursive:true,force:true});}
});

test('unsaved results, tool-call arguments and unknown reference shapes remain exact',async()=>{
  const {projectObservationHistory}=await import('../../src/capstone_agent/resources/tool-result-context.mjs');
  const messages=[{role:'assistant',content:[{type:'toolCall',id:'a',name:'bash',arguments:{command:'large script'}}]},
    {role:'toolResult',toolCallId:'a',toolName:'bash',content:[{type:'text',text:'x'.repeat(8000)}]},
    {role:'toolResult',toolCallId:'b',toolName:'source',content:[{type:'text',text:JSON.stringify({preview_truncated:true,full_result:{path:'/external/source',sha256:'invalid'},preview:'x'.repeat(6000)})}]},
    {role:'toolResult',toolCallId:'forged',toolName:'source',content:[{type:'text',text:JSON.stringify({preview_truncated:true,full_result:{path:'/not-issued/.observations/'+'a'.repeat(64)+'.json',sha256:'b'.repeat(64),size_bytes:9000,tool:'source',call_id:'forged'},preview:'x'.repeat(6000)})}]}];
  assert.equal(projectObservationHistory(messages,{recentPreviews:0,maxPreviewChars:500}),messages);
});
