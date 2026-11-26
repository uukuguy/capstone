import {createHash} from 'node:crypto';
import {mkdir,lstat,open,readFile,realpath,writeFile} from 'node:fs/promises';
import {constants} from 'node:fs';
import {join,dirname} from 'node:path';
import {readObservation,observationPointer,ObservationPointerError} from './observed-action.mjs';

// Symbols survive native result wrappers, but never enter JSON, model messages
// or public metadata. Only the host event projection reads this original.
const originalResult=Symbol('capstoneOriginalToolResult');
const savedResult=Symbol('capstoneSavedToolObservation');
export const savedToolObservation=result=>structuredClone(result?.[savedResult]);
const issuedObservationRefs=new Set();
const referenceKey=ref=>JSON.stringify([ref.path,ref.sha256,ref.size_bytes,ref.tool,ref.call_id,ref.base_pointer]);
const digest=value=>createHash('sha256').update(value).digest('hex');
export async function readSavedObservation(ref,pointer,{cwd}){
  if(!ref||typeof ref!=='object'||!issuedObservationRefs.has(referenceKey(ref)))
    throw Error('Unknown saved observation reference');
  const root=await realpath(cwd),directory=join(root,'.observations');
  if(dirname(ref.path)!==directory||await realpath(directory)!==directory)
    throw Error('Observation does not belong to this workspace');
  const handle=await open(ref.path,constants.O_RDONLY|constants.O_NOFOLLOW|constants.O_NONBLOCK);
  try{
    const info=await handle.stat();
    if(!info.isFile()||info.size!==ref.size_bytes)throw Error('Saved observation identity changed');
    const body=Buffer.alloc(ref.size_bytes);let position=0;
    while(position<body.length){
      const {bytesRead}=await handle.read(body,position,body.length-position,position);
      if(!bytesRead)break;
      position+=bytesRead;
    }
    const extra=await handle.read(Buffer.alloc(1),0,1,position);
    if(position!==ref.size_bytes||extra.bytesRead||digest(body)!==ref.sha256)throw Error('Saved observation identity changed');
    const value=ref.path.endsWith('.json')?JSON.parse(body.toString('utf8')):body.toString('utf8');
    const prefix=ref.base_pointer??'';
    return readObservation(new Map([['saved',{value:observationPointer(value,prefix),envelope_pointer:prefix}]]),'saved',pointer);
  }finally{await handle.close();}
}
export async function resolveTaskObservation(records,ref,{cwd,useLedger}){
  if(records.has(ref))return records.get(ref);
  const saved=useLedger?.resolve(ref);
  if(!saved)return;
  return {ref,ok:saved.ok,observedAt:saved.observedAt,receipt:saved.receipt,
    envelope_pointer:saved.base_pointer??'',
    value:await readSavedObservation(saved.reference,saved.base_pointer??'',{cwd})};
}
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
export function structureIndex(value){
  const keyInfo=object=>{
    const all=Object.keys(object),keys=all.filter(key=>key.length<=64).slice(0,8);
    return {keys,...(keys.length<all.length?{keys_truncated:true}:{})};
  };
  const rank=object=>Array.isArray(object)?object.length?0:2:object&&typeof object==='object'&&Object.keys(object).length?1:2;
  const summary={type:Array.isArray(value)?'array':value===null?'null':typeof value,
    ...(value&&typeof value==='object'&&!Array.isArray(value)?keyInfo(value):{}),containers:[],partial:false};
  if(summary.keys_truncated)summary.partial=true;
  const queue=[{value,pointer:'',depth:0}];let visited=0;
  while(queue.length&&visited++<128){
    queue.sort((a,b)=>rank(a.value)-rank(b.value));
    const item=queue.shift(),object=item.value;
    if(!object||typeof object!=='object')continue;
    const first=Array.isArray(object)&&object[0]&&typeof object[0]==='object'&&!Array.isArray(object[0])?keyInfo(object[0]):undefined;
    const record={pointer:item.pointer,type:Array.isArray(object)?'array':'object',
      ...(Array.isArray(object)?{length:object.length,...(first?{item_keys:first.keys,...(first.keys_truncated?{item_keys_truncated:true}:{})}:{})}:keyInfo(object))};
    if(record.keys_truncated||record.item_keys_truncated)summary.partial=true;
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

export async function boundToolResult(result,{cwd=process.cwd(),toolName,callId,storageCallId=callId,maxChars=6000,retain=false,reader}={}){
  if(!Number.isSafeInteger(maxChars)||maxChars<1500)throw new Error('Invalid tool result context budget');
  const size=content=>reader?Buffer.byteLength(JSON.stringify(content)):JSON.stringify(content).length;
  const needsPreview=size(result.content??[])>maxChars;
  if(!needsPreview&&!retain)return result;
  const body=(result.content??[]).filter(part=>part.type==='text').map(part=>part.text).join('\n');
  // Non-text observations have their own native image handling.
  if(!body||result.content.some(part=>part.type!=='text'))return result;
  let value,extension;
  try{value=JSON.parse(body);extension='json';}catch{value=body;extension='txt';}
  const root=await realpath(cwd),directory=join(root,'.observations');
  try{await mkdir(directory,{mode:0o700});}catch(error){if(error.code!=='EEXIST')throw error;}
  const info=await lstat(directory);
  if(!info.isDirectory()||info.isSymbolicLink())throw new Error('Tool observation directory is invalid');
  const path=join(directory,digest(String(toolName)+'\0'+String(storageCallId)+'\0'+body)+'.'+extension);
  try{await writeFile(path,body,{flag:'wx',mode:0o600});}
  catch(error){
    if(error.code!=='EEXIST')throw error;
    const existing=await lstat(path);
    if(!existing.isFile()||existing.isSymbolicLink()||await readFile(path,'utf8')!==body)
      throw new Error('Saved tool observation identity changed');
  }
  const structured=value?.structuredContent;
  const source=structured&&typeof structured==='object'&&Object.keys(structured).length?structured:value;
  const basePointer=extension==='json'?(source===value?'':'/structuredContent'):null;
  const fullResult={path,sha256:digest(body),size_bytes:Buffer.byteLength(body),tool:toolName,call_id:callId,base_pointer:basePointer};
  issuedObservationRefs.add(referenceKey(fullResult));
  const saved={reference:fullResult,base_pointer:basePointer};
  if(!needsPreview)return {...result,[savedResult]:saved};
  const envelope={preview_truncated:true,
    ...(reader?{original_output_complete:!result.isError&&!result.details?.truncation,
      ...(result.isError?{error_tail:body.slice(-240)}:{})}:{}),
    full_result:fullResult,
    preview_pointer:basePointer,
    structure:{...structureIndex(source),base_pointer:basePointer},
    instruction:reader
      ?'Call '+reader+' with reference equal to full_result and a JSON pointer from this observation. Page arrays or text with offset and limit. Original output may be incomplete if the shell capture was truncated.'
      :'Use tools.inspect(full_result) and tools.read(full_result,pointer): structured data is at root. Legacy structure.base_pointer paths still work. Arrays accept {offset,limit}. Original file bytes keep the transport envelope; prefer these helpers over shell paths. Reuse this observation; not Authority evidence.'};
  let content;
  for(const [depth,items,chars] of [[6,12,400],[5,6,240],[4,3,160],[2,2,80],[0,8,80]]){
    content=[{type:'text',text:JSON.stringify({...envelope,preview:preview(source,depth,items,chars)})}];
    if(size(content)<=maxChars)break;
  }
  if(size(content)>maxChars){
    const small=JSON.parse(content[0].text);small.structure={type:small.structure.type,base_pointer:basePointer,partial:true};
    content=[{type:'text',text:JSON.stringify(small)}];
  }
  if(size(content)>maxChars)throw new Error('Tool result reference exceeds context budget');
  return {...result,content,[originalResult]:result,[savedResult]:saved};
}

export function createObservationReadTool(cwd,historical=[]){
  const reply=(value,isError=false)=>({isError,content:[{type:'text',text:JSON.stringify(value)}]});
  return {
    name:'agent_observation_read',label:'Read saved tool output',
    description:'Read saved output using a full_result reference or read exact pointers from a host-admitted historical call ID. Use an exact JSON pointer without wildcards. For an array of records, select fields by exact key to read a smaller page.',
    parameters:{type:'object',properties:{
      reference:{type:'object',properties:{
        path:{type:'string'},sha256:{type:'string'},size_bytes:{type:'integer'},tool:{type:'string'},call_id:{type:'string'},
        base_pointer:{anyOf:[{type:'string'},{type:'null'}]},
      },required:['path','sha256','size_bytes','tool','call_id','base_pointer'],additionalProperties:false},
      historical_call_id:{type:'string',maxLength:128},
      pointers:{type:'array',minItems:1,maxItems:16,uniqueItems:true,items:{type:'string',maxLength:512}},
      fields:{type:'array',minItems:1,maxItems:16,uniqueItems:true,
        items:{type:'string',minLength:1,maxLength:128}},
      pointer:{type:'string',maxLength:512},offset:{type:'integer',minimum:0},limit:{type:'integer',minimum:1,maximum:2000},
    },additionalProperties:false},
    async execute(_callId,{reference,pointer='',offset,limit,fields,historical_call_id,pointers},signal){
      signal?.throwIfAborted();
      let value;
      try{
        if(historical_call_id!==undefined){
          const item=historical.find(entry=>entry.tool_call_id===historical_call_id);
          if(!item||reference!==undefined)throw new Error('Unknown historical call');
          const bytes=await readFile(item.path);
          if(digest(bytes)!==item.sha256)throw new Error('Historical observation digest changed');
          const envelope=JSON.parse(bytes);
          const source=envelope.structuredContent??envelope;
          value=pointers?.length?Object.fromEntries(pointers.map(key=>[key,observationPointer(source,key)]))
            :observationPointer(source,pointer);
        }else value=await readSavedObservation(reference,pointer,{cwd});
      }
      catch(error){
        signal?.throwIfAborted();
        return reply({code:'observation_unavailable',message:error instanceof ObservationPointerError
          ?error.message:'Use an exact saved observation reference issued in this task.'},true);
      }
      signal?.throwIfAborted();
      const paged=offset!==undefined||limit!==undefined||fields!==undefined;
      if(paged){
        if(!Array.isArray(value)&&typeof value!=='string')
          return reply({code:'observation_not_pageable',message:'Select an array or text field to page.'},true);
        const start=offset??0,end=Math.min(start+(limit??20),value.length);
        let selected=value.slice(start,end);
        if(fields!==undefined){
          if(!Array.isArray(selected)||selected.some(row=>!row||typeof row!=='object'||Array.isArray(row)))
            return reply({code:'observation_fields_unavailable',message:'Select an array of records for a field projection.'},true);
          selected=selected.map(row=>Object.fromEntries(fields.filter(field=>Object.hasOwn(row,field))
            .map(field=>[field,row[field]])));
        }
        const page={complete:end>=value.length,value:selected,total:value.length,
          ...(end<value.length?{next_offset:end}:{})};
        if(Buffer.byteLength(JSON.stringify(page))<=4000)return reply(page);
      }else if(Buffer.byteLength(JSON.stringify(value))<=3800)return reply({complete:true,value});
      return reply({complete:false,structure:structureIndex(value),
        instruction:'Select a narrower JSON pointer or a smaller page. For an oversized array item, select one of its fields.'});
    },
  };
}

export function restoreToolResult(result){
  const original=result?.[originalResult];
  if(!original)return result;
  // Native wrappers append provenance/aliases after the preview. Preserve those
  // additions while restoring exact gateway bytes for the host receipt check.
  return {...original,content:[...original.content,...result.content.slice(1)],details:result.details};
}

export function projectToolResultText(result,text){
  return {...result,content:[{type:'text',text},...result.content.slice(1)],
    [originalResult]:{...result,content:result.content.slice(0,1)}};
}

export function projectNativeRead(result){
  const parts=result.content??[];
  if(!parts.every(part=>part.type==='text')||!parts.some(part=>part.text.includes('\0')||
    /\uFFFD[^\n]{0,8}\uFFFD[^\n]{0,8}\uFFFD[^\n]{0,8}\uFFFD/.test(part.text)))return result;
  return {...result,content:[{type:'text',
    text:'The file is binary. Use its product preview or the producing tool receipt to confirm it. Use a format-specific tool if you need its contents.'}],
    [originalResult]:result};
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
    if(recent++<recentPreviews)continue;
    const suffix='… [older preview shortened; read full_result for exact data]';
    const excerpt=envelope.preview_excerpt;
    const preview=envelope.history_preview_compacted===true
      ?(typeof excerpt==='string'&&excerpt.endsWith(suffix)?excerpt.slice(0,-suffix.length):undefined)
      :JSON.stringify(envelope.preview);
    if(typeof preview!=='string'||preview.length<=maxPreviewChars)continue;
    const {preview:omitted,...retained}=envelope;
    const small={...retained,history_preview_compacted:true,
      preview_excerpt:preview.slice(0,maxPreviewChars)+suffix};
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
