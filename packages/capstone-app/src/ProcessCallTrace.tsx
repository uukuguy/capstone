import { useEffect, useRef, type ReactNode } from 'react'
import { AlertTriangle, ChevronRight, Check, CircleX, CircleDashed, LoaderCircle, Square, BrainCircuit } from 'lucide-react'
import { toolExecutionMs } from './processTiming'
import './processCallTrace.css'
import ThinkingProcess from './ThinkingProcess'

export type ProcessModelCall = { id: string; number: number; ms: number; label?: string; intent?: string; thinking?: string; thinkingStartedAt?: string; thinkingEndedAt?: string; thinkingSettled?: boolean; sequenceId?: string; settled?: boolean; startedAt?: string; finishedAt?: string; toolAssociation?: 'turn'; toolCallIds?: readonly string[]; stopReason?: string; errorCode?: string; errorStatus?: number; usage?: Record<string, unknown>; responseText?: string; toolRequests?: readonly { id: string; name: string; operation?: string }[] }
const modelErrors:Record<string,string>={model_context_limit:'上下文超限',model_rate_limit:'请求限流',model_authentication:'模型认证失败',model_transport:'模型连接异常',model_output_invalid:'模型输出格式异常',model_output_rejected:'模型输出被拒绝',model_turn_incomplete:'原因未记录'}
export type ProcessToolCall = { id: string; name: string; status: 'running' | 'completed' | 'failed' | 'cancelled'; startedAt?: string; finishedAt?: string; durationMs?: number; executionMs?: number; operation?: string; origin?: 'model' | 'parent' | 'system' | 'unknown' }
export type ProcessTraceFocus = { modelId: string; revision: number }
export function callTraceIssues(models: readonly ProcessModelCall[], tools: readonly ProcessToolCall[], active = true) {
  return models.flatMap(model => {
    if (active && !model.settled && !models.some(next => next.sequenceId === model.sequenceId && next.number > model.number)) return []
    const missingToolIds = [...new Set(model.toolCallIds ?? [])].filter(id => {
      const tool = tools.find(item => item.id === id)
      return !tool || tool.status === 'running'
    })
    return missingToolIds.length ? [{ modelId: model.id, number: model.number, missingToolIds }] : []
  })
}
const count = (value: unknown) => typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : undefined
const tokens = (value: number | undefined) => value === undefined ? '—' : value.toLocaleString('zh-CN')
const time = (ms: number) => `${(ms / 1000).toFixed(1)}s`
const toolTime = (ms: number) => ms < 1000 ? `${Math.round(ms)}ms` : time(ms)
function CallGlyph({label,kind}:{label:string;kind:string}){
  const Icon=kind==='done'?Check:kind==='failed'?CircleX:kind==='running'?LoaderCircle:kind==='cancelled'?Square:kind==='warning'?AlertTriangle:CircleDashed
  return <span role="img" aria-label={label} title={label} className={`capstone-call-state is-${kind}`}><Icon aria-hidden="true"/></span>
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
  // Presentation only: remove a simple leading workspace change, never execute it.
  const action = name === 'bash' ? operation.replace(/^\s*cd\s+(?:'[^']*'|"[^"]*"|[^\s;&|]+)[ \t]*(?:&&|;|\r?\n)\s*/, '') : operation
  // Only a leading shell/script comment is intent metadata; never infer a result.
  const lines = action.split('\n')
  const first = lines[0]?.trim() ?? ''
  const comment = first.startsWith('#') && !first.startsWith('#!') ? first
    : /<<-?\s*['"]?[\w]+['"]?\s*$/.test(first) ? lines[1]?.trim() : undefined
  if (name === 'bash' && comment?.startsWith('#') && !comment.startsWith('#!')) {
    const text = comment.replace(/^#+\s*/, '').trim()
    if (text) return text.length > 120 ? text.slice(0, 120) + '…' : text
  }
  const compact = action.replace(/\s+/g, ' ').trim()
  return compact.length > 120 ? compact.slice(0, 120) + '…' : compact
}
export function modelCallMs(call: Omit<ProcessModelCall, 'id'>, now?: number): number {
  const start = Date.parse(call.startedAt ?? '')
  return call.startedAt && !call.finishedAt && now !== undefined && Number.isFinite(start) && now >= start ? now - start : call.ms
}

/** Neutral presentation: adapters supply admitted identities, never inferred causality. */
export default function ProcessCallTrace({ models, tools, now, active = true, compact = false, expandedTools = false, renderToolDetails, focusRequest }: {
  models: readonly ProcessModelCall[]; tools: readonly ProcessToolCall[]; now?: number; active?: boolean;
  renderToolDetails?: (tool: ProcessToolCall) => ReactNode;
  focusRequest?: ProcessTraceFocus;
  compact?: boolean;
  expandedTools?: boolean;
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
  const overlap = (tool: ProcessToolCall,other: ProcessToolCall) => {
    const owner=owners.get(tool.id),peer=owners.get(other.id)
    if(other.id===tool.id||owner?.length!==1||peer?.length!==1||owner[0]!==peer[0])return false
    const start=Date.parse(tool.startedAt??''),otherStart=Date.parse(other.startedAt??'')
    const duration=timed(tool).durationMs,otherDuration=timed(other).durationMs
    return duration!==undefined&&otherDuration!==undefined&&duration>0&&otherDuration>0&&
      Number.isFinite(start)&&Number.isFinite(otherStart)&&start<otherStart+otherDuration&&otherStart<start+duration
  }
  const overlaps = (tool: ProcessToolCall) => tools.some(other=>overlap(tool,other))
  const parallelGroups=(items:readonly ProcessToolCall[])=>{
    const groups:ProcessToolCall[][]=[]
    for(const tool of items){
      const matching=groups.filter(group=>group.some(other=>overlap(tool,other)))
      if(!matching.length){groups.push([tool]);continue}
      const first=matching[0];first.push(tool)
      for(const group of matching.slice(1)){first.push(...group);groups.splice(groups.indexOf(group),1)}
    }
    return groups
  }
  const latestModelId=models.at(-1)?.id
  const renderTool = (tool: ProcessToolCall, independent = false) => <details key={tool.id} className="capstone-call-tool" open={expandedTools||Boolean(compact&&active&&latestModelId&&owners.get(tool.id)?.length===1&&owners.get(tool.id)?.[0]===latestModelId)}>
    <summary><ChevronRight aria-hidden="true" /><strong title={tool.name}>{tool.name}</strong>
      {independent && <small>{tool.origin === 'system' ? '系统动作' : tool.origin === 'parent' ? '主链调用' : '未关联'}</small>}
      <span className="capstone-call-duration" data-latency={latencyGrade(tool.executionMs??timed(tool).durationMs,'tool').level} title={`${tool.executionMs === undefined ? '调用记录区间' : '工具执行耗时'} · ${latencyGrade(tool.executionMs??timed(tool).durationMs,'tool').label}`}>{tool.executionMs === undefined && timed(tool).durationMs === undefined ? '耗时未记录' : toolTime(tool.executionMs ?? timed(tool).durationMs!)}</span>
      {compact?<CallGlyph label={tool.status==='completed'?'完成':tool.status==='failed'?'失败':tool.status==='cancelled'?'已停止':active?'执行中':'未完整记录'} kind={tool.status==='completed'?'done':tool.status==='failed'?'failed':tool.status==='cancelled'?'cancelled':active?'running':'unknown'}/>:<span>{tool.status === 'completed' ? '完成' : tool.status === 'failed' ? '失败' : tool.status === 'cancelled' ? '已停止' : active ? '执行中' : '未完整记录'}</span>}
      {!compact&&overlaps(tool)&&<small title="同一 LLM 轮次中，实际调用记录的时间区间有重叠。">并行调用</small>}
    </summary>
    <div className="capstone-call-tool-detail">
      <p>工具执行 {tool.executionMs === undefined ? '—' : time(tool.executionMs)} · 记录区间 {tool.durationMs === undefined ? '—' : time(timed(tool).durationMs!)}</p>
      {independent && tool.origin !== 'system' && <p>{tool.origin === 'parent' ? '由主链发起，不属于本任务的 LLM 轮次。' : '记录未提供对应的 LLM 调用标识。'}</p>}
      {tool.operation && <p className="capstone-call-operation">{tool.operation}</p>}
      {renderToolDetails?.(tool)}
    </div>
  </details>
  const timestamp = (value?: string) => { const parsed = Date.parse(value ?? ''); return Number.isFinite(parsed) ? parsed : Infinity }
  const entries = [
    ...models.map(model => ({ id: `model:${model.id}`, at: model.startedAt ?? model.finishedAt, model, tool: undefined as ProcessToolCall | undefined })),
    ...tools.filter(tool => !models.some(model => owned(tool, model))).map(tool => ({ id: `tool:${tool.id}`, at: tool.startedAt, model: undefined as ProcessModelCall | undefined, tool })),
  ].sort((a, b) => timestamp(a.at) - timestamp(b.at))
  if (!entries.length) return <p>尚未收到调用记录。</p>
  return <ol className={`capstone-call-trace${compact?' is-compact':''}`} aria-label="模型与工具调用过程">{entries.map(entry => {
    if (entry.tool) return <li key={entry.id}>{renderTool(entry.tool, true)}</li>
    const model = entry.model!, selected = tools.filter(tool => owned(tool, model)), toolMs = toolExecutionMs(selected.map(timed))
    const pending = !!model.startedAt && !model.finishedAt, running = pending && active && !model.settled
    const grade=latencyGrade(pending&&(!active||model.settled)?undefined:modelCallMs(model,running?now:undefined),'model')
    const linked = model.toolCallIds !== undefined
    const issue = issues.find(item => item.modelId === model.id)
    const usage = model.usage, inputParts = [count(usage?.input), count(usage?.cacheRead), count(usage?.cacheWrite)]
    const input = inputParts.every(value => value !== undefined) ? inputParts.reduce<number>((sum, value) => sum + value!, 0) : undefined
    const requests = model.toolRequests ?? selected.map(tool => ({ id: tool.id, name: tool.name, operation: tool.operation }))
    return <li key={entry.id}><section role="group" aria-label={model.label ?? `LLM 调用 ${model.number}`} className="capstone-call-round" data-record-gap={issue ? true : undefined}
      tabIndex={-1} ref={element => { if (element) roundElements.current.set(model.id, element); else roundElements.current.delete(model.id) }}>
      <div className="capstone-call-model">{compact&&<span role="img" aria-label="LLM 调用" title="LLM 模型调用"><BrainCircuit className="capstone-call-model-icon" aria-hidden="true"/></span>}<strong title={`LLM 调用 ${model.number}`}>{model.label ?? `LLM ${String(model.number).padStart(2, '0')}`}</strong>
        <span className="capstone-call-duration" data-latency={grade.level} title={`LLM 响应 · ${grade.label}`}>{pending && (!active || model.settled) ? '耗时 —' : time(modelCallMs(model, running ? now : undefined))}</span>
        {model.intent&&<span className="capstone-call-purpose" title={model.intent}>{model.intent}</span>}
        {compact?<CallGlyph label={model.stopReason==='error'?'错误响应':model.stopReason==='aborted'?'已中断':running?'进行中':pending?'未完整记录':model.stopReason==='length'?'输出截断':'已返回'} kind={model.stopReason==='error'?'failed':model.stopReason==='aborted'?'cancelled':running?'running':pending?'unknown':model.stopReason==='length'?'warning':'done'}/>:model.stopReason === 'error' ? <span>错误响应</span> : model.stopReason === 'aborted' ? <span>已中断</span> : running ? <span role="status">进行中</span> : pending ? <span>未完整记录</span> : model.stopReason === 'length' ? <span>输出截断</span> : <span>已返回</span>}
        {model.stopReason==='error'&&model.errorCode&&Object.hasOwn(modelErrors,model.errorCode)&&<span>{modelErrors[model.errorCode]}{typeof model.errorStatus==='number'&&Number.isInteger(model.errorStatus)&&model.errorStatus>=400&&model.errorStatus<=599?` · HTTP ${model.errorStatus}`:''}</span>}
        {!compact&&!running && <small title={model.toolAssociation==='turn'?'依据同一 SDK 执行轮次中的实际工具调用记录归组。':undefined}>{!linked ? '工具关联未记录' : !model.toolCallIds!.length ? '未调用工具' : `${model.toolAssociation==='turn'?'本轮工具':'工具'} ${model.toolCallIds!.length}次${toolMs === undefined || model.toolAssociation==='turn' ? '' : ` · 活动区间 ${time(toolMs)}`}`}</small>}
      </div>
      {model.thinking&&<ThinkingProcess kind="call" storageKey={`model-thinking:${model.id}`} now={now} thinking={{text:model.thinking,startedAt:model.thinkingStartedAt,endedAt:running&&!model.thinkingSettled?undefined:model.thinkingEndedAt,handedOff:!running||model.thinkingSettled===true,phase:running&&!model.thinkingSettled?'running':'completed'}}/>}
      {usage && <div className="capstone-call-tokens" title="输入包含 SDK 单独报告的缓存读取/写入 token；未报告的值保持未知。">
        <span>输入 {tokens(input)}</span><span>输出 {tokens(count(usage.output))}</span>
        {count(usage.cacheRead) !== undefined && Number(usage.cacheRead) > 0 && <span>缓存 {tokens(count(usage.cacheRead))}</span>}<span>token</span>
      </div>}
      {!compact&&model.toolAssociation!=='turn'&&requests.length > 0 && <p className="capstone-call-intent" title={requests.map(item => `${item.name}${item.operation ? ' · ' + item.operation : ''}`).join('；')}>发起工具：{requests.map(item => `${item.name}${item.operation ? ' · ' + operationExcerpt(item.name, item.operation) : ''}`).join('；')}</p>}
      {model.responseText && <p className="capstone-call-response" title={model.responseText}>{model.responseText.length > 240 ? model.responseText.slice(0,240) + '…' : model.responseText}</p>}
      {issue && <div className="capstone-call-gap"><p role="status"><AlertTriangle aria-hidden="true" />工具记录缺失 · {issue.missingToolIds.length}项</p>
        <details><summary>缺失明细</summary><ul>{issue.missingToolIds.map(id => <li key={id}>
          <strong>{model.toolRequests?.find(item => item.id === id)?.name ?? '工具名称未记录'}</strong> · {tools.some(tool => tool.id === id) ? '缺少结果记录' : '缺少执行记录'}<code>{id}</code>
        </li>)}</ul></details></div>}
      {selected.length > 0 && <div className="capstone-call-batch" aria-label="本轮工具调用">{compact?parallelGroups(selected).map(group=>group.length>1?<div key={group[0].id} className="capstone-parallel-group" role="group" aria-label={`并行工具调用 · ${group.length} 项`} title="这些调用属于同一轮，实际执行区间存在重叠。">{group.map(tool=>renderTool(tool))}</div>:renderTool(group[0])):selected.map(tool=>renderTool(tool))}</div>}
      {!issue && linked && model.toolCallIds!.length > selected.length && <p className="capstone-call-pending">等待工具记录 · {model.toolCallIds!.length - selected.length}项</p>}
    </section></li>
  })}</ol>
}
