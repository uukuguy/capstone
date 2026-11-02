// Source-backed table preparation. Column meanings and units remain caller-owned.
import {mkdir,lstat,realpath,writeFile} from 'node:fs/promises';
import {join,relative} from 'node:path';
import {createHash,randomUUID} from 'node:crypto';
import {observationRecordPointer,observationPointer} from './observed-action.mjs';
import {appendProduct} from './semantic-data-context.mjs';

const hash=value=>createHash('sha256').update(value).digest('hex');
const types=new Set(['string','number','integer','boolean','date','datetime']);
const object=x=>x!==null&&typeof x==='object'&&!Array.isArray(x);
const exact=(x,keys)=>object(x)&&Object.keys(x).every(k=>keys.includes(k));
const pointer=x=>typeof x==='string'&&(x===''||x.startsWith('/'));
function validDate(value){
  if(typeof value!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(value))return false;
  const time=Date.parse(value+'T00:00:00Z');
  return Number.isFinite(time)&&new Date(time).toISOString().slice(0,10)===value;
}
function valid(value,type,nullable){
  if(value===null)return nullable===true;
  if(type==='number')return typeof value==='number'&&Number.isFinite(value);
  if(type==='integer')return Number.isSafeInteger(value);
  if(type==='date')return validDate(value);
  if(type==='datetime')return typeof value==='string'&&validDate(value.slice(0,10))&&
    /^\d{4}-\d{2}-\d{2}T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(value)&&Number.isFinite(Date.parse(value));
  return typeof value===type;
}
const csv=value=>{const text=value===null?'':String(value);return /[",\r\n]/.test(text)?'"'+text.replaceAll('"','""')+'"':text;};

export async function prepareObservationTable({cwd,spec,resolveRecord,maxBytes=16*1024*1024}){
  if(!exact(spec,['name','sources','columns','minimum_rows'])||!/^[a-zA-Z0-9_-]{1,80}$/.test(spec.name??'')||
      !Array.isArray(spec.sources)||!spec.sources.length||!Array.isArray(spec.columns)||!spec.columns.length||
      spec.minimum_rows!==undefined&&(!Number.isSafeInteger(spec.minimum_rows)||spec.minimum_rows<0))
    throw Error('/table: expected {name,sources:[{ref,pointer}],columns:[{name,pointer,type,nullable?}],minimum_rows?}');
  for(const [i,c] of spec.columns.entries())if(!exact(c,['name','pointer','type','nullable'])||typeof c.name!=='string'||
      !c.name.trim()||c.name.length>128||!pointer(c.pointer)||!types.has(c.type)||c.nullable!==undefined&&typeof c.nullable!=='boolean')
    throw Error(`/columns/${i}: exact column name, row-relative pointer and supported type are required`);
  if(new Set(spec.columns.map(c=>c.name)).size!==spec.columns.length)throw Error('/columns: duplicate output column names');
  if(!Number.isSafeInteger(maxBytes)||maxBytes<1)throw Error('Invalid table processing budget');
  const issues=[],sources=[],seen=new Set(),lines=[spec.columns.map(c=>csv(c.name)).join(',')];let totalIssues=0,rows=0,processed=0,bytes=Buffer.byteLength(lines[0])+1;
  const issue=item=>{totalIssues++;if(issues.length<32)issues.push(item);};
  const fail=()=>{throw Error(JSON.stringify({code:'dataset_validation_failed',stage:'prepare_table',published:false,
    issues,total_issues:totalIssues,issues_truncated:totalIssues>issues.length,sources,
    recovery:'Inspect the same source references and correct the mapping or validity rules. No source call is needed. No output table was published.'}));};
  if(bytes>maxBytes){issue({reason:'processing_budget_exceeded',maximum_bytes:maxBytes});fail();}
  for(const [index,source] of spec.sources.entries()){
    if(!exact(source,['ref','pointer'])||typeof source.ref!=='string'||!source.ref||!pointer(source.pointer))throw Error(`/sources/${index}: expected an issued ref and exact array pointer`);
    const key=JSON.stringify([source.ref,source.pointer]);
    if(seen.has(key))throw Error(`/sources/${index}: duplicate source slice; reuse one reference without duplicating rows`);
    seen.add(key);
    const record=await resolveRecord(source.ref);
    sources.push({ref:source.ref,pointer:source.pointer});
    if(!record||record.ok!==true){issue({source:index,ref:source.ref,reason:'successful_source_required'});continue;}
    let selected;
    try{selected=observationRecordPointer(record,source.pointer);}catch(error){issue({source:index,ref:source.ref,reason:'source_field_missing',message:error.message});continue;}
    if(!Array.isArray(selected)){issue({source:index,ref:source.ref,pointer:source.pointer,reason:'array_required',actual_type:selected===null?'null':typeof selected});continue;}
    Object.assign(sources.at(-1),{observed_at:record.observedAt?new Date(record.observedAt).toISOString():null,
      source_sha256:hash(JSON.stringify(record.value)),status:record.value?.status,gaps:record.value?.gaps??[]});
    for(const [row,item] of selected.entries()){
      processed+=Buffer.byteLength(JSON.stringify(item)??'null');
      if(processed>maxBytes){issue({reason:'processing_budget_exceeded',maximum_bytes:maxBytes});fail();}
      const values=[];let rowValid=true;
      for(const [column,c] of spec.columns.entries()){
        let value;
        try{value=observationPointer(item,c.pointer);}catch(error){rowValid=false;issue({source:index,row,column,pointer:c.pointer,reason:'source_field_missing',message:error.message});continue;}
        if(!valid(value,c.type,c.nullable)){rowValid=false;issue({source:index,row,column,pointer:c.pointer,reason:'invalid_value',expected:c.type,
          actual_type:value===null?'null':Array.isArray(value)?'array':typeof value});continue;}
        values.push(value);
      }
      rows++;
      if(rowValid){const line=values.map(csv).join(',');bytes+=Buffer.byteLength(line)+1;
        if(bytes>maxBytes){issue({reason:'processing_budget_exceeded',maximum_bytes:maxBytes});fail();}lines.push(line);}
    }
  }
  if(rows<(spec.minimum_rows??1))issue({reason:'insufficient_rows',actual:rows,minimum:spec.minimum_rows??1});
  if(totalIssues)fail();
  const root=await realpath(cwd),out=join(root,'out');
  try{await mkdir(out);}catch(e){if(e.code!=='EEXIST')throw e;}
  if(!(await lstat(out)).isDirectory()||(await lstat(out)).isSymbolicLink()||await realpath(out)!==out)throw Error('Output directory outside task');
  const directory=join(out,spec.name+'-'+randomUUID());await mkdir(directory);
  const path=join(directory,'data.csv'),body=lines.join('\n')+'\n';
  const manifest={schema:'capstone-observation-table/1',authority_evidence:false,rows,columns:spec.columns,sources,
    path:relative(root,path),sha256:hash(body),size_bytes:Buffer.byteLength(body)};
  const manifestPath=join(directory,'table.json');
  await writeFile(path,body,{flag:'wx'});await writeFile(manifestPath,JSON.stringify(manifest),{flag:'wx'});
  await appendProduct(root,{path:relative(root,path),role:'support'});
  await appendProduct(root,{path:relative(root,manifestPath),role:'support'});
  return {...manifest,path,manifest_path:manifestPath};
}
