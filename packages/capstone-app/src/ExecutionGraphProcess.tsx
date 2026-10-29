import { useEffect, useId, useState } from 'react'
import { AlertTriangle } from 'lucide-react'
import type { ExecutionGraph, GraphExecution, GraphNode, GraphResult, GraphParentResponse, GraphTool } from './executionGraph'
import { RecordedResult, readStepOpen, saveStepOpen, toolExecutionMs, type StepFoldCommand } from './TaskStepProcess'
import ProcessStepRecord, { ProcessDetailGroup, ProcessFoldControls } from './ProcessStepRecord'
import ProcessLifecycleNode from './ProcessLifecycleNode'
import ProcessCallTrace, { callTraceIssues, modelCallMs, type ProcessTraceFocus, type ProcessToolCall } from './ProcessCallTrace'
import './taskStepProcess.css'

const phaseLabels: Record<string, string> = { pending: '等待', ready: '可执行', executing: '执行中', executed: '已返回', recorded: '待检查', assessing: '检查中', success: '完成', limited: '受限', failure: '失败' }
const nativeLabels: Record<string, string> = { completed: '原生执行完成', failed: '原生执行失败', cancelled: '原生执行已取消', unknown: '原生结束状态未知' }
const waitLabels: Record<string, string> = { dependencies: '前置结果尚未通过评估', model_revision_required: '需要模型修订' }
const reasonLabels: Record<string, string> = { source_changed: '来源变化', method_changed: '方法变化', missing_result: '结果缺失', discrepancy: '发现矛盾' }
const time = (ms: number) => `${(ms / 1000).toFixed(1)}s`
const timedTools = (tools: readonly ProcessToolCall[], now?: number) => tools.map(tool => tool.status === 'running' && now !== undefined && tool.startedAt && Number.isFinite(Date.parse(tool.startedAt)) && now >= Date.parse(tool.startedAt)
  ? { ...tool, durationMs: now - Date.parse(tool.startedAt) } : tool)

function ResultVersion({ result }: { result: GraphResult }) {
  return <details className="capstone-graph-result-version"><summary>结果诊断</summary>
    <dl><dt>结果引用</dt><dd><code>{result.result_ref}</code></dd><dt>生产者 / 输出槽</dt><dd>{result.producer.step_id} / {result.slot} · 执行 v{result.producer.execution_revision} · {result.kind}</dd>
      <dt>生产行动</dt><dd><code>{result.producer.action_id}</code></dd><dt>覆盖范围</dt><dd>{result.scope}</dd>
      <dt>实际消费结果</dt><dd>{result.consumed_results.length ? result.consumed_results.map(ref => <code key={ref}>{ref}</code>) : '未消费其他结果'}</dd>
      <dt>来源版本</dt><dd>{result.source_versions.length ? result.source_versions.map(v => <code key={v.ref}>{v.ref} · {v.revision ?? '版本未知'}</code>) : '未记录'}</dd>
      <dt>方法版本</dt><dd>{result.method.ref ? <code>{result.method.ref} · {result.method.revision ?? '版本未知'}</code> : result.method.unavailable ?? '未记录'}{Object.entries(result.method).filter(([key]) => !['ref', 'revision', 'unavailable'].includes(key)).map(([key, value]) => <code key={key}>{key}: {value}</code>)}</dd>
      {result.supersedes.length > 0 && <><dt>替代版本</dt><dd>{result.supersedes.map(ref => <code key={ref}>{ref}</code>)}</dd></>}
      {result.recompute_reason && <><dt>重算原因</dt><dd>{reasonLabels[result.recompute_reason.kind] ?? result.recompute_reason.kind}{result.recompute_reason.diagnostic && <p>{result.recompute_reason.diagnostic}</p>}{result.recompute_reason.refs.map(ref => <code key={ref}>{ref}</code>)}</dd></>}
    </dl>
  </details>
}

