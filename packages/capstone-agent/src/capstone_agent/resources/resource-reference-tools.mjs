import {createHash} from 'node:crypto';
import {readFile,writeFile,rename,open} from 'node:fs/promises';
import {constants} from 'node:fs';
import {join,resolve} from 'node:path';
import {setTimeout as delay} from 'node:timers/promises';

const canonical=value=>Array.isArray(value)?value.map(canonical):value&&typeof value==='object'
 ?Object.fromEntries(Object.keys(value).sort().map(key=>[key,canonical(value[key])])):value;

/** Source references are frozen by the host; models cannot select paths or endpoints. */
export function createResourceReferenceTools(config){
 if(!config.resourceReferencePath||!config.resourceReferences?.length)return [];
 const resources=new Map(config.resourceReferences.map(resource=>[resource.resource_id,resource]));
 const historicalIds=new Set((config.resourceOrigins??[]).map(item=>item.resource_id));
 const rangeResources=new Map([...resources].filter(([id])=>!historicalIds.has(id)));
 return [{name:'agent_resource_open',label:'读取引用资料',
  description:'Read one exact resource from the supplied reference catalog only when needed for the current request. The host checks its frozen version, hash and scope, then returns a bounded leading text preview and a protected read-only path for larger processing. Use the preview directly for short reads. For larger work use the exact returned absolute path; no file bodies are loaded merely because they belong to this conversation. Do not reconstruct a prior file from history.',
  parameters:{type:'object',properties:{resource_id:{type:'string',enum:[...resources.keys()]}},required:['resource_id'],additionalProperties:false},
  async execute(callId,args,signal){
   const resource=resources.get(args?.resource_id);
   if(!resource||Object.keys(args).some(key=>key!=='resource_id'))return {isError:true,content:[{type:'text',text:'Resource reference is not admitted for this task.'}]};
   signal?.throwIfAborted();
   const key=createHash('sha256').update(JSON.stringify([callId,resource.resource_id])).digest('hex')+'.json';
   const request=JSON.stringify({resource_id:resource.resource_id});
   const temporary=join(config.resourceReferencePath,'requests',key+'.tmp');
   try{await writeFile(temporary,request,{flag:'wx'});await rename(temporary,join(config.resourceReferencePath,'requests',key));}
   catch(error){if(error.code!=='EEXIST'||await readFile(join(config.resourceReferencePath,'requests',key),'utf8')!==request)throw error;}
   while(Date.now()<config.deadlineAt){
    signal?.throwIfAborted();
    try{
     const raw=await readFile(join(config.resourceReferencePath,'responses',key),'utf8');
     if(Buffer.byteLength(raw)>8192)throw Error('Resource receipt exceeds bounds');
     const receipt=JSON.parse(raw);
     if(receipt.ok!==true)return {isError:true,content:[{type:'text',text:'The referenced resource could not be opened. Do not claim it was read.'}]};
     const expected=resolve(config.resourceInputRoot,'resources',resource.resource_id,resource.file_name);
     if(receipt.path!==expected||JSON.stringify(canonical(receipt.resource))!==JSON.stringify(canonical(resource)))throw Error('Resource receipt identity changed');
     const file=await open(receipt.path,constants.O_RDONLY|constants.O_NOFOLLOW|constants.O_NONBLOCK);
     try{
      const stat=await file.stat();
      if(!stat.isFile()||stat.size!==resource.size_bytes)throw Error('Resource source identity changed');
      const buffer=Buffer.alloc(Math.min(4096,stat.size));
      const {bytesRead}=await file.read(buffer,0,buffer.length,0);
      const truncated=bytesRead<stat.size;
      let text;
      try{if(!buffer.subarray(0,bytesRead).includes(0))text=new TextDecoder('utf-8',{fatal:true}).decode(buffer.subarray(0,bytesRead),{stream:truncated});}catch{/* Binary sources remain available through the protected path. */}
      receipt.preview={bytes_read:bytesRead,truncated,...(text===undefined?{format:'binary'}:{encoding:'utf-8',text})};
     }finally{await file.close();}
     const source_ref=`resource:${resource.resource_id}:${resource.version}:${resource.sha256}`;
     const historical=Boolean(config.resourceOrigins?.some(item=>item.resource_id===resource.resource_id));
     config.deliveryReviewSources??=[];
     if(!config.deliveryReviewSources.some(item=>item.source_ref===source_ref))config.deliveryReviewSources.push({path:receipt.path,file_name:resource.file_name,size_bytes:resource.size_bytes,sha256:resource.sha256,source_ref,origin:historical?'previous_product':'original_input'});
     config.contextDiagnosticSources?.set(callId,{kind:'file',id:resource.resource_id,
       revision:String(resource.version),digest:resource.sha256,offset:0,length:receipt.preview.bytes_read,
       delivery:receipt.preview.text===undefined?'reference':'preview'});
     return {content:[{type:'text',text:JSON.stringify({...receipt,source_ref,historical_only:historical})}],details:{event:'tool_result',capability:'agent_resource_open',ok:true,result:receipt,evidence_refs:[]}};
    }catch(error){if(error.code!=='ENOENT')throw error;}
    await delay(10,undefined,{signal});
   }
   throw Error('Resource open deadline expired; do not claim source bytes were read');
  }},...(Number.isSafeInteger(config.resourceReadBytes)&&rangeResources.size?[createRangeTool(config,rangeResources)]:[])];
}

