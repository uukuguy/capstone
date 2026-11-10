import { useEffect, useRef, useState, type ReactNode } from 'react'
import { AlertTriangle, ChevronRight, Check, CircleX, CircleDashed, LoaderCircle, Square, BrainCircuit } from 'lucide-react'
import { receiptDuration, receiptBatchSummary, dispatchDuration, type ToolBatch, type ToolDispatchReceipt, type ToolExecutionReceipt } from './toolExecutionReceipt'
import { batchElapsedMs,toolExecutionMs } from './processTiming'
import './processCallTrace.css'
import ThinkingProcess from './ThinkingProcess'
import {summarizeLlmPoolCalls,type ProcessLlmPoolCall} from './processLlmPool'
import {requestExecutionMs,uniqueModelRequests,type ProcessModelRequest} from './processModelRequestPool'
import RequestPoolQueue,{RequestPoolExecutions} from './RequestPoolQueue'
import {responseOpeningIntent,scriptOpeningIntent} from './executionIntent'
import {compactionDuration,type ProcessCompaction} from './processCompactions'

export type ProcessModelCall = { retry?:{attempt:number;maximum?:number;delayMs?:number;success?:boolean;finished?:boolean}; id: string; number: number; ms: number; requestPool?:readonly ProcessModelRequest[];requestPoolOnly?:boolean;poolCalls?:readonly ProcessLlmPoolCall[]; label?: string; intent?: string; thinking?: string; thinkingStartedAt?: string; thinkingEndedAt?: string; thinkingSettled?: boolean; sequenceId?: string; settled?: boolean; startedAt?: string; finishedAt?: string; toolAssociation?: 'turn'; toolCallIds?: readonly string[]; stopReason?: string; errorCode?: string; errorStatus?: number; usage?: Record<string, unknown>; responseText?: string; toolRequests?: readonly { id: string; name: string; operation?: string }[] }
const modelErrors:Record<string,string>={model_context_limit:'上下文超限',model_rate_limit:'请求限流',model_authentication:'模型认证失败',model_transport:'模型连接异常',model_output_invalid:'模型输出格式异常',model_output_rejected:'模型输出被拒绝',model_turn_incomplete:'原因未记录'}
export type ProcessToolCall = { serviceBusCalls?: ServiceBusCalls; kind?: 'skill'; toolBatch?: ToolBatch; dispatchReceipt?: ToolDispatchReceipt; executionReceipt?: ToolExecutionReceipt; id: string; name: string; status: 'running' | 'completed' | 'failed' | 'cancelled'; startedAt?: string; finishedAt?: string; durationMs?: number; executionMs?: number; operation?: string; warning?: string; failure?: string; origin?: 'model' | 'parent' | 'system' | 'unknown' }
export type ProcessTraceFocus = { modelId: string; revision: number }
export function callTraceIssues(models: readonly ProcessModelCall[], tools: readonly ProcessToolCall[], active = true) {
  return models.flatMap(model => {
    if (active && !models.some(next => next.sequenceId === model.sequenceId && next.number > model.number)) return []
    const missingToolIds = [...new Set(model.toolCallIds ?? [])].filter(id => {
      const tool = tools.find(item => item.id === id)
      return !tool || (!active && tool.status === 'running')
    })
    return missingToolIds.length ? [{ modelId: model.id, number: model.number, missingToolIds }] : []
  })
}
const count = (value: unknown) => typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : undefined
const tokens = (value: number | undefined) => value === undefined ? '—' : value.toLocaleString('zh-CN')
const time = (ms: number) => `${(ms / 1000).toFixed(1)}s`
const toolTime = (ms: number) => ms < 1000 ? `${Math.round(ms)}ms` : time(ms)
function BatchHeading({title,count,summary,callerElapsedMs,running=false}:{title:string;count:number;summary:{capacity?:number;peak?:number;elapsedMs?:number};callerElapsedMs?:number;running?:boolean}){
  const elapsed=summary.elapsedMs??callerElapsedMs
  const callerTiming=summary.elapsedMs===undefined&&callerElapsedMs!==undefined
  return <div className="capstone-parallel-heading">
    <span className="capstone-parallel-title">{title} · {count} 项</span>
    <span className="capstone-batch-metrics">
      {summary.capacity!==undefined&&<span>执行容量 {summary.capacity}</span>}
      {summary.peak!==undefined&&<span>{summary.capacity!==undefined?' · ':''}观测峰值 {summary.peak}</span>}
      <span aria-label={running?'本批次已用时间':'本批次总耗时'} title={elapsed===undefined?'本批次缺少完整计时记录。':callerTiming?'调用区间：从本批次首个调用发起到最后返回，含等待；不能据此推断实际执行重叠。':'执行回执：从本批次首个提交到最后执行结束，含排队。'}>{' · '}{elapsed===undefined?'—':toolTime(elapsed)}</span>
    </span>
  </div>
}
function CallGlyph({label,kind}:{label:string;kind:string}){
  const Icon=kind==='done'?Check:kind==='failed'?CircleX:kind==='running'?LoaderCircle:kind==='cancelled'?Square:kind==='warning'?AlertTriangle:CircleDashed
  return <span role="img" aria-label={label} title={label} className={`capstone-call-state is-${kind}`}><Icon aria-hidden="true"/></span>
}
function ToolFailureNotice({message,running}:{message:string;running:boolean}){
  const [expanded,setExpanded]=useState(running)
  useEffect(()=>setExpanded(running),[running])
  return <button type="button" className={`capstone-call-notice is-error capstone-tool-failure${expanded?' is-expanded':''}`} aria-expanded={expanded} title={message} onClick={()=>setExpanded(value=>!value)}><CircleX aria-hidden="true"/><span>{message}</span></button>
}
function latencyGrade(ms: number | undefined, kind: 'model' | 'tool') {
  if(ms===undefined||!Number.isFinite(ms)||ms<0)return {level:undefined,label:'耗时未记录'}
  const [noticeable,slow,verySlow]=kind==='model'?[10000,30000,60000]:[1000,5000,15000]
  return ms>=verySlow?{level:'very-slow',label:`明显偏长（≥${verySlow/1000}s）`}
    :ms>=slow?{level:'slow',label:`偏长（≥${slow/1000}s）`}
    :ms>=noticeable?{level:'noticeable',label:`较长（≥${noticeable/1000}s）`}
    :{level:'normal',label:'常规耗时'}
}
function operationExcerpt(name: string, operation: string) {
  if(name==='bash')return scriptOpeningIntent(operation)??'执行脚本'
  const compact = operation.replace(/\s+/g, ' ').trim()
  return compact.length > 120 ? compact.slice(0, 120) + '…' : compact
}
/** A one-line action sentence. Shell text without a comment is a command, not a purpose. */
function purposeTitle(name: string, operation?: string): string | undefined {
  const text = operation?.trim()
  if (!text) return undefined
  if (name === 'bash') return scriptOpeningIntent(text)
  const line = text.split(/\r?\n/, 1)[0].replace(/\s+/g, ' ').trim()
  if (!line || !/[\u4e00-\u9fff]/.test(line) || /^[{[`]|```/.test(line) || /(?:api[_ -]?key|access[_ -]?token|authorization|password|secret)["']?\s*[:=]/i.test(line)) return undefined
  return line.length > 80 ? `${line.slice(0, 80)}…` : line
}
/** The model sometimes puts its one-line purpose on the tool instead of the LLM opening. */
function omittedCallPurpose(requests: readonly { id: string; name: string; operation?: string }[]): { id: string; text: string } | undefined {
  for (const item of requests) {
    const text = purposeTitle(item.name, item.operation)
    if (text) return { id: item.id, text }
  }
  return undefined
}
export function modelCallMs(call: Omit<ProcessModelCall, 'id'>, now?: number): number {
  const actual=call.requestPool?.filter(request=>request.association==='main')
  if(actual?.length)return actual.reduce((sum,request)=>sum+(requestExecutionMs(request,now)??0),0)
  const start = Date.parse(call.startedAt ?? '')
  return call.startedAt && !call.finishedAt && now !== undefined && Number.isFinite(start) && now >= start ? now - start : call.ms
}

/** Neutral presentation: adapters supply admitted identities, never inferred causality. */
export default function ProcessCallTrace({ models, tools, compactions = [], now, active = true, compact = false, expandedTools = false, expandedThinking = false, renderToolDetails, focusRequest }: {
  models: readonly ProcessModelCall[]; tools: readonly ProcessToolCall[]; now?: number; active?: boolean;
  compactions?:readonly ProcessCompaction[];
  renderToolDetails?: (tool: ProcessToolCall) => ReactNode;
  focusRequest?: ProcessTraceFocus;
  compact?: boolean;
  expandedTools?: boolean;
  expandedThinking?: boolean;
}) {
  const roundElements = useRef(new Map<string, HTMLElement>())
  useEffect(() => {
    if (!focusRequest) return
    const timer = window.setTimeout(() => {
      const element = roundElements.current.get(focusRequest.modelId)
      element?.scrollIntoView?.({ block: 'nearest' }); element?.focus({ preventScroll: true })
    }, 0)
    return () => window.clearTimeout(timer)
  }, [focusRequest])
  const issues = callTraceIssues(models, tools, active)
  const owners = new Map<string, string[]>()
  for (const model of models) for (const id of new Set(model.toolCallIds ?? [])) owners.set(id, [...(owners.get(id) ?? []), model.id])
  const owned = (tool: ProcessToolCall, model: ProcessModelCall) => tool.origin !== 'system' && tool.origin !== 'parent' && owners.get(tool.id)?.length === 1 && owners.get(tool.id)![0] === model.id
  const timed = (tool: ProcessToolCall) => tool.status === 'running' && active && now !== undefined && tool.startedAt && now >= Date.parse(tool.startedAt)
    ? { ...tool, durationMs: now - Date.parse(tool.startedAt) } : tool
  const latestModelId=models.filter(model=>!model.requestPoolOnly).at(-1)?.id
  const poolCalls=models.flatMap(model=>model.poolCalls??[])
  const dispatches=uniqueModelRequests(models.flatMap(model=>model.requestPool??[]))
  const unassociated=dispatches.filter(request=>request.association==='unassociated')
  const hasQueue=dispatches.some(request=>['queued','waiting_dependencies'].includes(request.status))||dispatches.length>0&&poolCalls.some(job=>['queued','waiting_dependencies','running'].includes(job.status)&&!dispatches.some(request=>request.childId===job.id&&request.parentToolCallId===job.parentToolCallId))
  const renderPool=(parentId:string)=>{
    const actual=dispatches.filter(request=>request.association==='analysis'&&request.parentToolCallId===parentId)
    if(actual.length)return <RequestPoolExecutions requests={actual} active={active} now={now}/>
    const children=poolCalls.filter(call=>call.parentToolCallId===parentId&&(!dispatches.length||!['queued','waiting_dependencies','running'].includes(call.status)))
    if(!children.length)return null
    const summary=summarizeLlmPoolCalls(children)
    const labels={queued:'排队中',waiting_dependencies:'等待依赖',running:'执行中',cancelling:'取消中',completed:'已完成',failed:'未完成',cancelled:'已停止',blocked:'依赖未完成'}
    return <section className="capstone-call-pool" aria-label="轻量子 LLM 调用">
      <p>{summary.maxConcurrency>1?`并行分析 · 峰值并发 ${summary.maxConcurrency} · `:''}子 LLM 响应 {summary.responses??'—'} 次 · 响应累计 {summary.responseMs===undefined?'未完整记录':time(summary.responseMs)}</p>
      <ul>{children.map(call=><li key={call.id}><span title={call.title}>{call.title}</span><span>{labels[call.status]}</span><small>响应 {call.responseMs===undefined?'—':time(call.responseMs)}</small></li>)}</ul>
    </section>
  }
  const renderTool = (tool: ProcessToolCall, independent = false) => {
    const isSkill=tool.kind==='skill'||tool.name==='agent_skill'
    const skillName=tool.operation?.match(/^([a-z0-9][a-z0-9_-]{0,127}) · (?:已加载|模型报告)$/)?.[1]
    const skillTitle=tool.name==='agent_skill'?(skillName??'技能'):tool.name.replace(/^使用任务技能 · /,'')
    const executionMs = dispatchDuration(tool.dispatchReceipt) ?? receiptDuration(tool.executionReceipt, 'execution_started', 'execution_ended')
    const queueMs = receiptDuration(tool.executionReceipt, 'queued', 'acquired')
    const excerpt = tool.operation?.trim() ? operationExcerpt(tool.name, tool.operation) : tool.name
    const sentence = independent ? undefined : purposeTitle(tool.name, tool.operation)
    const title = isSkill?skillTitle:sentence?tool.name:excerpt
    const purposeIsEntireOperation = !!sentence && !!tool.operation && sentence === tool.operation.replace(/\s+/g, ' ').trim()
    const batch=models.find(model=>model.toolCallIds?.includes(tool.id))
    const batchRunning=active&&(batch?batch.toolCallIds!.some(id=>{const item=tools.find(candidate=>candidate.id===id);return !item||item.status==='running'}):tool.status==='running')
    return <div key={tool.id} className={`capstone-call-tool-entry${isSkill?' is-skill':''}`}><details className="capstone-call-tool" open={expandedTools||Boolean(active&&dispatches.some(request=>request.parentToolCallId===tool.id&&['running','cancelling'].includes(request.status)))||Boolean(compact&&active&&latestModelId&&owners.get(tool.id)?.length===1&&owners.get(tool.id)?.[0]===latestModelId)}>
    <summary><ChevronRight aria-hidden="true" />{isSkill&&<span className="capstone-skill-badge">技能</span>}<strong title={tool.name}>{title}</strong>
      {!isSkill && !sentence && tool.operation?.trim() && excerpt !== tool.name && <small>{tool.name}</small>}
      {independent && tool.origin && <small>{tool.origin === 'system' ? '系统动作' : tool.origin === 'parent' ? '主链调用' : null}</small>}
      <span className="capstone-call-duration" data-latency={latencyGrade(executionMs??timed(tool).durationMs,'tool').level} title={`${executionMs === undefined ? '调用记录区间 · 实际执行未知' : '工具执行耗时'} · ${latencyGrade(executionMs??timed(tool).durationMs,'tool').label}`}>{executionMs === undefined && timed(tool).durationMs === undefined ? '耗时未记录' : toolTime(executionMs ?? timed(tool).durationMs!)}</span>
      {compact?<CallGlyph label={tool.status==='completed'?'完成':tool.status==='failed'?'失败':tool.status==='cancelled'?'已停止':active?'执行中':'未完整记录'} kind={tool.status==='completed'?'done':tool.status==='failed'?'failed':tool.status==='cancelled'?'cancelled':active?'running':'unknown'}/>:<span>{tool.status === 'completed' ? '完成' : tool.status === 'failed' ? '失败' : tool.status === 'cancelled' ? '已停止' : active ? '执行中' : '未完整记录'}</span>}

    </summary>
    <div className="capstone-call-tool-detail">
      <ServiceBusCallDetails calls={tool.serviceBusCalls}/>
      <p>执行端排队 {queueMs === undefined ? '未知' : time(queueMs)} · 工具执行 {executionMs === undefined ? '未知' : time(executionMs)} · 记录区间 {tool.durationMs === undefined ? '—' : time(timed(tool).durationMs!)}</p>
      {independent && tool.origin !== 'system' && <p>{tool.origin === 'parent' ? '由主链发起，不属于本任务的 LLM 轮次。' : '记录未提供对应的 LLM 调用标识。'}</p>}
      {tool.operation && !purposeIsEntireOperation && <p className="capstone-call-operation">{tool.operation}</p>}
      {tool.name==='agent_llm_submit'&&renderPool(tool.id)}
      {renderToolDetails?.(tool)}
    </div>
  </details>
    {tool.status==='failed'&&<ToolFailureNotice running={batchRunning} message={tool.failure==='Composition stopped'?'同一组合已停止，这次调用被取消。':tool.failure||'工具执行失败，展开查看返回详情'}/>}
    {tool.warning&&<p className="capstone-call-notice is-warning" role="status"><AlertTriangle aria-hidden="true"/><span>{tool.warning}</span></p>}
  </div>
  }
  const timestamp = (value?: string) => { const parsed = Date.parse(value ?? ''); return Number.isFinite(parsed) ? parsed : Infinity }
  const entries: {id:string;at?:string;model?:ProcessModelCall;tool?:ProcessToolCall;compaction?:ProcessCompaction}[] = [
    ...models.filter(model=>{
      if(model.requestPoolOnly)return false
      const main=model.requestPool?.filter(request=>request.association==='main')??[]
      return !main.length||main.some(request=>request.startedAtMs!==undefined)||main.every(request=>['completed','failed','cancelled','blocked'].includes(request.status))
    }).map(model => ({ id: `model:${model.id}`, at: model.startedAt ?? model.finishedAt, model, tool: undefined as ProcessToolCall | undefined })),
    ...tools.filter(tool => !models.some(model => owned(tool, model))).map(tool => ({ id: `tool:${tool.id}`, at: tool.startedAt, model: undefined as ProcessModelCall | undefined, tool })),
    ...compactions.map(compaction=>({id:`compaction:${compaction.id}`,at:compaction.startedAt??compaction.finishedAt,compaction})),
  ].sort((a, b) => timestamp(a.at) - timestamp(b.at))
  if (!entries.length&&!dispatches.length&&!hasQueue) return <p>尚未收到调用记录。</p>
  return <ol className={`capstone-call-trace${compact?' is-compact':''}`} aria-label="模型与工具调用过程">{entries.map(entry => {
    if(entry.compaction){
      const phase=entry.compaction,duration=compactionDuration(phase,active,now),running=phase.state==='started'&&active
      const reason={manual:'手动触发',threshold:'上下文达到压缩阈值',overflow:'上下文超限',unknown:'原因未记录'}[phase.reason]
      const status=phase.state==='started'?(running?'进行中':'未完整记录'):{completed:'已完成',cancelled:'已取消',failed:'失败',skipped:'已跳过'}[phase.state]
      return <li key={entry.id}><div className="capstone-call-model" role={running?'status':undefined} aria-label="上下文压缩">
        <strong>{running?'正在压缩上下文':'上下文压缩'}</strong><span className="capstone-call-purpose">{reason}</span>
        <span className="capstone-call-duration">{duration===undefined?'耗时未记录':time(duration)}</span><span>{status}</span>
        {phase.willRetry&&<small>将重试模型请求</small>}
      </div></li>
    }
    if (entry.tool) return <li key={entry.id}>{renderTool(entry.tool, true)}</li>
    const model = entry.model!, selected = tools.filter(tool => owned(tool, model)), toolMs = toolExecutionMs(selected.map(timed))
    const batchTitle = model.toolAssociation === 'turn' ? '并行工具调用' : '同一响应工具批次'
    const requests = model.toolRequests ?? selected.map(tool => ({ id: tool.id, name: tool.name, operation: tool.operation }))
    const ownPurpose=model.intent?.trim()||responseOpeningIntent(model.responseText)
    const lifted=ownPurpose?undefined:omittedCallPurpose(requests)
    const intent=ownPurpose||lifted?.text
    const responseText=responseOpeningIntent(model.responseText)?model.responseText?.split(/\r?\n/).slice(1).join('\n').trim():model.responseText
    const mainDispatches=model.requestPool?.filter(request=>request.association==='main')??[]
    const unexecuted=mainDispatches.length>0&&mainDispatches.every(request=>request.startedAtMs===undefined)&&mainDispatches.every(request=>['completed','failed','cancelled','blocked'].includes(request.status))
    const unexecutedLabel=mainDispatches.some(request=>request.status==='cancelled')?'已停止':'未执行'
    const pending = !!model.startedAt && !model.finishedAt, running = pending && active && !model.settled&&(!mainDispatches.length||mainDispatches.some(request=>['running','cancelling'].includes(request.status)))
    const waiting=mainDispatches.some(request=>['queued','waiting_dependencies'].includes(request.status))&&!running
    const grade=latencyGrade(pending&&(!active||model.settled)?undefined:modelCallMs(model,running?now:undefined),'model')
    const linked = model.toolCallIds !== undefined
    const issue = issues.find(item => item.modelId === model.id)
    const usage = model.usage, inputParts = [count(usage?.input), count(usage?.cacheRead), count(usage?.cacheWrite)]
    const input = inputParts.every(value => value !== undefined) ? inputParts.reduce<number>((sum, value) => sum + value!, 0) : undefined
    const tokenSummary = usage && <span className="capstone-call-tokens" title="输入包含 SDK 单独报告的缓存读取/写入 token；未报告的值保持未知。">
      <span>输入 {tokens(input)}</span><span>输出 {tokens(count(usage.output))}</span>
      {count(usage.cacheRead) !== undefined && Number(usage.cacheRead) > 0 && <span>缓存 {tokens(count(usage.cacheRead))}</span>}<span>token</span>
    </span>
    return <li key={entry.id}><section role="group" aria-label={model.label ?? `LLM 调用 ${model.number}`} className="capstone-call-round" data-record-gap={issue ? true : undefined}
      tabIndex={-1} ref={element => { if (element) roundElements.current.set(model.id, element); else roundElements.current.delete(model.id) }}>
      <div className="capstone-call-model capstone-llm-call-heading">{compact&&<span role="img" aria-label="LLM 调用" title="LLM 模型调用"><BrainCircuit className="capstone-call-model-icon" aria-hidden="true"/></span>}<strong className="capstone-call-model-label" title={`LLM 调用 ${model.number}`}>{model.label ?? `LLM ${String(model.number).padStart(2, '0')}`}</strong>
        {intent&&<strong className="capstone-call-purpose" title={intent}>{intent}</strong>}
        <span className="capstone-call-duration" data-latency={unexecuted?undefined:grade.level} title={unexecuted?'请求未实际启动':`LLM 响应 · ${grade.label}`}>{unexecuted?'未执行':waiting?'等待调度':pending && (!active || model.settled)&&!mainDispatches.length ? '耗时 —' : time(modelCallMs(model, running ? now : undefined))}</span>
        {unexecuted?<CallGlyph label={unexecutedLabel} kind={unexecutedLabel==='已停止'?'cancelled':'unknown'}/>:compact?<CallGlyph label={waiting?'排队中':model.stopReason==='error'?'错误响应':model.stopReason==='aborted'?'已中断':running?'进行中':pending?'未完整记录':model.stopReason==='length'?'输出截断':'已返回'} kind={model.stopReason==='error'?'failed':model.stopReason==='aborted'?'cancelled':running?'running':pending?'unknown':model.stopReason==='length'?'warning':'done'}/>:waiting?<span>排队中</span>:model.stopReason === 'error' ? <span>错误响应</span> : model.stopReason === 'aborted' ? <span>已中断</span> : running ? <span role="status">进行中</span> : pending ? <span>未完整记录</span> : model.stopReason === 'length' ? <span>输出截断</span> : <span>已返回</span>}
        {model.retry&&<span>模型重试 {model.retry.attempt}{model.retry.maximum?`/${model.retry.maximum}`:''}{model.retry.success===true?' · 已完成':model.retry.success===false?' · 未成功':model.retry.finished?' · 结果未记录':models.some(next=>next.number>model.number&&next.startedAt)?' · 已发起':` · 计划等待 ${((model.retry.delayMs??0)/1000).toFixed(1)}s`}</span>}
        {model.stopReason==='error'&&model.errorCode&&Object.hasOwn(modelErrors,model.errorCode)&&<span>{modelErrors[model.errorCode]}{typeof model.errorStatus==='number'&&Number.isInteger(model.errorStatus)&&model.errorStatus>=400&&model.errorStatus<=599?` · HTTP ${model.errorStatus}`:''}{models.some(next=>next.number>model.number&&next.startedAt)?' · 后续模型调用已开始':''}</span>}
        {!compact&&!running && <small title={model.toolAssociation==='turn'?'依据同一 SDK 执行轮次中的实际工具调用记录归组。':undefined}>{!linked ? '工具关联未记录' : !model.toolCallIds!.length ? '未调用工具' : `${model.toolAssociation==='turn'?'本轮工具':'工具'} ${model.toolCallIds!.length}次${toolMs === undefined || model.toolAssociation==='turn' ? '' : ` · 活动区间 ${time(toolMs)}`}`}</small>}
      </div>
      {!compact&&model.toolAssociation!=='turn'&&requests.length > 0 && <p className="capstone-call-intent" title={requests.map(item => `${item.name}${item.operation ? ' · ' + item.operation : ''}`).join('；')}>发起工具：{requests.map(item => `${item.name}${item.operation && !purposeTitle(item.name, item.operation) ? ' · ' + operationExcerpt(item.name, item.operation) : ''}`).join('；')}</p>}
      {responseText && <p className="capstone-call-response" title={responseText}>{responseText.length > 240 ? responseText.slice(0,240) + '…' : responseText}</p>}
      {issue && <div className="capstone-call-gap"><p role="status"><AlertTriangle aria-hidden="true" />工具记录缺失 · {issue.missingToolIds.length}项</p>
        <details><summary>缺失明细</summary><ul>{issue.missingToolIds.map(id => <li key={id}>
          <strong>{model.toolRequests?.find(item => item.id === id)?.name ?? '工具名称未记录'}</strong> · {tools.some(tool => tool.id === id) ? '缺少结果记录' : '缺少执行记录'}<code>{id}</code>
        </li>)}</ul></details></div>}
      <div className="capstone-call-nested"><ThinkingProcess kind="call" expanded={expandedThinking} trailing={tokenSummary} storageKey={`model-thinking:${model.id}`} now={now} thinking={{text:model.thinking??'',startedAt:model.thinking?model.thinkingStartedAt:undefined,endedAt:running&&!model.thinkingSettled?undefined:model.thinkingEndedAt,handedOff:!running||model.thinkingSettled===true,phase:running&&!model.thinkingSettled?'running':'completed'}}/>{selected.length > 0 && <div className="capstone-call-batch" aria-label="本轮工具调用">{selected.length>1?(()=>{const batch=selected[0]?.toolBatch;const exactBatch=batch&&batch.call_ids.length===model.toolCallIds?.length&&selected.every(tool=>tool.toolBatch?.batch_id===batch.batch_id&&batch.call_ids.includes(tool.id));const summary=exactBatch?{elapsedMs:batch.elapsed_ms}:receiptBatchSummary((model.toolCallIds??[]).map(id=>selected.find(tool=>tool.id===id)?.executionReceipt));return <div className="capstone-parallel-group" role="group" aria-label={`${batchTitle} · ${model.toolCallIds!.length} 项`}><BatchHeading title={batchTitle} count={model.toolCallIds!.length} summary={summary} callerElapsedMs={model.toolCallIds!.length===selected.length?batchElapsedMs(selected,active,now):undefined} running={active&&selected.some(tool=>tool.status==='running')}/>{selected.map(tool=>renderTool(tool))}</div>})():selected.map(tool=>renderTool(tool))}</div>}</div>

      {!issue && linked && model.toolCallIds!.length > selected.length && <p className="capstone-call-pending">等待工具记录 · {model.toolCallIds!.length - selected.length}项</p>}
      {mainDispatches.length>0&&<RequestPoolExecutions requests={mainDispatches} active={active} now={now}/>}
    </section></li>
  })}{unassociated.some(request=>request.startedAtMs!==undefined)&&<li><RequestPoolExecutions label="未关联模型请求" requests={unassociated} active={active} now={now}/></li>}{hasQueue&&<li><RequestPoolQueue requests={dispatches} jobs={poolCalls}/></li>}</ol>
}
import ServiceBusCallDetails from './ServiceBusCallDetails'
import type {ServiceBusCalls} from './serviceBusCalls'
