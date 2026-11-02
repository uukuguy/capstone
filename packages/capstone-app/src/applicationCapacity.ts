import defaults from '../../../configs/runtime/application-capacity.json'

export type CapacityKey=keyof typeof defaults.limits
export type CapacityMode='normal'|'debug'
export type CapacityProfile=Readonly<{schema:'capstone-capacity-profile/1';mode:CapacityMode;limits:Readonly<Record<CapacityKey,number>>;fingerprint?:string}>
export class CapacityError extends Error {
  readonly dimension?:CapacityKey
  readonly effective?:number
  readonly fatal:boolean
  readonly mode:CapacityMode
  readonly source:string
  constructor(message:string,readonly key?:CapacityKey,readonly limit?:number,readonly actual?:number,readonly location='capacity-check',details?:{mode?:CapacityMode;source?:string}){
    const source=details?.source||snapshot?.fingerprint||'application-capacity-profile/1'
    super(key?`${message} [dimension=${key}; actual=${actual}; effective=${limit}; source=${source}; location=${location}]`:message)
    this.name='CapacityError';this.dimension=key;this.effective=limit;this.mode=details?.mode||snapshot?.mode||'normal';this.fatal=this.mode==='debug';this.source=source
  }
}
let snapshot:CapacityProfile=Object.freeze({schema:'capstone-capacity-profile/1',mode:'normal',limits:Object.freeze({...defaults.limits})})
/** One immutable effective profile. Install before loading a Thread; no per-view capacity store. */
export function initializeApplicationCapacity(value:unknown={}):CapacityProfile {
  if(!value||typeof value!=='object'||Array.isArray(value))throw new CapacityError('应用容量配置无效')
  const document=value as Record<string,unknown>
  const profile='schema' in document||'limits' in document||'mode' in document
  if(profile&&(document.schema!=='capstone-capacity-profile/1'||Object.keys(document).some(key=>!['schema','mode','limits','fingerprint'].includes(key))))throw new CapacityError('应用容量配置版本或字段无效')
  const mode=document.mode??'normal'
  if(mode!=='normal'&&mode!=='debug')throw new CapacityError('应用容量 mode 必须为 normal 或 debug')
  const limits=profile?document.limits:document
  if(!limits||typeof limits!=='object'||Array.isArray(limits))throw new CapacityError('应用容量 limits 无效')
  const effective={...defaults.limits}
  for(const [key,value] of Object.entries(limits)){
    if(!Object.hasOwn(effective,key))throw new CapacityError(`未知应用容量：${key}`)
    if(!Number.isSafeInteger(value)||(value as number)<(key==='provider_stream_bytes'?0:1))throw new CapacityError(`应用容量 ${key} 必须为${key==='provider_stream_bytes'?'非负':'正'}安全整数`)
    effective[key as CapacityKey]=value as number
  }
  if(profile&&document.fingerprint!==undefined&&typeof document.fingerprint!=='string')throw new CapacityError('应用容量 fingerprint 无效')
  snapshot=Object.freeze({schema:'capstone-capacity-profile/1',mode,limits:Object.freeze(effective),...(typeof document.fingerprint==='string'?{fingerprint:document.fingerprint}:{})})
  return snapshot
}
export const applicationCapacity=(key:CapacityKey):number=>snapshot.limits[key]
export const applicationCapacitySnapshot=():CapacityProfile=>snapshot
export function assertCapacity(actual:number,key:CapacityKey,location='capacity-check'):void {
  const limit=applicationCapacity(key)
  if(actual>limit&&!(key==='provider_stream_bytes'&&limit===0))throw new CapacityError(`超过应用容量 ${key}：当前 ${actual}，上限 ${limit}。`,key,limit,actual,location)
}
/** Soft windows remain usable in normal mode; debug interrupts before any loss. */
export function observeCapacity(actual:number,key:CapacityKey,location:string):boolean {
  const exceeded=actual>applicationCapacity(key)
  if(exceeded&&snapshot.mode==='debug')assertCapacity(actual,key,location)
  return exceeded
}
export function rethrowDebugCapacity(error:unknown):void {if(error instanceof CapacityError&&error.mode==='debug')throw error}
/** Use inside strict schema predicates while keeping a clear capacity error. */
export function exceedsCapacity(actual:number,key:CapacityKey):boolean {assertCapacity(actual,key);return false}

/** Public bootstrap; old hosts can omit the endpoint, invalid advertised profiles cannot. */
export async function readRuntimeCapacity(apiOrigin:string,signal?:AbortSignal,fetcher:typeof fetch=fetch):Promise<CapacityProfile>{
  const response=await fetcher.call(globalThis,`${apiOrigin.replace(/\/$/,'')}/api/v1/runtime-capacity`,{signal,credentials:'omit',cache:'no-store'})
  if(response.status===404||response.status===401)return snapshot
  if(!response.ok)throw new CapacityError(`应用容量配置暂不可读取（${response.status}），请重试。`)
  const text=await response.text()
  assertCapacity(new TextEncoder().encode(text).byteLength,'control_document_bytes')
  signal?.throwIfAborted()
  let value:unknown
  try{value=JSON.parse(text)}catch{throw new CapacityError('应用容量配置不是有效 JSON')}
  return initializeApplicationCapacity(value)
}