function HandoffStatus({execution,nodePhase,now,interrupted}:{execution?:GraphExecution;nodePhase:string;now?:number;interrupted:boolean}){
  const calls=execution?.tools.filter(tool=>tool.name==='agent_task_return')??[]
  if(!calls.length)return null
  const latest=calls.at(-1)!,failures=calls.filter(tool=>tool.status==='failed')
  const running=!interrupted&&!execution?.nativeStatus&&latest.status==='running'
  const start=Date.parse(calls[0].startedAt??''),end=running?now:Date.parse(latest.finishedAt??'')
  const duration=Number.isFinite(start)&&end!==undefined&&Number.isFinite(end)?Math.max(0,end-start):undefined
  const registered=['success','limited','failure'].includes(nodePhase)
  const savedLabel=registered?`结果已登记${nodePhase==='limited'?' · 含限制':nodePhase==='failure'?' · 失败结果':''}`:'返回已保存 · 待接收'
  return <div className="capstone-graph-metrics" aria-label="结果交接状态">
    <span title="提交时长仅包含子任务返回调用及其重试；系统登记和主流程处理由实际任务状态单独表示。">{running?'提交返回中':latest.status==='completed'?savedLabel:interrupted?'结果提交已停止':'结果提交未完成'}{duration!==undefined?` · ${running?'已用时':'返回提交区间'} ${time(duration)}`:''}</span>
    {failures.length>0&&<span>交接失败 {failures.length} 次{latest.status==='completed'?' · 后续返回已保存':''}</span>}
    {failures.at(-1)?.output&&<span>{failures.at(-1)!.output}</span>}
    {!!latest.returnLimitations?.count&&<details><summary>已记录 {latest.returnLimitations.count} 项限制，结果保留</summary><ul>{latest.returnLimitations.notes.map((note,index)=><li key={index}>{note}</li>)}</ul></details>}
  </div>
}

export type GraphTraceFocus = ProcessTraceFocus & { nodeId: string }
export function graphTraceIssues(graph: ExecutionGraph, attemptPhase?: string) {
  const active = !['completed', 'failed', 'cancelled', 'interrupted'].includes(attemptPhase ?? '')
  return graph.current.nodes.flatMap(node => {
    const execution = graph.executions.find(item => item.action.id === node.execute_action_id)
    return execution ? callTraceIssues(execution.responses.map(response => ({ ...response, id: `${execution.action.id}:response:${response.number}` })), execution.tools, active && !execution.nativeStatus).map(issue => ({ ...issue, nodeId: node.id })) : []
  })
}

function ExecutionTools({ execution, storageKey, inline = false, now, active = true, focusRequest }: { execution: GraphExecution; storageKey: string; inline?: boolean; now?: number; active?: boolean; focusRequest?: ProcessTraceFocus }) {
  const key = `graph:${execution.action.id}`
  const [open, setOpen] = useState(() => readStepOpen(storageKey, key))
  const ms = toolExecutionMs(execution.tools)
  const content = <ProcessCallTrace models={execution.responses.map(response => ({ ...response, id: `${execution.action.id}:response:${response.number}` }))}
    tools={execution.tools} now={now} focusRequest={focusRequest} active={active && !execution.nativeStatus} renderToolDetails={item => {
      const tool=execution.tools.find(value => value.id === item.id)!
      return <>{tool.output && <RecordedResult text={tool.output} title={`${execution.node.purpose} · ${tool.name}`} />}
        <details><summary>调用标识</summary><code>{tool.id}</code><span>{tool.actionKind === 'assess' ? '评估行动' : '执行行动'}</span><code>{tool.actionId ?? execution.action.id}</code></details></>
    }} />
  return inline ? content : <details className="capstone-graph-tools" open={open} onToggle={event => {
    const value = event.currentTarget.open; setOpen(value); saveStepOpen(storageKey, key, value)
  }}><summary>调用过程 · LLM {execution.responses.length}次 · 工具 {execution.tools.length}次{ms === undefined ? '' : ` · 活动区间 ${time(ms)}`}</summary>{content}</details>
}

