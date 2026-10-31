import {createHash} from 'node:crypto';
import {readFile,writeFile,rename} from 'node:fs/promises';
import {join,resolve} from 'node:path';
import {setTimeout as delay} from 'node:timers/promises';

const canonical=value=>Array.isArray(value)?value.map(canonical):value&&typeof value==='object'
 ?Object.fromEntries(Object.keys(value).sort().map(key=>[key,canonical(value[key])])):value;

/** Source references are frozen by the host; models cannot select paths or endpoints. */
export function createResourceReferenceTools(config){
 if(!config.resourceReferencePath||!config.resourceReferences?.length)return [];
 const resources=new Map(config.resourceReferences.map(resource=>[resource.resource_id,resource]));
 return [{name:'agent_resource_open',label:'读取引用资料',
  description:'Open one exact resource from the supplied reference catalog only when needed for the current request. The host checks its frozen version, hash and scope, then returns a protected read-only path. No file bodies are loaded merely because they belong to this conversation. Reuse the returned path; do not reconstruct a prior file from history.',
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
     const source_ref=`resource:${resource.resource_id}:${resource.version}:${resource.sha256}`;
     const historical=Boolean(config.resourceOrigins?.some(item=>item.resource_id===resource.resource_id));
     config.deliveryReviewSources??=[];
     if(!config.deliveryReviewSources.some(item=>item.source_ref===source_ref))config.deliveryReviewSources.push({path:receipt.path,file_name:resource.file_name,size_bytes:resource.size_bytes,sha256:resource.sha256,source_ref,origin:historical?'previous_product':'original_input'});
     return {content:[{type:'text',text:JSON.stringify({...receipt,source_ref,historical_only:historical})}],details:{event:'tool_result',capability:'agent_resource_open',ok:true,result:receipt,evidence_refs:[]}};
    }catch(error){if(error.code!=='ENOENT')throw error;}
    await delay(10,undefined,{signal});
   }
   throw Error('Resource open deadline expired; do not claim source bytes were read');
  }}];
}
