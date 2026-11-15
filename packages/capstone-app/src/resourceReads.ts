import {parseStoredResources,type StoredResource} from './resourceUploads'
export type ResourceRead={schema:'capstone-resource-read/1';read_id:string;thread_id:string;attempt_id:string;task_id:string;request_id:string;resource:StoredResource;offset:number;length:number;sha256:string;preview:{bytes_read:number;truncated:boolean;status:'text'|'binary'|'invalid-UTF8';text:string|null}}
export type ResourceReadPage={schema:'capstone-resource-read-page/1';items:ResourceRead[];next_cursor:string|null}
export type ResourceReadClient={supportsResourceReads?:boolean;listResourceReads?:(threadId:string,attemptId:string,cursor?:string,signal?:AbortSignal)=>Promise<ResourceReadPage>;readResourceRead?:(threadId:string,readId:string,attemptId:string,signal?:AbortSignal)=>Promise<ResourceRead>}
const hash=(value:unknown)=>typeof value==='string'&&/^[a-f0-9]{64}$/.test(value)
const identity=(value:unknown)=>typeof value==='string'&&/^[a-zA-Z0-9_-]{1,128}$/.test(value)
const integer=(value:unknown)=>typeof value==='number'&&Number.isSafeInteger(value)&&value>=0
function keys(value:object,expected:string){return Object.keys(value).sort().join(',')===expected.split(',').sort().join(',')}
export function parseResourceRead(value:unknown,threadId:string,attemptId:string):ResourceRead{
 const item=value as ResourceRead
 if(!item||!keys(item,'schema,read_id,thread_id,attempt_id,task_id,request_id,resource,offset,length,sha256,preview')||item.schema!=='capstone-resource-read/1'||!/^read_[a-f0-9]{32}$/.test(item.read_id)||item.thread_id!==threadId||item.attempt_id!==attemptId||!identity(item.task_id)||!identity(item.request_id)||!hash(item.sha256)||!integer(item.offset)||!integer(item.length)||item.length<1)throw new Error('资源读取回执无效')
 parseStoredResources({schema:'capstone-resources/1',resources:[item.resource]},threadId)
 const p=item.preview
 if(item.offset>item.resource.size_bytes-item.length||!p||!keys(p,'bytes_read,truncated,status,text')||!integer(p.bytes_read)||p.bytes_read>Math.min(item.length,8192)||typeof p.truncated!=='boolean'||p.truncated!==(p.bytes_read<item.length)||!['text','binary','invalid-UTF8'].includes(p.status)||(p.status==='text'?(typeof p.text!=='string'||new TextEncoder().encode(p.text).byteLength>8192):p.text!==null))throw new Error('资源读取范围或预览无效')
 return item
}
export function parseResourceReadPage(value:unknown,threadId:string,attemptId:string):ResourceReadPage{
 const page=value as ResourceReadPage
 if(!page||!keys(page,'schema,items,next_cursor')||page.schema!=='capstone-resource-read-page/1'||!Array.isArray(page.items)||page.items.length>50||(page.next_cursor!==null&&(typeof page.next_cursor!=='string'||!page.next_cursor.length||page.next_cursor.length>2048)))throw new Error('资源读取目录无效')
 const items=page.items.map(item=>parseResourceRead(item,threadId,attemptId))
 if(new Set(items.map(item=>item.read_id)).size!==items.length)throw new Error('资源读取回执重复')
 return {...page,items}
}
