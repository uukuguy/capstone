import ProcessStepRecord, { type ProcessFoldCommand } from './ProcessStepRecord'
import ProcessCallTrace, { type ProcessModelCall, type ProcessToolCall } from './ProcessCallTrace'
import { toolExecutionMs } from './processTiming'

/** A measured process boundary, not a task submitted to an execution scheduler. */
export default function ProcessLifecycleNode({ kind, storageKey, startedAt, endedAt, now, active, models = [], tools = [], expanded = false, foldCommand }: {
  kind: 'startup' | 'finalization'; storageKey: string; startedAt?: number; endedAt?: number; now?: number; active: boolean;
  models?: ProcessModelCall[]; tools?: ProcessToolCall[]; expanded?: boolean; foldCommand?: ProcessFoldCommand;
}) {
  const title=kind==='startup'?'任务启动':'任务收尾'
  const end=active?now:endedAt
  const elapsed=startedAt!==undefined&&end!==undefined&&Number.isFinite(startedAt)&&Number.isFinite(end)?Math.max(0,end-startedAt):undefined
  const time=(ms:number)=>`${(ms/1000).toFixed(1)}s`
  const pending=models.find(call=>!call.finishedAt)
  const summary=active?(pending?'主链模型处理中。':kind==='startup'?'正在准备输入、规划和调度首个任务。':'正在接收结果、整理交付和生成回答。'):
    kind==='startup'?'首个任务已启动。':'主链处理已结束。'
  const toolMs=toolExecutionMs(tools)
  return <section className="capstone-graph-node capstone-process-lifecycle" role="region" aria-label={title}>
    <ProcessStepRecord id={`lifecycle:${kind}`} title={title} storageKey={storageKey} defaultExpanded={expanded} foldCommand={foldCommand}
      resultSummary={summary} headingClassName="capstone-graph-node-heading" heading={<>
        <span className="capstone-step-number" aria-label="系统阶段">{kind==='startup'?'启动':'收尾'}</span><strong>{title}</strong>
        <span className="capstone-graph-heading-metrics"><span>{active?'已用时':'总耗时'} {elapsed===undefined?'—':time(elapsed)}</span>
          <span>LLM {models.length}次 / {time(models.reduce((sum,call)=>sum+call.ms,0))}</span>
          <span>工具 {tools.length}次 / {toolMs===undefined?'—':time(toolMs)}</span>
          {active&&pending&&now!==undefined&&<span>本次请求 {time(Math.max(0,now-Date.parse(pending.startedAt??'')))}</span>}
        </span><span className="capstone-process-status">{active?(pending?'模型处理中':'处理中'):'完成'}</span>
      </>}>
      <p>{summary}</p><ProcessCallTrace models={models} tools={tools} now={now} active={active} />
    </ProcessStepRecord>
  </section>
}
