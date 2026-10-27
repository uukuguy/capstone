import {readFile,writeFile,mkdir,realpath} from 'node:fs/promises';
import {resolve,join,sep,relative} from 'node:path';
import {createHash} from 'node:crypto';
const canonical=v=>Array.isArray(v)?v.map(canonical):v&&typeof v==='object'?Object.fromEntries(Object.keys(v).sort().map(k=>[k,canonical(v[k])])):v;
const digest=v=>createHash('sha256').update(JSON.stringify(canonical(v))).digest('hex');
function pointer(value,path=''){
  if(path==='')return value;
  if(!path.startsWith('/'))throw Error('Invalid source pointer');
  for(const key of path.slice(1).split('/').map(k=>k.replace(/~1/g,'/').replace(/~0/g,'~'))){
    if(value===null||typeof value!=='object'||!Object.hasOwn(value,key))throw Error('Missing source pointer field');
    value=value[key];
  }return value;
}
export async function saveSemanticContext({cwd,name,spec,records,scope}){
  if(!/^[a-zA-Z0-9_-]{1,80}$/.test(name))throw Error('Invalid context name');
  const selected=new Map();
  const observe=ref=>{const record=records.get(ref);if(!record)throw Error('Unknown observation reference');selected.set(ref,record);return record;};
  const bindings=Object.fromEntries(Object.entries(spec.bindings??{}).map(([key,b])=>{
    if(b.call){const record=observe(b.call);return [key,{basis:'observed',value:pointer(record.value,b.pointer),ref:b.call,pointer:b.pointer??''}];}
    if(b.unknown===true)return [key,{basis:'unknown',reason:b.reason??''}];
    if(Object.hasOwn(b,'value'))return [key,{basis:'declared',value:b.value}];
    throw Error('Invalid semantic binding');
  }));
  const datasets=(spec.datasets??[]).map(d=>{const r=observe(d.call);pointer(r.value,d.pointer);return {name:d.name,ref:d.call,pointer:d.pointer??''};});
  if(new Set(datasets.map(d=>d.name)).size!==datasets.length)throw Error('Duplicate dataset name');
  const document={schema:'capstone-semantic-data/1',authority_evidence:false,scope,bindings,datasets,
    observations:[...selected.values()].map(r=>({...r,sha256:digest(r.value)}))};
  document.sha256=digest(document);
  const text=JSON.stringify(document);
  if(Buffer.byteLength(text)>16*1024*1024)throw Error('Context processing budget exceeded; retain upstream resource references');
  const directory=join(cwd,'out',name);await mkdir(directory,{recursive:true});
  const root=await realpath(cwd),actual=await realpath(directory);
  if(!actual.startsWith(root+sep))throw Error('Output path outside task');
  const path=join(directory,'context.json');await writeFile(path,text);
  const manifestPath=join(cwd,'.capstone-products.json');let manifest={schema:'capstone-workspace-products/1',products:[]};
  try{manifest=JSON.parse(await readFile(manifestPath,'utf8'));}catch(e){if(e.code!=='ENOENT')throw e;}
  manifest.products??=[];
  const productPath=relative(cwd,path);
  manifest.products=manifest.products.filter(p=>p.path!==productPath);
  manifest.products.push({path:productPath,role:'support'});
  await writeFile(manifestPath,JSON.stringify(manifest));return {path,sha256:document.sha256};
}
export async function loadSemanticContext({cwd,path,allowedInputs=[]}){
  const root=await realpath(cwd),actual=await realpath(resolve(cwd,path));
  const admitted=await Promise.all(allowedInputs.map(p=>realpath(p)));
  if(actual!==root&&!actual.startsWith(root+sep)&&!admitted.includes(actual))throw Error('Context path outside admitted task inputs');
  const text=await readFile(actual,'utf8');if(Buffer.byteLength(text)>16*1024*1024)throw Error('Context processing budget exceeded');
  const document=JSON.parse(text),{sha256,...body}=document;
  if(document.schema!=='capstone-semantic-data/1'||digest(body)!==sha256)throw Error('Context digest changed');
  const observations=new Map(document.observations.map(r=>{if(digest(r.value)!==r.sha256)throw Error('Observation hash changed');return [r.ref,r];}));
  return {schema:document.schema,authority_evidence:false,bindings:document.bindings,
    datasets:Object.fromEntries(document.datasets.map(d=>{const r=observations.get(d.ref);if(!r)throw Error('Missing observation reference');return [d.name,{data:pointer(r.value,d.pointer),status:r.value.status,provenance:r.value.provenance,gaps:r.value.gaps,receipt:r.receipt}];}))};
}
