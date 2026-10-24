import {assertCapacity,exceedsCapacity} from './applicationCapacity'
/** Bounded browser transfer. A stored resource is not yet processed task context. */
export type ResourceUpload = {schema:'capstone-resource-upload/1';upload_id:string;file_name:string;size_bytes:number;chunk_bytes:number;state:string;received_parts:number[];part_sha256:Record<string,string>}
type Request = (path:string,init?:RequestInit)=>Promise<unknown>
export type ResourceTransferOptions = {signal?:AbortSignal;uploadId?:string;requestId:string;draft?:boolean;onSession?:(id:string)=>void;onProgress?:(bytes:number,total:number)=>void}
export type StoredResource = {schema:'capstone-resource/1';resource_id:string;thread_id:string;version:number;file_name:string;size_bytes:number;sha256:string;processing_state:string}
export function parseStoredResources(value:unknown,threadId:string):StoredResource[]{
  const page=value as {schema?:string;resources?:StoredResource[]}
  if(page?.schema!=='capstone-resources/1'||!Array.isArray(page.resources))throw new Error('资源目录无效')
  for(const resource of page.resources)if(resource.schema!=='capstone-resource/1'||resource.thread_id!==threadId
    ||!/^resource_[a-f0-9]{32}$/.test(resource.resource_id)||resource.version!==1||typeof resource.file_name!=='string'
    ||!Number.isSafeInteger(resource.size_bytes)||resource.size_bytes<1||!/^[a-f0-9]{64}$/.test(resource.sha256))throw new Error('资源身份无效')
  return page.resources
}

function checked(value:unknown,file:File):ResourceUpload {
  const item=value as ResourceUpload
  if(!item||item.schema!=='capstone-resource-upload/1'||!/^upload_[a-f0-9]{32}$/.test(item.upload_id)
    ||item.file_name!==file.name||item.size_bytes!==file.size||!Number.isSafeInteger(item.chunk_bytes)
    ||item.chunk_bytes<1||exceedsCapacity(item.chunk_bytes,'upload_chunk_max_bytes')||!Array.isArray(item.received_parts)
    ||!item.part_sha256||typeof item.part_sha256!=='object')throw new Error('上传状态无效，请重新读取')
  return item
}

export async function transferResource(request:Request,path:string,file:File,options:ResourceTransferOptions) {
  assertCapacity(file.size,'upload_file_bytes')
  const {signal}=options
  const raw=options.uploadId
    ?await request(`${path}/${encodeURIComponent(options.uploadId)}`,{signal})
    :await request(path,{method:'POST',signal,body:JSON.stringify({file_name:file.name,size_bytes:file.size,request_id:options.requestId,...(options.draft?{draft:true}:{})})})
  const upload=checked(raw,file)
  if(!['uploading','complete'].includes(upload.state))throw new Error('上传已取消或过期，请重新开始')
  options.onSession?.(upload.upload_id)
  let confirmed=0
  for(let index=0,offset=0;offset<file.size;index++,offset+=upload.chunk_bytes){
    signal?.throwIfAborted()
    const part=file.slice(offset,Math.min(file.size,offset+upload.chunk_bytes))
    const bytes=await part.arrayBuffer()
    const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),x=>x.toString(16).padStart(2,'0')).join('')
    signal?.throwIfAborted()
    if(upload.received_parts.includes(index)){
      if(upload.part_sha256[String(index)]!==hash)throw new Error('所选文件与已上传分片不一致，请选择原文件或重新开始')
    }else{
      const receipt=await request(`${path}/${upload.upload_id}/parts/${index}`,{method:'PUT',body:part,headers:{'Content-Type':'application/octet-stream'},signal}) as {sha256?:string;size_bytes?:number}
      if(receipt.sha256!==hash||receipt.size_bytes!==part.size)throw new Error('分片校验失败，请重试')
    }
    confirmed+=part.size;options.onProgress?.(confirmed,file.size)
  }
  const resource=await request(`${path}/${upload.upload_id}/complete`,{method:'POST',signal}) as {schema?:string;resource_id?:string;version?:number;file_name?:string;size_bytes?:number;sha256?:string}
  if(resource?.schema!=='capstone-resource/1'||resource.resource_id!==upload.upload_id.replace('upload_','resource_')
    ||resource.version!==1||resource.file_name!==file.name||resource.size_bytes!==file.size
    ||!resource.sha256||!/^[a-f0-9]{64}$/.test(resource.sha256))throw new Error('资源保存回执无效，请重试确认')
  return resource
}
