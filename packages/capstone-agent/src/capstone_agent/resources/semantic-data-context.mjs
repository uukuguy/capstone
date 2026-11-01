import {readFile,writeFile,mkdir,realpath,rename,lstat} from 'node:fs/promises';
import {resolve,join,sep,relative} from 'node:path';
import {createHash,randomUUID} from 'node:crypto';
import {observationPointer as pointer,ObservationPointerError as MissingSourceField} from './observed-action.mjs';
const manifestUpdates=new Map();
async function appendProduct(cwd,product){
  const key=await realpath(cwd),previous=manifestUpdates.get(key)??Promise.resolve();
  const update=previous.catch(()=>{}).then(async()=>{
    const manifestPath=join(key,'.capstone-products.json');let manifest={schema:'capstone-workspace-products/1',products:[]};
    try{
      if((await lstat(manifestPath)).isSymbolicLink())throw Error('Invalid product manifest path');
      manifest=JSON.parse(await readFile(manifestPath,'utf8'));
    }catch(e){if(e.code!=='ENOENT')throw e;}
    if(!Array.isArray(manifest.products))throw Error('Invalid product manifest');
    manifest.products.push(product);
    const temporary=join(key,`.capstone-products.${randomUUID()}.tmp`);
    await writeFile(temporary,JSON.stringify(manifest),{flag:'wx'});await rename(temporary,manifestPath);
  });
  manifestUpdates.set(key,update);
  try{await update;}finally{if(manifestUpdates.get(key)===update)manifestUpdates.delete(key);}
}
const canonical=v=>Array.isArray(v)?v.map(canonical):v&&typeof v==='object'?Object.fromEntries(Object.keys(v).sort().map(k=>[k,canonical(v[k])])):v;
const digest=v=>createHash('sha256').update(JSON.stringify(canonical(v))).digest('hex');
export async function saveSemanticContext({cwd,name,spec,records,scope}){
  if(!/^[a-zA-Z0-9_-]{1,80}$/.test(name))throw Error('Invalid context name');
  if(!spec||typeof spec!=='object'||Array.isArray(spec))throw Error('/spec: expected an object');
  if(spec.datasets!==undefined&&!Array.isArray(spec.datasets))throw Error('/datasets: expected an array');
  for(const [i,d] of (spec.datasets??[]).entries()){
    const path=`/datasets/${i}`;
    if(!d||typeof d!=='object'||Array.isArray(d))throw Error(`${path}: expected an object`);
    if(typeof d.name!=='string'||!d.name)throw Error(`${path}/name: required nonempty string`);
    if(typeof d.call!=='string'||!d.call)throw Error(`${path}/call: required observation reference; use the ref returned by tools.call, not inline value`);
    if(!records.has(d.call))throw Error(`${path}/call: Unknown observation reference; reuse a ref from this task`);
    if(d.pointer!==undefined&&(typeof d.pointer!=='string'||(d.pointer!==''&&!d.pointer.startsWith('/'))))
      throw Error(`${path}/pointer: expected a JSON pointer`);
  }
  const selected=new Map(),gaps=[];
  const observe=ref=>{const record=records.get(ref);if(!record)throw Error('Unknown observation reference');selected.set(ref,record);return record;};
  const bindings=Object.fromEntries(Object.entries(spec.bindings??{}).map(([key,b])=>{
    if(b&&typeof b==='object'){
      if(b.call){
        const record=observe(b.call);
        try{return [key,{basis:'observed',value:pointer(record.value,b.pointer),ref:b.call,pointer:b.pointer??''}];}
        catch(error){
          if(!(error instanceof MissingSourceField))throw error;
          const gap={binding:key,reason:'source_field_missing',ref:b.call,pointer:b.pointer};gaps.push(gap);
          return [key,{basis:'unknown',...gap}];
        }
      }
      if(b.unknown===true)return [key,{basis:'unknown',reason:b.reason??''}];
      if(Object.hasOwn(b,'value'))return [key,{basis:'declared',value:b.value}];
    }
    // Shorthand metadata is usable, but never promoted to an observed fact.
    return [key,{basis:'declared',value:b}];
  }));
  const datasets=(spec.datasets??[]).map((d,i)=>{
    const r=observe(d.call);
    try{pointer(r.value,d.pointer);}catch(error){
      throw Error(`/datasets/${i}/pointer: source ${JSON.stringify(d.call.slice(0,256))}; ${error.message}`);
    }
    return {name:d.name,ref:d.call,pointer:d.pointer??''};
  });
  if(new Set(datasets.map(d=>d.name)).size!==datasets.length)throw Error('Duplicate dataset name');
  const document={schema:'capstone-semantic-data/1',authority_evidence:false,scope,bindings,datasets,gaps,
    observations:[...selected.values()].map(r=>({...r,sha256:digest(r.value)}))};
  document.sha256=digest(document);
  const text=JSON.stringify(document);
  if(Buffer.byteLength(text)>16*1024*1024)throw Error('Context processing budget exceeded; retain upstream resource references');
  const directory=join(cwd,'out',`${name}-${randomUUID()}`);await mkdir(directory,{recursive:true});
  const root=await realpath(cwd),actual=await realpath(directory);
  if(!actual.startsWith(root+sep))throw Error('Output path outside task');
  const path=join(directory,'context.json');await writeFile(path,text,{flag:'wx'});
  await appendProduct(cwd,{path:relative(cwd,path),role:'support'});
  return {path,product_path:relative(cwd,path),sha256:document.sha256,gaps};
}
export async function loadSemanticContext({cwd,path,allowedInputs=[]}){
  const root=await realpath(cwd),actual=await realpath(resolve(cwd,path));
  const admitted=await Promise.all(allowedInputs.map(p=>realpath(p)));
  if(actual!==root&&!actual.startsWith(root+sep)&&!admitted.includes(actual))throw Error('Context path outside admitted task inputs');
  const text=await readFile(actual,'utf8');if(Buffer.byteLength(text)>16*1024*1024)throw Error('Context processing budget exceeded');
  const document=JSON.parse(text),{sha256,...body}=document;
  if(document.schema!=='capstone-semantic-data/1'||digest(body)!==sha256)throw Error('Context digest changed');
  const observations=new Map(document.observations.map(r=>{if(digest(r.value)!==r.sha256)throw Error('Observation hash changed');return [r.ref,r];}));
  return {schema:document.schema,authority_evidence:false,bindings:document.bindings,gaps:document.gaps??[],
    datasets:Object.fromEntries(document.datasets.map(d=>{const r=observations.get(d.ref);if(!r)throw Error('Missing observation reference');return [d.name,{data:pointer(r.value,d.pointer),status:r.value.status,provenance:r.value.provenance,gaps:r.value.gaps,receipt:r.receipt}];}))};
}