function ExecutionMetrics({ node, execution, parentResponses = [], now }: { node: GraphNode; execution?: GraphExecution; parentResponses?: readonly GraphParentResponse[]; now?: number }) {
  if (!execution && !node.execute_action_id) return null
  const responses = (execution?.responses ?? []).map(response => ({ ...response, ms:modelCallMs(response, execution?.nativeStatus ? undefined : now) }))
  const tools = timedTools(execution?.tools ?? [], now), toolMs = toolExecutionMs(tools)
  const liveMs = now !== undefined && execution?.executionStartedAt && !execution.executionFinishedAt && now >= Date.parse(execution.executionStartedAt)
    ? now - Date.parse(execution.executionStartedAt) : undefined
  const intervalEnd = execution?.executionFinishedAt ? Date.parse(execution.executionFinishedAt) : now
  const intervalResponses = node.execution === 'parent' && execution?.executionStartedAt && intervalEnd !== undefined
    ? parentResponses.filter(r => Date.parse(r.startedAt) >= Date.parse(execution.executionStartedAt!) && Date.parse(r.finishedAt) <= intervalEnd) : []
  const duration = execution?.executionIntervalMs ?? execution?.durationMs ?? liveMs
  const llm = responses.length ? responses : intervalResponses
  return <div className="capstone-graph-metrics capstone-graph-heading-metrics">
    <span title="从步骤启动到执行返回；包含等待">{duration === undefined ? '耗时 —' : time(duration)}</span>
    {execution && <span title="实际工具调用数量及调用区间并集；执行中区间更新至当前时间，并行区间只计一次，不是 CPU 时间。—表示未完整记录">工具 {tools.length}次 / {toolMs === undefined ? '—' : time(toolMs)}</span>}
    <span title={node.execution === 'parent' ? '本步骤执行区间内的主流程请求，含网络与 Provider 等待；不是节点独占用量' : '模型请求累计时长，含 Provider 等待；进行中的请求按当前活动区间更新，不含工具执行'}>{llm.length ? `LLM ${llm.length}次 / ${time(llm.reduce((sum, r) => sum + r.ms, 0))}` : 'LLM —'}</span>
  </div>
}

function InputBindings({ node, results }: { node: GraphNode; results: readonly GraphResult[] }) {
  if (!node.input_bindings.length) return null
  return <details className="capstone-graph-inputs"><summary>实际消费版本 · {node.input_bindings.length} 项</summary><small>保留实际消费版本，不自动切换至最新结果。</small>{node.input_bindings.map(binding => <div key={binding.input_name ?? binding.result_ref}><span>{binding.input_name} · {binding.producer_step_id} / {binding.slot}</span><code>{binding.result_ref}</code>{results.some(r => r.supersedes.includes(binding.result_ref)) && <p>已有替代版本；此消费者仍绑定上述旧版本。</p>}</div>)}</details>
}

function SourceScope({ node, execution }: { node: GraphNode; execution?: GraphExecution }) {
  const refs = execution ? execution.action.source_refs : node.source_refs
  const versions = execution ? execution.action.source_versions : node.selected_source_versions
  if (refs === undefined) return <small>未记录原始资料范围</small>
  if (!refs.length) return <small>未绑定原始资料</small>
  return <details className="capstone-graph-inputs"><summary>绑定原始资料 · {refs.length} 项</summary>{refs.map(ref => <div key={ref}><code>{ref}</code><code>{versions?.find(v => v.ref === ref)?.revision ?? '版本未提供'}</code></div>)}</details>
}