function createRangeTool(config,resources){
 return {name:'agent_resource_read',label:'读取资料片段',
 description:'Read an exact byte range from an admitted resource. Returns a protected read-only fragment and source receipt. This covers only the requested bytes; it does not establish full-file coverage. Choose whole-file open when the task needs full processing.',
 parameters:{type:'object',properties:{resource_id:{type:'string',enum:[...resources.keys()]},offset:{type:'integer',minimum:0},length:{type:'integer',minimum:1,maximum:config.resourceReadBytes}},required:['resource_id','offset','length'],additionalProperties:false},
 async execute(callId,args,signal){
  const resource=resources.get(args?.resource_id);
  if(!resource||Object.keys(args).sort().join(',')!=='length,offset,resource_id'||!Number.isSafeInteger(args.offset)||!Number.isSafeInteger(args.length)||args.offset<0||args.length<=0||args.length>config.resourceReadBytes||args.offset+args.length>resource.size_bytes)throw Error('Range is not admitted');
  const request_id=createHash('sha256').update(JSON.stringify(['range',callId])).digest('hex');
  const request={schema:'capstone-resource-range-request/1',request_id,...args};
  const key=request_id+'.json',body=JSON.stringify(request),target=join(config.resourceReferencePath,'range-requests',key);
  signal?.throwIfAborted();
  try{await writeFile(target,body,{flag:'wx'});}catch(error){if(error.code!=='EEXIST'||await readFile(target,'utf8')!==body)throw error;}
  while(Date.now()<config.deadlineAt){
   signal?.throwIfAborted();
   try{
    const raw=await readFile(join(config.resourceReferencePath,'range-responses',key),'utf8');
    if(Buffer.byteLength(raw)>65536)throw Error('Range receipt exceeds bounds');
    const result=JSON.parse(raw),receipt=result.receipt;
    if(result.ok===false){
     if(result.request_id!==request_id||result.error?.schema!=='capstone-resource-range-failure/1'||!['resource_range_unavailable','resource_range_rejected','resource_range_capacity'].includes(result.error.code))throw Error('Range failure identity changed');
     return {isError:true,content:[{type:'text',text:JSON.stringify(result)}],details:{event:'tool_result',capability:'agent_resource_read',ok:false,result,evidence_refs:[]}};
    }
    const expected=resolve(config.resourceInputRoot,'ranges',request_id);
    if(result.ok!==true||result.path!==expected||receipt?.schema!=='capstone-resource-read/1'||receipt.task_id!==config.taskId||receipt.attempt_id!==config.resourceAttemptId||receipt.request_id!==request_id||receipt.offset!==args.offset||receipt.length!==args.length||receipt.thread_id!==resource.thread_id||JSON.stringify(canonical(receipt.resource))!==JSON.stringify(canonical(resource)))throw Error('Range receipt identity changed');
    const file=await open(expected,constants.O_RDONLY|constants.O_NOFOLLOW|constants.O_NONBLOCK);
    try{
     const stat=await file.stat();
     if(!stat.isFile()||stat.size!==args.length||(stat.mode&0o222))throw Error('Range fragment identity changed');
     const bytes=await file.readFile();
     if(bytes.length!==args.length||createHash('sha256').update(bytes).digest('hex')!==receipt.sha256)throw Error('Range digest changed');
    }finally{await file.close();}
    config.contextDiagnosticSources?.set(callId,{kind:'file',id:resource.resource_id,
      revision:String(resource.version),digest:resource.sha256,offset:args.offset,length:args.length,delivery:'reference'});
    return {content:[{type:'text',text:JSON.stringify(result)}],details:{event:'tool_result',capability:'agent_resource_read',ok:true,result,evidence_refs:[]}};
   }catch(error){if(error.code!=='ENOENT')throw error;}
   await delay(10,undefined,{signal});
  }
  throw Error('Range read deadline expired; no returned bytes confirmed');
 }};
}
