import {useState,type ReactNode} from 'react'
import {ChevronRight} from 'lucide-react'
import type {ProcessLlmPoolCall} from './processLlmPool'
import {requestExecutionMs,type ProcessModelRequest} from './processModelRequestPool'
const labels={queued:'排队中',waiting_dependencies:'等待依赖',running:'执行中',cancelling:'取消中 · 等待释放',completed:'已返回',failed:'请求失败',cancelled:'已停止',blocked:'未执行'}
function RequestRow({request,active,now,action,compactReceipt}:{request:ProcessModelRequest;active:boolean;now?:number;action?:ReactNode;compactReceipt?:boolean}){
 const [manual,setManual]=useState<boolean|undefined>(),automatic=active&&!request.settlementUnobserved&&['running','cancelling'].includes(request.status),open=manual??automatic
 const label=request.settlementUnobserved?'任务已结束 · 请求结算未记录':labels[request.status]
 const ms=requestExecutionMs(request,now)
 const first=request.startedAtMs!==undefined&&request.firstContentAtMs!==undefined?request.firstContentAtMs-request.startedAtMs:undefined
 const release=request.cancelRequestedAtMs!==undefined&&request.finishedAtMs!==undefined?request.finishedAtMs-request.cancelRequestedAtMs:undefined
 return <details className="capstone-call-tool capstone-model-request" open={open} onToggle={event=>{if(event.currentTarget.open!==open)setManual(event.currentTarget.open)}}>
  <summary onClick={event=>{if(event.target instanceof Element&&event.target.closest('button'))return;event.preventDefault();setManual(!open)}}><ChevronRight aria-hidden="true"/>{compactReceipt?<small>调度详情</small>:<><strong>{request.title??(request.kind==='main'?'主链模型请求':'分析模型请求')}</strong><span>{label}</span><small title="实际请求区间，不含排队或依赖等待">{ms===undefined?'耗时未记录':`${(ms/1000).toFixed(1)}s`}</small></>}{action}</summary>
  <div className="capstone-call-tool-detail"><p>{request.id}{compactReceipt&&` · ${label}${ms===undefined?'':` · ${(ms/1000).toFixed(1)}s`}`}{request.startedAtMs!==undefined&&` · 排队 ${((request.startedAtMs-request.queuedAtMs)/1000).toFixed(1)}s`}{request.association==='unassociated'?' · 未关联到父 LLM':''}</p>{request.dependsOn.length>0&&<p>依赖：{request.dependsOn.join('、')}</p>}</div>
  {first!==undefined&&first>=0&&<p>模型首个内容 {(first/1000).toFixed(1)}s</p>}
  {release!==undefined&&release>=0&&request.startedAtMs!==undefined&&<p>取消至请求释放 {(release/1000).toFixed(1)}s</p>}
 </details>
}
export function RequestPoolExecutions({requests,active=false,now,label='实际模型请求',contextAction,compactReceipt}:{contextAction?:(id:string)=>ReactNode;compactReceipt?:boolean;requests:readonly ProcessModelRequest[];active?:boolean;now?:number;label?:string}){
 const visible=requests.filter(request=>request.startedAtMs!==undefined)
 return visible.length?<section aria-label={label}>{visible.map(request=><RequestRow key={request.id} request={request} compactReceipt={compactReceipt} active={active} now={now} action={contextAction?.(request.id)}/>)}</section>:null
}
export default function RequestPoolQueue({requests,jobs=[]}:{requests:readonly ProcessModelRequest[];jobs?:readonly ProcessLlmPoolCall[]}){
 const pending=requests.filter(request=>!request.settlementUnobserved&&['queued','waiting_dependencies'].includes(request.status))
 const semantic=jobs.filter(job=>['queued','waiting_dependencies','running'].includes(job.status)&&!requests.some(request=>request.kind==='analysis'&&request.parentToolCallId===job.parentToolCallId&&request.childId===job.id))
 if(!pending.length&&!semantic.length)return null
 return <section className="capstone-call-pool" aria-label="模型请求等待队列"><p>等待队列 · {pending.length+semantic.length}</p><ul>
  {pending.map(request=><li key={request.id}><span>{request.title??request.id}</span><span>{labels[request.status]}</span>{request.association==='unassociated'&&<small>未关联到父 LLM</small>}{request.dependsOn.length>0&&<small>前驱：{request.dependsOn.join('、')}</small>}</li>)}
  {semantic.map(job=><li key={`${job.parentToolCallId}:${job.id}`}><span>{job.title}</span><span>{job.status==='waiting_dependencies'?'等待依赖':'等待模型请求'}</span></li>)}
 </ul></section>
}