function ParallelMetrics({ nodes, executions, now }: { nodes: GraphNode[]; executions: GraphExecution[]; now?: number }) {
  const selected = nodes.map(node => executions.find(e => e.action.id === node.execute_action_id))
  const starts = selected.map(e => Date.parse(e?.executionStartedAt ?? ''))
  const ends = selected.map(e => Date.parse(e?.executionFinishedAt ?? ''))
  const started = starts.filter(Number.isFinite)
  const live = now !== undefined && selected.some(e => e?.executionStartedAt && !e.executionFinishedAt)
  const start = Math.min(...started)
  const end = live ? now : Math.max(...ends)
  const complete = live || starts.every(Number.isFinite) && ends.every(Number.isFinite)
  const ms = complete && Number.isFinite(start) && Number.isFinite(end) && end >= start ? end - start : undefined
  const tools = timedTools(selected.flatMap(e => e?.tools ?? []), now), toolMs = toolExecutionMs(tools)
  const responses = selected.flatMap(e => (e?.responses ?? []).map(response => ({ ...response, ms:modelCallMs(response, e?.nativeStatus ? undefined : now) })))
  if (nodes.every(node => !node.execute_action_id)) return <span>尚未启动</span>
  return <>
    <span title="最早分支启动至最后分支结束的实际时间跨度，不累加各分支；未完整记录时显示 —。不含前置准备和后续汇总。">{live ? '已用时' : '总耗时'} {ms === undefined ? '—' : time(ms)}</span>
    <span title="本组当前执行的实际工具调用次数及调用区间并集，并行区间只计一次；不是 CPU 时间。">工具 {tools.length}次 / {toolMs === undefined ? '—' : time(toolMs)}</span>
    <span title="各分支已完成模型请求的次数和累计时长，含 Provider 等待；并行请求时长会累加，与总耗时不同。">LLM {responses.length ? `${responses.length}次 / ${time(responses.reduce((sum, r) => sum + r.ms, 0))}` : '—'}</span>
  </>
}

