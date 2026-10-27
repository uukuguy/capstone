import {createHash} from 'node:crypto';
import {mkdir,lstat,readFile,realpath,writeFile} from 'node:fs/promises';
import {join} from 'node:path';

// Symbols survive native result wrappers, but never enter JSON, model messages
// or public metadata. Only the host event projection reads this original.
const originalResult=Symbol('capstoneOriginalToolResult');
const digest=value=>createHash('sha256').update(value).digest('hex');
function preview(value,depth,items,chars){
  if(typeof value==='string')return value.length<=chars?value:value.slice(0,chars)+'… [read full result]';
  if(value===null||typeof value!=='object')return value;
  if(depth===0)return Array.isArray(value)?{preview_type:'array',total_items:value.length}:
    {preview_type:'object',keys:Object.keys(value).slice(0,items)};
  if(Array.isArray(value)){
    const selected=value.slice(0,items).map(item=>preview(item,depth-1,items,chars));
    return value.length<=items?selected:{preview_type:'array',total_items:value.length,items:selected,omitted_items:value.length-items};
  }
  const entries=Object.entries(value),selected=entries.slice(0,items);
  return {...Object.fromEntries(selected.map(([key,item])=>[key,preview(item,depth-1,items,chars)])),
    ...(entries.length>items?{preview_omitted_keys:entries.length-items}:{})};
}

export async function boundToolResult(result,{cwd=process.cwd(),toolName,callId,maxChars=6000}={}){
  if(!Number.isSafeInteger(maxChars)||maxChars<1500)throw new Error('Invalid tool result context budget');
  if(JSON.stringify(result.content??[]).length<=maxChars)return result;
  const body=(result.content??[]).filter(part=>part.type==='text').map(part=>part.text).join('\n');
  // Non-text observations have their own native image handling.
  if(!body||result.content.some(part=>part.type!=='text'))return result;
  let value,extension;
  try{value=JSON.parse(body);extension='json';}catch{value=body;extension='txt';}
  const root=await realpath(cwd),directory=join(root,'.observations');
  try{await mkdir(directory,{mode:0o700});}catch(error){if(error.code!=='EEXIST')throw error;}
  const info=await lstat(directory);
  if(!info.isDirectory()||info.isSymbolicLink())throw new Error('Tool observation directory is invalid');
  const path=join(directory,digest(String(toolName)+'\0'+String(callId)+'\0'+body)+'.'+extension);
  try{await writeFile(path,body,{flag:'wx',mode:0o600});}
  catch(error){
    if(error.code!=='EEXIST')throw error;
    const existing=await lstat(path);
    if(!existing.isFile()||existing.isSymbolicLink()||await readFile(path,'utf8')!==body)
      throw new Error('Saved tool observation identity changed');
  }
  const structured=value?.structuredContent;
  const source=structured&&typeof structured==='object'&&Object.keys(structured).length?structured:value;
  const envelope={preview_truncated:true,
    full_result:{path,sha256:digest(body),size_bytes:Buffer.byteLength(body),tool:toolName,call_id:callId},
    instruction:'This is an incomplete preview. The exact original result is saved in the task directory. Read bounded sections or analyze the file with code; do not repeat the query to recover omitted rows. For independent analyses and deliverables, organize tasks when needed. This file is a source observation, not Authority evidence.'};
  let content;
  for(const [depth,items,chars] of [[6,12,400],[5,6,240],[4,3,160],[2,2,80],[0,8,80]]){
    content=[{type:'text',text:JSON.stringify({...envelope,preview:preview(source,depth,items,chars)})}];
    if(JSON.stringify(content).length<=maxChars)break;
  }
  if(JSON.stringify(content).length>maxChars)throw new Error('Tool result reference exceeds context budget');
  return {...result,content,[originalResult]:result};
}

export function restoreToolResult(result){
  const original=result?.[originalResult];
  if(!original)return result;
  // Native wrappers append provenance/aliases after the preview. Preserve those
  // additions while restoring exact gateway bytes for the host receipt check.
  return {...original,content:[...original.content,...result.content.slice(1)],details:result.details};
}
