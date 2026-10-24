import {applicationCapacity,exceedsCapacity} from './applicationCapacity'
export const MAX_THREAD_MATERIAL_BYTES=applicationCapacity('inline_material_bytes')
export type ThreadMaterial={schema:'capstone-thread-material/1';thread_id:string;material_id:string;file_name:string;display_name:string;media_type:'text/plain'|'text/markdown'|'text/csv';sha256:string;size_bytes:number;created_at:string}
export function parseThreadMaterial(value:unknown,threadId:string):ThreadMaterial {
  if(!value||typeof value!=='object'||Array.isArray(value))throw new Error('资料信息无效')
  const item=value as Record<string,unknown>
  const media:Record<string,string>={txt:'text/plain',md:'text/markdown',csv:'text/csv'}
  if(item.schema!=='capstone-thread-material/1'||item.thread_id!==threadId||typeof item.material_id!=='string'||!/^material_[a-f0-9]{32}$/.test(item.material_id)
    ||typeof item.file_name!=='string'||!item.file_name||/[\\/\u0000-\u001f\u007f]/.test(item.file_name)||new TextEncoder().encode(item.file_name).byteLength>255
    ||typeof item.display_name!=='string'||!item.display_name.trim()||item.display_name.length>255
    ||item.media_type!==media[item.file_name.split('.').pop()?.toLowerCase()||'']
    ||typeof item.sha256!=='string'||!/^[a-f0-9]{64}$/.test(item.sha256)||!Number.isSafeInteger(item.size_bytes)||(item.size_bytes as number)<1||exceedsCapacity(item.size_bytes as number,'inline_material_bytes')
    ||typeof item.created_at!=='string'||!Number.isFinite(Date.parse(item.created_at)))throw new Error('资料归属或文件信息无效')
  return {...item} as ThreadMaterial
}