/** Present the model's actual task steps. Keep graph implementation details in diagnostics. */
export default function ExecutionGraphProcess({ graph, storageKey, attemptPhase, expandedResearch = false, foldCommand, onFoldChange, now, showFoldControls = true, traceFocus, overallTools = [], attemptStartedAt, attemptDurationMs }: { graph: ExecutionGraph; storageKey: string; attemptPhase?: string; expandedResearch?: boolean; foldCommand?: StepFoldCommand; onFoldChange?: (id: string, open: boolean) => void; now?: number; showFoldControls?: boolean; traceFocus?: GraphTraceFocus; overallTools?: ProcessToolCall[]; attemptStartedAt?: string; attemptDurationMs?: number }) {
  const prefix = useId()
  const [localFold, setLocalFold] = useState<StepFoldCommand>()
  const [showPlan, setShowPlan] = useState(false)
  const [focus, setFocus] = useState<(GraphTraceFocus & { command: StepFoldCommand })>()
  useEffect(() => { setFocus(undefined) }, [foldCommand, localFold])
  useEffect(() => { if (traceFocus) setFocus({ ...traceFocus, command: { open: true, revision: traceFocus.revision } }) }, [traceFocus])
  const issues = graphTraceIssues(graph, attemptPhase)
  const current = graph.current
  const displayedNodes = showPlan ? current.nodes : current.nodes.filter(node => node.execute_action_id)
  const anchor = (id: string) => `${prefix}-graph-${id}`
  const byId = new Map(current.nodes.map(n => [n.id, n]))
  const interruption = attemptPhase === 'cancelled' ? '任务已取消' : attemptPhase === 'failed' ? '任务执行失败' : attemptPhase === 'interrupted' ? '任务已中断' : attemptPhase === 'completed' ? '本轮已结束 · 此步骤未完成' : undefined
  const parentResponses = graph.parentResponses ?? []
  const errors = parentResponses.filter(r => r.kind === 'error')
  const modelCalls = [
    ...parentResponses.map((response,index)=>({...response,sequenceId:'parent',number:index+1,label:`主链 · LLM ${String(index+1).padStart(2,'0')}`})),
    ...(graph.parentPendingResponse && !interruption ? [{...graph.parentPendingResponse,ms:now===undefined?0:Math.max(0,now-Date.parse(graph.parentPendingResponse.startedAt)),sequenceId:'parent',number:parentResponses.length+1,label:`主链 · LLM ${String(parentResponses.length+1).padStart(2,'0')}`}] : []),
    ...graph.executions.flatMap(execution=>execution.responses.map(response=>({...response,
      id:`${execution.action.id}:response:${response.number}`,sequenceId:execution.action.id,settled:!!execution.nativeStatus,label:`任务 ${String(current.nodes.findIndex(node=>node.id===execution.node.id)+1).padStart(2,'0')} · LLM ${String(response.number).padStart(2,'0')}`,
      ms:modelCallMs(response,interruption||execution.nativeStatus?undefined:now)}))),
  ]
  const allTools = [...new Map([...overallTools,...graph.executions.flatMap(execution=>execution.tools)].map(tool=>[tool.id,tool])).values()]
  const totalToolMs = toolExecutionMs(timedTools(allTools,interruption?undefined:now))
  const currentExecutions=current.nodes.flatMap(node=>graph.executions.filter(e=>e.action.id===node.execute_action_id))
  const firstStart=Math.min(...currentExecutions.map(e=>Date.parse(e.executionStartedAt??e.startedAt??'')))
  const allReturned=current.nodes.length>0 && currentExecutions.length===current.nodes.length && currentExecutions.every(e=>!!e.nativeStatus && !!(e.executionFinishedAt??e.finishedAt))
  const lastEnd=allReturned?Math.max(...currentExecutions.map(e=>Date.parse(e.executionFinishedAt??e.finishedAt??''))):undefined
  const attemptStart=Date.parse(attemptStartedAt??'')
  const finalEnd=Number.isFinite(attemptStart)&&attemptDurationMs!==undefined?attemptStart+attemptDurationMs:Math.max(...parentResponses.map(r=>Date.parse(r.finishedAt)))
  const tailEnd=interruption?finalEnd:now
  const tailCalls=lastEnd===undefined?[]:modelCalls.filter(call=>call.sequenceId==='parent' && Date.parse(call.startedAt??'')>=lastEnd)
  const tailTools=lastEnd===undefined?[]:overallTools.filter(tool=>Date.parse(tool.startedAt??'')>=lastEnd)
  const startupEnd=Number.isFinite(firstStart)?firstStart:undefined
  const startupCalls=modelCalls.filter(call=>call.sequenceId==='parent' && (startupEnd===undefined||Date.parse(call.startedAt??'')<startupEnd))
  const startupTools=overallTools.filter(tool=>startupEnd===undefined||Date.parse(tool.startedAt??'')<startupEnd)
  // A temporarily empty incremental pool is not whole-goal finalization.
  const finalizing=allReturned && (!!interruption || tailTools.some(tool=>/(?:^| · )agent_research_(?:assess|finish)$/.test(tool.name)))

  return <div className="capstone-execution-graph" aria-label="任务步骤">
    <div className="capstone-graph-metrics" aria-label="本轮整体计量">
      <strong title="主链与全部任务模型请求累计；并行时区间重叠，不等于墙钟总耗时">LLM 总计 {modelCalls.length}次 / {time(modelCalls.reduce((sum,call)=>sum+call.ms,0))}</strong>
      <span title="按调用标识去重；时间是活动区间并集，包含等待，不是CPU时间">工具总计 {allTools.length}次 / 活动区间 {totalToolMs===undefined?'—':time(totalToolMs)}</span>
    </div>
    <details className="capstone-graph-history"><summary>全轮调用时间线 · 主链与任务</summary>
      <ProcessCallTrace models={modelCalls} tools={allTools} active={!interruption} now={now} />
    </details>
    <div className="capstone-graph-metrics" aria-label="本轮模型计时">
      <span>{parentResponses.length ? `本轮主流程 LLM ${parentResponses.length}次 / ${time(parentResponses.reduce((sum, r) => sum + r.ms, 0))}` : '本轮主流程 LLM 计时未记录'}</span>
      {errors.length > 0 && <span>错误响应 {errors.length}次 / {time(errors.reduce((sum, r) => sum + r.ms, 0))}</span>}
    </div>
    {parentResponses.length > 0 && <details className="capstone-graph-history"><summary>LLM 请求计时明细</summary><ol>{parentResponses.map((r, index) => <li key={r.id}>请求 {index + 1} · {r.kind === 'error' ? '错误响应' : r.kind === 'tools' ? '工具请求' : '文字回答'} · {time(r.ms)}</li>)}</ol></details>}
    <div className="capstone-graph-heading"><strong>{showPlan ? '完整计划' : '任务步骤'} · {displayedNodes.length} 项</strong><button type="button" className="capstone-process-plan-toggle" aria-label={showPlan ? '返回执行记录' : '查看完整计划'} aria-pressed={showPlan} onClick={() => setShowPlan(value => !value)}>{showPlan ? '返回执行记录' : `完整计划 · ${current.nodes.length} 项`}</button>{showFoldControls && <ProcessFoldControls onChange={open => setLocalFold(previous => ({ open, revision: (previous?.revision ?? 0) + 1 }))} />}<details><summary>执行诊断</summary><p>执行图 · v{current.graph_revision}</p><code>{current.graph_ref}</code></details></div>
    {!displayedNodes.length && <p className="capstone-graph-caption">计划已生成，等待执行启动。</p>}
    <ProcessLifecycleNode kind="startup" storageKey={storageKey} startedAt={Number.isFinite(attemptStart)?attemptStart:undefined}
      endedAt={startupEnd} now={now} active={startupEnd===undefined&&!interruption} models={startupCalls} tools={startupTools}
      expanded={expandedResearch} foldCommand={foldCommand??localFold} />
    <div className="capstone-graph-records">{(() => {
      // Matching prerequisites describe eligibility, not observed concurrency.
      // Group only adjacent siblings whose actual execution intervals overlap.
      const groups: GraphNode[][] = []
      const interval = (node: GraphNode) => {
        const execution = graph.executions.find(item => item.action.id === node.execute_action_id)
        const start = Date.parse(execution?.executionStartedAt ?? '')
        const end = execution?.executionFinishedAt ? Date.parse(execution.executionFinishedAt)
          : !interruption && !execution?.nativeStatus ? now : undefined
        return Number.isFinite(start) && end !== undefined && Number.isFinite(end) && end > start ? { start, end } : undefined
      }
      for (const node of displayedNodes) {
        const previous = groups.at(-1)
        const key = (item: GraphNode) => JSON.stringify([...item.depends_on].sort())
        const currentInterval = interval(node)
        const overlaps = currentInterval && previous?.some(item => {
          const other = interval(item)
          return other && Math.max(currentInterval.start, other.start) < Math.min(currentInterval.end, other.end)
        })
        if (node.execution === 'delegated' && previous?.[0].execution === 'delegated' && key(previous[0]) === key(node) && overlaps) previous.push(node)
        else groups.push([node])
      }
      return groups.map(nodes => {
        const live = !interruption && now !== undefined ? nodes.filter(node => graph.executions.some(e => e.action.id === node.execute_action_id && e.executionStartedAt && Date.parse(e.executionStartedAt) <= now && !e.executionFinishedAt)).length : 0
        return <div key={nodes[0].id} className={nodes.length > 1 ? 'capstone-graph-parallel' : undefined} role={nodes.length > 1 ? 'group' : undefined} aria-label={nodes.length > 1 ? `并行任务 · ${nodes.length} 项` : undefined}>
          {nodes.length > 1 && <div className="capstone-graph-parallel-heading"><span>并行任务 · {nodes.length} 项</span><ParallelMetrics nodes={nodes} executions={graph.executions} now={interruption ? undefined : now} />{live > 1 && <span className="capstone-graph-parallel-live" role="status">正在同时执行 {live} 项</span>}</div>}
          {nodes.map(node => {
      const index = current.nodes.indexOf(node)
      const execution = graph.executions.find(e => e.action.id === node.execute_action_id)
      const prior = graph.executions.filter(e => e.action.step_id === node.id && e.action.id !== node.execute_action_id)
      const results = node.output_bindings.flatMap(binding => current.results.filter(r => r.result_ref === binding.result_ref))
      const interrupted = interruption && !['success', 'limited', 'failure'].includes(node.phase)
      const interruptedLabel = execution?.nativeStatus === 'cancelled' ? '已取消' : execution?.nativeStatus === 'failed' ? '失败' : attemptPhase === 'cancelled' ? '已取消' : attemptPhase === 'completed' ? node.execute_action_id ? '未完成' : '未执行' : attemptPhase === 'failed' ? '失败' : '已中断'
      return <section key={node.id} id={anchor(node.id)} tabIndex={-1} data-step-id={node.id} className="capstone-graph-node" role="region" aria-label={node.purpose} data-phase={node.applicability === 'stale' ? 'stale' : node.phase}>
        <ProcessStepRecord id={node.id} title={node.purpose} storageKey={storageKey} resultSummary={results.map(result => result.summary).join('；') || execution?.resultSummary} defaultExpanded={expandedResearch} foldCommand={focus?.nodeId === node.id ? focus.command : foldCommand ?? localFold} onFoldChange={onFoldChange} headingClassName="capstone-graph-node-heading" heading={<><span className="capstone-step-number">{String(index + 1).padStart(2, '0')}</span><strong>{node.purpose}</strong><ExecutionMetrics node={node} execution={execution} parentResponses={parentResponses} now={interruption ? undefined : now} />{issues.some(issue => issue.nodeId === node.id) && <button type="button" className="capstone-process-trace-warning" aria-label="定位本任务的工具记录缺失" onClick={() => { const issue = issues.find(item => item.nodeId === node.id)!; setFocus({ ...issue, revision: (focus?.revision ?? 0) + 1, command: { open: true, revision: (focus?.revision ?? 0) + 1 } }) }}><AlertTriangle aria-hidden="true" />工具记录缺失 · {issues.filter(issue => issue.nodeId === node.id).reduce((sum, issue) => sum + issue.missingToolIds.length, 0)}项</button>}<span className="capstone-process-status" data-attempt-interruption={interrupted ? attemptPhase : undefined}>{interrupted ? interruptedLabel : node.applicability === 'stale' ? '已过期' : node.blocked_by.length ? '等待' : phaseLabels[node.phase]}</span></>}>
        <ProcessDetailGroup id={`${node.id}:result`} title="执行结果" storageKey={storageKey} defaultExpanded>
          {results.map(result => <div key={result.result_ref} className="capstone-graph-output"><RecordedResult text={result.summary} title={`${node.purpose} · ${result.slot}`} /></div>)}
          {!results.length && <>{execution?.resultSummary ? <RecordedResult text={execution.resultSummary} title={node.purpose} /> : <p>尚未返回结果。</p>}</>}
        </ProcessDetailGroup>
        <ProcessDetailGroup id={`${node.id}:task`} title="任务说明" storageKey={storageKey} defaultExpanded><h4>任务问题</h4><ul>{node.questions.map(question => <li key={question}>{question}</li>)}</ul><h4>预期产出</h4><ul>{node.expected_outputs.map(output => <li key={output}>{output}</li>)}</ul><h4>检查要求</h4><ul>{node.checks.map(check => <li key={check}>{check}</li>)}</ul></ProcessDetailGroup>
        <ProcessDetailGroup id={`${node.id}:execution`} title="调用过程" storageKey={storageKey} foldCommand={focus?.nodeId === node.id ? focus.command : undefined}>
        {node.depends_on.length > 0 && <nav className="capstone-graph-dependencies" aria-label={`${node.purpose} 的前置步骤`}>前置步骤：{node.depends_on.map(dep => <a key={dep} href={`#${anchor(dep)}`} aria-label={`前置步骤：${node.purpose} 依赖 ${byId.get(dep)!.purpose}`}>{byId.get(dep)!.purpose}</a>)}</nav>}
        {node.blocked_by.length > 0 && <p className="capstone-graph-wait">等待 {node.blocked_by.map(dep => byId.get(dep)!.purpose).join('、')} 完成</p>}
        {node.wait_reason && <p className="capstone-graph-wait">{waitLabels[node.wait_reason] ?? node.wait_reason}</p>}
        {execution && <ExecutionTools execution={execution} storageKey={storageKey} now={interruption ? undefined : now} active={!interruption} focusRequest={focus?.nodeId === node.id ? focus : undefined} inline />}
        </ProcessDetailGroup>
        <ProcessDetailGroup id={`${node.id}:diagnostics`} title="诊断信息" storageKey={storageKey} className="capstone-process-diagnostics"><details><summary>执行指令</summary><p>{node.instruction}</p></details><code>{node.id}</code><p>执行 v{node.execution_revision} · 图状态：{phaseLabels[node.phase]}</p>{interrupted && <p>{interruption} · 最后步骤状态：{phaseLabels[node.phase]}</p>}<p>{nativeLabels[execution?.nativeStatus ?? node.settled_status ?? ''] ?? '原生结束状态未记录'}</p>{node.execution === 'parent' && <p>父主流程共享模型，未提供按节点计量</p>}<p>LLM为已完成请求区间，含网络与Provider等待。工具时长为调用区间并集，不是CPU时间。</p>
        {results.map(result => <ResultVersion key={result.result_ref} result={result} />)}
        <InputBindings node={node} results={current.results} />
        <SourceScope node={node} execution={execution} />
        {prior.length > 0 && <details className="capstone-graph-history"><summary>本步骤历史执行 · {prior.length}</summary>{prior.map(old => <section key={old.action.id}><strong>执行 v{old.action.execution_revision} · {phaseLabels[old.node.phase]}</strong><code>{old.action.id}</code><ExecutionMetrics node={old.node} execution={old} /><InputBindings node={old.node} results={current.results} /><SourceScope node={old.node} execution={old} /><ExecutionTools execution={old} storageKey={storageKey} /></section>)}</details>}
        </ProcessDetailGroup>
        </ProcessStepRecord>
        <HandoffStatus execution={execution} nodePhase={node.phase} now={now} interrupted={!!interruption}/>
      </section>
          })}
        </div>
      })
    })()}</div>
    {allReturned&&!finalizing&&<p className="capstone-graph-metrics" role="status">主链编排 · 接收结果并判断下一步{lastEnd!==undefined&&now!==undefined?` · 已用时 ${time(Math.max(0,now-lastEnd))}`:''}</p>}
    {finalizing&&lastEnd!==undefined && Number.isFinite(lastEnd) && <ProcessLifecycleNode kind="finalization" storageKey={storageKey}
      startedAt={lastEnd} endedAt={tailEnd} now={now} active={!interruption} models={tailCalls} tools={tailTools}
      expanded={expandedResearch} foldCommand={foldCommand??localFold} />}
    <details className="capstone-graph-history"><summary>图修订与控制记录 · {graph.revisions.length} 个版本</summary>
      {graph.revisions.map(revision => <section key={revision.graph.graph_ref}><strong>图 v{revision.graph.graph_revision}</strong><code>{revision.graph.graph_ref}</code><p>{revision.graph.model_revision_reason ?? '模型初次声明'}</p><ul>{revision.graph.nodes.map(n => <li key={n.id}><code>{n.id}</code> {n.purpose}{n.depends_on.length ? ` · 依赖 ${n.depends_on.join('、')}` : ' · 无前置依赖'}</li>)}</ul></section>)}
      {graph.controlEvents.map(control => <p key={control.id}>{control.kind === 'graph_delivery_committed' ? '模型提交交付' : '模型提交执行图'} · <code>{control.graphRef}</code> · 检查点 v{control.checkpoint.revision}{control.summary && <span> · {control.summary}</span>}</p>)}
      <small>仅保留已收到的公开图版本；模型响应不作为业务步骤。</small>
    </details>
    {current.results.some(r => !current.nodes.some(n => n.output_bindings.some(b => b.result_ref === r.result_ref))) && <details className="capstone-graph-history"><summary>保留的结果版本</summary>{current.results.filter(r => !current.nodes.some(n => n.output_bindings.some(b => b.result_ref === r.result_ref))).map(r => <ResultVersion key={r.result_ref} result={r} />)}</details>}
  </div>
}
