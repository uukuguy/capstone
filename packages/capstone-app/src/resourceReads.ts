import type {StoredResource} from './resourceUploads'
import {applicationCapacity} from './applicationCapacity'
export type ResourceRead={schema:'capstone-resource-read/1';read_id:string;thread_id:string;attempt_id:string;task_id:string;request_id:string;resource:Omit<StoredResource,'processing_state'>;offset:number;length:number;sha256:string;preview:{bytes_read:number;truncated:boolean;status:'text'|'binary'|'invalid-UTF8';text:string|null}}
export type ResourceReadPage={schema:'capstone-resource-read-page/1';items:ResourceRead[];next_cursor:string|null}
export type ResourceReadClient={supportsResourceReads?:boolean;listResourceReads?:(threadId:string,attemptId:string,cursor?:string,signal?:AbortSignal)=>Promise<ResourceReadPage>;readResourceRead?:(threadId:string,readId:string,attemptId:string,signal?:AbortSignal)=>Promise<ResourceRead>}
const hash=(value:unknown)=>typeof value==='string'&&/^[a-f0-9]{64}$/.test(value)
const identity=(value:unknown)=>typeof value==='string'&&/^[a-zA-Z0-9_-]{1,128}$/.test(value)
const integer=(value:unknown)=>typeof value==='number'&&Number.isSafeInteger(value)&&value>=0
function keys(value:object,expected:string){return Object.keys(value).sort().join(',')===expected.split(',').sort().join(',')}
export function parseResourceRead(value:unknown,threadId:string,attemptId:string):ResourceRead{
 const item=value as ResourceRead
 if(!item||!keys(item,'schema,read_id,thread_id,attempt_id,task_id,request_id,resource,offset,length,sha256,preview')||item.schema!=='capstone-resource-read/1'||!/^read_[a-f0-9]{32}$/.test(item.read_id)||item.thread_id!==threadId||item.attempt_id!==attemptId||!identity(item.task_id)||!identity(item.request_id)||!hash(item.sha256)||!integer(item.offset)||!integer(item.length)||item.length<1)throw new Error('资源读取回执无效')
 const resource=item.resource
 if(!resource||!keys(resource,'schema,resource_id,thread_id,version,file_name,size_bytes,sha256')||resource.schema!=='capstone-resource/1'||resource.thread_id!==threadId||!/^resource_[a-f0-9]{32}$/.test(resource.resource_id)||!integer(resource.version)||resource.version<1||typeof resource.file_name!=='string'||!integer(resource.size_bytes)||resource.size_bytes<1||!hash(resource.sha256))throw new Error('资源身份无效')
 const p=item.preview
 if(item.offset>item.resource.size_bytes-item.length||!p||!keys(p,'bytes_read,truncated,status,text')||!integer(p.bytes_read)||p.bytes_read>Math.min(item.length,applicationCapacity('resource_read_preview_bytes'))||typeof p.truncated!=='boolean'||p.truncated!==(p.bytes_read<item.length)||!['text','binary','invalid-UTF8'].includes(p.status)||(p.status==='text'?(typeof p.text!=='string'||/[\uD800-\uDFFF]/u.test(p.text)||new TextEncoder().encode(p.text).byteLength!==p.bytes_read):p.text!==null))throw new Error('资源读取范围或预览无效')
 return item
}
export function checkResourceReadCursor(cursor:unknown,threadId:string,attemptId:string):asserts cursor is string{
 try{
  if(typeof cursor!=='string'||!cursor.length||cursor.length>1024||! /^[A-Za-z0-9_+\/-]+={0,2}$/.test(cursor))throw new Error()
  const encoded=cursor.replaceAll('-','+').replaceAll('_','/')
  const decoded=atob(encoded)
  if(btoa(decoded)!==encoded)throw new Error()
  const value=JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(Uint8Array.from(decoded,char=>char.charCodeAt(0))))
  if(!value||!keys(value,'thread,attempt,after')||value.thread!==threadId||value.attempt!==attemptId||!integer(value.after))throw new Error()
 }catch{throw new Error('资源读取游标无效')}
}
export function parseResourceReadPage(value:unknown,threadId:string,attemptId:string):ResourceReadPage{
 const page=value as ResourceReadPage
 if(!page||!keys(page,'schema,items,next_cursor')||page.schema!=='capstone-resource-read-page/1'||!Array.isArray(page.items)||page.items.length>50)throw new Error('资源读取目录无效')
 if(page.next_cursor!==null)checkResourceReadCursor(page.next_cursor,threadId,attemptId)
 const items=page.items.map(item=>parseResourceRead(item,threadId,attemptId))
 if(new Set(items.map(item=>item.read_id)).size!==items.length)throw new Error('资源读取回执重复')
 return {...page,items}
}
