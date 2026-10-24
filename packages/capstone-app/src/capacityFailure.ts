export type PublicCapacityFailure={code:'capacity_exceeded';dimension:string;actual:number;limit:number;unit:string;phase:string|null;retryable:false;mode?:'debug';fatal?:true;effective?:number;source?:string;location?:string|null}
const record=(value:unknown):Record<string,unknown>|undefined=>value!==null&&typeof value==='object'&&!Array.isArray(value)?value as Record<string,unknown>:undefined
const identifier=(value:unknown):value is string=>typeof value==='string'&&/^[A-Za-z0-9_.:-]{1,128}$/.test(value)
const phaseName=(value:unknown):value is string=>typeof value==='string'&&/^[A-Za-z0-9_.:/ -]{1,160}$/.test(value)

/** Only the closed public failure projection is reader-facing, never exception text. */
export function parseCapacityFailure(value:unknown):PublicCapacityFailure|undefined{
  const capacity=record(value)
  if(!capacity||Object.keys(capacity).some(key=>!['actual','code','dimension','limit','phase','retryable','unit','mode','fatal','effective','source','location'].includes(key))
    ||!['actual','code','dimension','limit','phase','retryable','unit'].every(key=>Object.hasOwn(capacity,key))
    ||capacity.code!=='capacity_exceeded'||!identifier(capacity.dimension)||!identifier(capacity.unit)
    ||typeof capacity.actual!=='number'||!Number.isFinite(capacity.actual)||typeof capacity.limit!=='number'||!Number.isFinite(capacity.limit)
    ||capacity.limit<0||capacity.actual<=capacity.limit||capacity.retryable!==false
    ||capacity.phase!==null&&!phaseName(capacity.phase))return
  const debugFields=['mode','fatal','effective','source','location']
  if(debugFields.some(key=>Object.hasOwn(capacity,key))&&(capacity.mode!=='debug'||capacity.fatal!==true||capacity.effective!==capacity.limit
    ||!identifier(capacity.source)||capacity.location!==null&&!phaseName(capacity.location)))return
  return {...capacity} as PublicCapacityFailure
}

export function capacityFailureNotice(payload:Record<string,unknown>):string|undefined{
  const failure=record(payload.failure),raw=record(failure?.capacity)
  const capacity=parseCapacityFailure(raw)
  const codes=new Set(['capacity_exceeded','native_capacity_exceeded'])
  if(!capacity&&!codes.has(String(failure?.code))&&!codes.has(String(payload.error_code))&&raw?.code!=='capacity_exceeded')return
  if(!capacity)return '**执行超过容量限制**\n\n当前记录未提供可核对的实际值与上限。请查看执行过程，并检查应用容量配置。'
  const unit:Record<string,string>={bytes:'字节',chars:'字符',characters:'字符',items:'项',count:'项',seconds:'秒',milliseconds:'毫秒',tokens:'tokens'}
  const measure=unit[capacity.unit]||capacity.unit
  const phase=capacity.location||capacity.phase||(phaseName(failure?.phase)?failure.phase:'未记录')
  return `**执行超过容量限制**\n\n容量项：${capacity.dimension}\n\n实际：${capacity.actual} ${measure}\n\n上限：${capacity.limit} ${measure}\n\n发生位置：${phase}${capacity.mode==='debug'?`\n\n模式：debug · 已立即中断\n\n配置来源：${capacity.source}`:''}\n\n此容量失败不会自动重试；请减少本轮内容或调整应用容量后再发送。`
}
