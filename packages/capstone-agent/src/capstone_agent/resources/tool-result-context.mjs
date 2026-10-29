import {createHash} from 'node:crypto';
import {mkdir,lstat,readFile,realpath,writeFile} from 'node:fs/promises';
import {join} from 'node:path';

// Symbols survive native result wrappers, but never enter JSON, model messages
// or public metadata. Only the host event projection reads this original.
const originalResult=Symbol('capstoneOriginalToolResult');
const issuedObservationRefs=new Set();
const referenceKey=ref=>JSON.stringify([ref.path,ref.sha256,ref.size_bytes,ref.tool,ref.call_id]);
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

// Structural facts only: no inferred units, semantics or source quality verdicts.
function structureIndex(value){
  const keys=object=>Object.keys(object).filter(key=>key.length<=64).slice(0,8);
  const summary={type:Array.isArray(value)?'array':value===null?'null':typeof value,
    ...(value&&typeof value==='object'&&!Array.isArray(value)?{keys:keys(value)}:{}),containers:[],partial:false};
  const queue=[{value,pointer:'',depth:0}];let visited=0;
  while(queue.length&&visited++<128){
    const item=queue.shift(),object=item.value;
    if(!object||typeof object!=='object')continue;
    const record={pointer:item.pointer,type:Array.isArray(object)?'array':'object',
      ...(Array.isArray(object)?{length:object.length,...(object[0]&&typeof object[0]==='object'&&!Array.isArray(object[0])?{item_keys:keys(object[0])}:{})}:{keys:keys(object)})};
    if(item.pointer||Array.isArray(object)){
      if(JSON.stringify({...summary,containers:[...summary.containers,record]}).length>900){summary.partial=true;continue}
      summary.containers.push(record);
    }
    // Array rows are represented by their actual first-row keys, not expanded.
    if(Array.isArray(object))continue;
    if(item.depth>=4){summary.partial=true;continue}
    const entries=Object.entries(object);if(entries.length>128)summary.partial=true;
    for(const [key,child] of entries.slice(0,128)){
      if(!child||typeof child!=='object')continue;
      const pointer=item.pointer+'/'+key.replaceAll('~','~0').replaceAll('/','~1');
      if(pointer.length<=256)queue.push({value:child,pointer,depth:item.depth+1});else summary.partial=true;
    }
  }
  if(queue.length)summary.partial=true;
  return summary;
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
  const fullResult={path,sha256:digest(body),size_bytes:Buffer.byteLength(body),tool:toolName,call_id:callId};
  issuedObservationRefs.add(referenceKey(fullResult));
  const envelope={preview_truncated:true,
    full_result:fullResult,
    structure:structureIndex(source),
    instruction:'This is an incomplete preview. The exact original result is saved in the task directory. Read bounded sections or analyze the file with code; do not repeat the query to recover omitted rows. For independent analyses and deliverables, organize tasks when needed. This file is a source observation, not Authority evidence.'};
  let content;
  for(const [depth,items,chars] of [[6,12,400],[5,6,240],[4,3,160],[2,2,80],[0,8,80]]){
    content=[{type:'text',text:JSON.stringify({...envelope,preview:preview(source,depth,items,chars)})}];
    if(JSON.stringify(content).length<=maxChars)break;
  }
  if(JSON.stringify(content).length>maxChars){
    const small=JSON.parse(content[0].text);small.structure={type:small.structure.type,partial:true};
    content=[{type:'text',text:JSON.stringify(small)}];
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

/** Project older previews only. Files, audit receipts and tool calls stay exact. */
export function projectObservationHistory(messages,{recentPreviews=6,maxPreviewChars=1200}={}){
  if(!Number.isSafeInteger(recentPreviews)||recentPreviews<0||
    !Number.isSafeInteger(maxPreviewChars)||maxPreviewChars<128)
    throw new Error('Invalid observation history context budget');
  let recent=0,changed=false;
  const projected=[...messages];
  for(let i=messages.length-1;i>=0;i--){
    const message=messages[i],part=message.content?.[0];
    if(message.role!=='toolResult'||message.isError===true||part?.type!=='text')continue;
    let envelope;
    try{envelope=JSON.parse(part.text);}catch{continue;}
    const full=envelope?.full_result;
    if(envelope?.preview_truncated!==true||!full||full.tool!==message.toolName||full.call_id!==message.toolCallId||
      typeof full.path!=='string'||!/(?:^|\/)\.observations\/[a-f0-9]{64}\.(?:json|txt)$/.test(full.path)||
      !/^[a-f0-9]{64}$/.test(full.sha256??'')||!Number.isSafeInteger(full.size_bytes)||full.size_bytes<0||
      !issuedObservationRefs.has(referenceKey(full)))continue;
    if(recent++<recentPreviews||envelope.history_preview_compacted===true)continue;
    const preview=JSON.stringify(envelope.preview);
    if(typeof preview!=='string'||preview.length<=maxPreviewChars)continue;
    const {preview:omitted,...retained}=envelope;
    const small={...retained,history_preview_compacted:true,
      preview_excerpt:preview.slice(0,maxPreviewChars)+'… [older preview shortened; read full_result for exact data]'};
    projected[i]={...message,content:[{...part,text:JSON.stringify(small)},...message.content.slice(1)]};
    changed=true;
  }
  return changed?projected:messages;
}

export function configureObservationHistory(pi,options){
  pi.on('context',event=>{
    const messages=projectObservationHistory(event.messages,options);
    return messages===event.messages?undefined:{messages};
  });
}
