import { useEffect, useRef, useState } from 'react'
import { ApiError, CapstoneClient } from './api'
import { runAutomaticSession } from './autoRun'
import { commandKey } from './commandKey'
import { NetworkView } from './NetworkView'
import { parseNetworkDiagram } from './networkValidation'
import { ensureCreateKey, forgetRun, readRun, readSelection,
  rememberSelection, rememberSession } from './sessionMemory'
import type { ApplicationCard, CaseCard, Catalog, CommittedTurn, NetworkDiagram,
  NetworkStory, NetworkView as NetworkViewData, SessionStatus } from './types'

type Selection = { applicationId: string; caseId: string }
type DetailTab = 'overview' | 'evidence'
type Props = { clientFactory?: (token: string) => CapstoneClient }
const defaultClientFactory = (token: string) => new CapstoneClient(import.meta.env.VITE_API_ORIGIN || '', token)

const stateLabel: Record<SessionStatus['state'], string> = {
  pending: '等待工作进程', ready: '等待指令', executing: '分析中', closing: '整理结果中',
  completed: '已完成', failed: '运行失败', interrupted: '运行中断',
}

function statusText(status: SessionStatus | null): string {
  if (!status) return '尚未开始'
  if (status.error_code === 'session_idle_timeout') return '会话已超时'
  if (status.error_code === 'session_capacity_evicted') return '空闲会话已让位'
  return stateLabel[status.state]
}

function formatDuration(durationMs: number): string {
  const seconds = Math.max(0, durationMs) / 1000
  if (seconds < 60) return `${seconds < 10 ? seconds.toFixed(1) : Math.round(seconds)} 秒`
  const minutes = Math.floor(seconds / 60)
  const remainder = Math.round(seconds % 60)
  return `${minutes} 分 ${String(remainder).padStart(2, '0')} 秒`
}

function isLongCaseFact(value: string): boolean {
  return value.length > 18
}

// Step-to-network projection is intentionally disabled until its contract is
// validated independently. The case diagram remains available as a static
// preview while answers and reports continue to use the real run.
const ENABLE_NETWORK_STEP_LINK = false

function isTerminal(state: SessionStatus['state']): boolean {
  return state === 'completed' || state === 'failed' || state === 'interrupted'
}

function Mark() {
  return <span className="mark" aria-hidden="true"><i /><i /><i /><i /></span>
}

function PageHeader() {
  return <header className="topbar">
    <div className="brand"><Mark /><span className="brand-name">CAPSTONE</span><span className="brand-divider" />
      <span className="brand-subtitle">电网分析工作台</span></div>
    <a className="project-link" href="https://github.com/uukuguy/capstone"
      target="_blank" rel="noopener noreferrer" aria-label="在 GitHub 查看 CAPSTONE 项目源代码">
      <svg className="project-link-icon" viewBox="0 0 16 16" aria-hidden="true" focusable="false">
        <path d="M6.766 11.328c-2.063-.25-3.516-1.734-3.516-3.656 0-.781.281-1.625.75-2.188-.203-.515-.172-1.609.063-2.062.625-.078 1.468.25 1.968.703.594-.187 1.219-.281 1.985-.281.765 0 1.39.094 1.953.265.484-.437 1.344-.765 1.969-.687.218.422.25 1.515.046 2.047.5.593.766 1.39.766 2.203 0 1.922-1.453 3.375-3.547 3.64.531.344.89 1.094.89 1.954v1.625c0 .468.391.734.86.547C13.781 14.359 16 11.53 16 8.03 16 3.61 12.406 0 7.984 0 3.563 0 0 3.61 0 8.031a7.88 7.88 0 0 0 5.172 7.422c.422.156.828-.125.828-.547v-1.25c-.219.094-.5.156-.75.156-1.031 0-1.64-.562-2.078-1.609-.172-.422-.36-.672-.719-.719-.187-.015-.25-.093-.25-.187 0-.188.313-.328.625-.328.453 0 .844.281 1.25.86.313.452.64.655 1.031.655s.641-.14 1-.5c.266-.265.47-.5.657-.656" />
      </svg>
      <span className="project-link-address">github.com/uukuguy/capstone</span>
      <span className="project-link-short">GitHub</span>
      <span aria-hidden="true">↗</span>
    </a>
  </header>
}

function CatalogPanel({ catalog, selection, onSelect }: {
  catalog: Catalog; selection: Selection | null; onSelect: (value: Selection) => void
}) {
  const total = catalog.applications.reduce((count, app) => count + app.cases.length, 0)
  return <aside className="catalog-panel" aria-label="案例目录">
    <div className="section-heading"><div><span className="eyebrow">CASE LIBRARY</span><h2>案例库</h2></div>
      <span className="count-pill">{String(total).padStart(2, '0')}</span></div>
    <p className="panel-intro">从已登记的分析任务开始，每一步都保留在同一运行中。</p>
    <div className="application-list">
      {catalog.applications.map((app: ApplicationCard) => <section key={app.application_id}>
        <div className="app-label">{app.title}</div>
        <div className="case-list">{app.cases.map((caseCard: CaseCard) => {
          const active = selection?.applicationId === app.application_id && selection.caseId === caseCard.case_id
          return <button key={caseCard.case_id} className={`case-card ${active ? 'is-active' : ''}`}
            aria-current={active ? 'true' : undefined}
            onClick={() => onSelect({ applicationId: app.application_id, caseId: caseCard.case_id })}>
            <span className="case-card-top"><span className="case-card-title">{caseCard.title}</span><span aria-hidden="true">↗</span></span>
            <span className="case-card-summary">{caseCard.summary}</span>
            <span className="case-card-footer"><span>共 3 步</span></span>
          </button>
        })}</div>
      </section>)}</div>
    <div className="catalog-footnote">数值和网络结论以当前运行结果为准。</div>
  </aside>
}

export function readerAnswerText(turn: CommittedTurn): string {
  if (typeof turn.answer_summary === 'string' && turn.answer_summary.trim()) {
    return turn.answer_summary
  }
  if (!/^scripted semantic execution completed for question \d+\s*:/i.test(turn.answer_output)) {
    return turn.answer_output
  }
  return turn.result_refs.length > 0 || turn.evidence_refs.length > 0
    ? '本步已完成，结果与证据已写入当前运行。'
    : '本步已完成。'
}

function AnswerCard({ turn, onEvidence }: {
  turn: CommittedTurn; onEvidence: (ref: string) => void
}) {
  return <div className="answer-card">
    <div className="answer-label"><span className="answer-check">✓</span> 已提交回答</div>
    <p className="answer-text">{readerAnswerText(turn)}</p>
    {(turn.result_refs.length > 0 || turn.evidence_refs.length > 0) &&
      <div className="reference-row">
        <span className="reference-title">本轮引用</span>
        {turn.result_refs.map((ref, index) => <span className="reference-chip" key={ref}
          title={ref}>结果 {index + 1}</span>)}
        {turn.evidence_refs.map((ref, index) => <button className="reference-chip evidence-chip"
          key={ref} title={ref} onClick={() => onEvidence(ref)}>证据 {index + 1} ↗</button>)}
      </div>}
  </div>
}

function CapstoneIntro() {
  return <section className="capstone-intro" aria-label="CAPSTONE 框架介绍">
      <div className="capstone-intro-art notranslate" translate="no">
        <img src="/capstone-science-hero.png" alt="工业专业框架与 AI 智能体应用的连接示意" />
        <div className="capstone-intro-overlay">
          <div className="capstone-intro-main">
            <span className="capstone-intro-kicker">电网科学AI <span> / SCIENTIFIC AI FOR THE GRID</span></span>
            <strong>从专业仿真<br />到智能推演</strong>
            <div className="capstone-intro-frameworks"><span>pandapower</span><span>PyPSA</span></div>
            <div className="capstone-intro-disciplines" aria-label="电网科学AI模型方向">
              <span><b>神经算子</b>DeepONet · FNO</span>
              <span><b>动力学模型</b>Neural-DAE · Koopman</span>
              <span><b>物理图网络</b>GraphGPS · PI-GNN</span>
            </div>
          </div>
          <span className="capstone-intro-principles">CAPABILITY / EVIDENCE / CONTROL</span>
        </div>
      </div>
      <p>CAPSTONE 为电网科学AI提供应用底座：把 pandapower、PyPSA 等科学计算工具封装为统一的领域能力，由智能体组织任务、权威系统完成计算。每一步的结果与证据随运行留存，形成可复用、可核查的分析过程。</p>
    </section>
}

function RunPanel({ caseCard, status, turns, progress, actionPending, automatic, autoPaused, onStart,
                    onSubmit, onClose, onAuto, onRestart, onStopAuto, onEvidence,
                    networkView, previewDiagram, previewUnavailable,
                    networkFocusKey, networkUnavailable, nextNetworkTask,
                    networkStory, selectedStoryOrdinal, onStoryStep,
                    report, result, runDurationMs }: {
  caseCard: CaseCard; status: SessionStatus | null;
  turns: Record<number, CommittedTurn>; progress: string | null; actionPending: boolean;
  automatic: boolean; autoPaused: boolean; onAuto: () => void; onRestart: () => void; onStopAuto: () => void;
  onStart: () => void; onSubmit: () => void; onClose: () => void;
  onEvidence: (ref: string) => void
  networkView: NetworkViewData | null; previewDiagram: NetworkDiagram | null;
  previewUnavailable: boolean; networkFocusKey: string;
  networkUnavailable: boolean; nextNetworkTask: boolean;
  networkStory: NetworkStory | null; selectedStoryOrdinal: number | null;
  onStoryStep: (ordinal: number) => void;
  report: string | null; result: unknown; runDurationMs: number | null
}) {
  const next = (status?.completed_turns ?? 0) + 1
  return <main className="run-panel">
    <h1 className="visually-hidden">{caseCard.title}</h1>
    <div className="timeline-heading model-section-heading"><div>
      <span className="eyebrow">MODEL / OVERVIEW</span><h2>电网模型</h2>
    </div></div>
    <NetworkView view={networkView} previewDiagram={previewDiagram}
      modelName={caseCard.model_origin} focusKey={networkFocusKey}
      unavailable={networkUnavailable} previewUnavailable={previewUnavailable}
      nextTask={nextNetworkTask}
      historyFocusIds={networkStory?.steps.find((step) => step.ordinal === selectedStoryOrdinal)?.history_focus_ids || []} />
    {networkStory && <div className="network-story-controls" aria-label="拓扑故事步骤">
      <span className="network-story-label">完成后回看</span>
      {networkStory.steps.map((step) => <button type="button" key={step.ordinal}
        className={step.ordinal === selectedStoryOrdinal ? 'is-selected' : ''}
        onClick={() => onStoryStep(step.ordinal)}>
        步骤 {step.ordinal}
      </button>)}
      <span className="network-story-source">{networkStory.plan_source === 'llm' ? '重点由模型规划' : '按权威排序展示'}</span>
    </div>}
      <div className="timeline-heading"><div><span className="eyebrow">ANALYSIS / WORKFLOW</span><h2>推演过程</h2></div>
      <div className="timeline-heading-actions">{(status?.state === 'completed' || status?.state === 'failed' ||
        status?.state === 'interrupted') &&
        <button type="button" className="timeline-reset" onClick={onRestart}
          disabled={actionPending}>重置案例</button>}
        <span className="timeline-count">{status?.completed_turns ?? 0} / {caseCard.instructions.length} 已完成</span></div></div>
    {autoPaused && status?.state !== 'completed' && status?.state !== 'failed' &&
      status?.state !== 'interrupted' && <div className="auto-pause-notice" role="status">
        {status && status.accepted_turns > status.completed_turns
          ? '自动执行已停止；当前指令仍会完成，后续不会自动提交。'
          : '自动执行已停止；后续不会自动提交，可手动继续或重新自动完成。'}
      </div>}
    <div className={`run-action-bar${status?.state === 'completed' || status?.state === 'failed' ||
      status?.state === 'interrupted' ? ' is-terminal' : ''}`}>
      {!status && <><div><strong>准备开始</strong><span>执行首条指令，或自动完成全部指令。</span></div>
        <div className="action-buttons"><button className="secondary-button" onClick={onStart} disabled={actionPending}>执行指令 1</button>
          <button className="primary-button auto-button" onClick={onAuto} disabled={actionPending}>自动完成</button></div></>}
      {status?.state === 'pending' && <div className="working-line"><span className="spinner" />正在准备当前运行…</div>}
      {status?.state === 'ready' && next <= caseCard.instructions.length && <><div><strong>指令 {next} 已就绪</strong>
        <span>{automatic ? '自动执行会等待本轮回答后继续。' : '可逐步提交，或由系统自动完成剩余步骤。'}</span></div>
        {!automatic && <div className="action-buttons"><button className="secondary-button" onClick={onSubmit} disabled={actionPending}>执行指令 {next}</button>
          <button className="primary-button auto-button" onClick={onAuto} disabled={actionPending}>自动完成</button></div>}</>}
      {status?.state === 'executing' && <div className="working-line"><span className="spinner" />{progress || '正在执行当前指令…'}</div>}
      {status?.state === 'ready' && next > caseCard.instructions.length && <><div><strong>全部指令已完成</strong>
        <span>结束本轮后生成最终结果与报告。</span></div>
        {!automatic && <div className="action-buttons"><button className="primary-button" onClick={onClose} disabled={actionPending}>生成报告 <span aria-hidden="true">↗</span></button></div>}</>}
      {status?.state === 'closing' && <div className="working-line"><span className="spinner" />正在整理本轮结果与报告…</div>}
      {status?.state === 'completed' && <div className="completion-message"><span>✓</span><div><strong>本轮推演已完成</strong>
        <small>{runDurationMs !== null ? `推演用时 ${formatDuration(runDurationMs)}；` : ''}
          {report ? '报告见下方，证据可在右侧查看。' : '已提交答案保留在本次运行中。'}</small></div></div>}
      {(status?.state === 'failed' || status?.state === 'interrupted') && <div className="failure-message">
        <strong>{statusText(status)}</strong><span>{status.error_code === 'session_idle_timeout'
          ? '长时间未提交新指令，计算资源已释放；已完成步骤仍可回看。'
          : status.error_code === 'session_capacity_evicted'
            ? '有新分析需要运行，当前空闲会话已释放；已完成步骤仍可回看。'
          : '已提交的回答仍可查看。'}</span></div>}
      {automatic && status?.state !== 'closing' && status?.state !== 'completed' &&
        status?.state !== 'failed' && status?.state !== 'interrupted' &&
        <button className="secondary-button stop-auto" onClick={onStopAuto}>停止自动执行</button>}
    </div>
    <ol className="timeline">
      {caseCard.instructions.map((instruction, index) => {
        const ordinal = index + 1
        const answer = turns[ordinal]
        const isNext = status?.state === 'ready' && ordinal === next
        const isExecuting = status?.state === 'executing' && ordinal === next
        const itemStatus = answer
          ? answer.duration_ms !== undefined ? `已完成 · ${formatDuration(answer.duration_ms)}` : '已完成'
          : isExecuting ? '分析中' : isNext ? '下一步' : '待执行'
        return <li key={ordinal} className={`timeline-item ${answer ? 'is-complete' : ''} ${isNext || isExecuting ? 'is-current' : ''}`}>
          <span className="timeline-number">{String(ordinal).padStart(2, '0')}</span>
          <div className="timeline-content"><div className="timeline-item-head">
            <p className="instruction-text">{instruction}</p><span>{itemStatus}</span></div>
            {answer && <AnswerCard turn={answer} onEvidence={onEvidence} />}
            {isExecuting && <div className="working-line"><span className="spinner" />{progress || '正在执行已登记的分析步骤…'}</div>}
          </div>
        </li>
      })}
    </ol>
    {report && <section className="run-report" aria-label="分析报告">
      <div className="timeline-heading"><div><span className="eyebrow">ANALYSIS / REPORT</span><h2>分析报告</h2></div></div>
      <div className="run-report-paper"><ReportDocument report={report} />
        {result !== null && <details className="result-details"><summary>查看结构化结果</summary>
          <pre>{JSON.stringify(result, null, 2)}</pre></details>}</div>
    </section>}
  </main>
}

function reportInlineText(value: string): string {
  return value
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/__([^_]+)__/g, '$1')
}

function reportTableRow(line: string): string[] {
  const cells = line.trim().replace(/^\|/, '').replace(/\|$/, '').split('|')
  return cells.map((cell) => reportInlineText(cell.trim()))
}

function isReportTableLine(line: string): boolean {
  const trimmed = line.trim()
  return trimmed.startsWith('|') && trimmed.endsWith('|') && trimmed.split('|').length >= 3
}

function isReportTableSeparator(line: string): boolean {
  return reportTableRow(line).every((cell) => /^:?-{3,}:?$/.test(cell.replace(/\s/g, '')))
}

function ReportTable({ rows }: { rows: string[][] }) {
  const [header, ...body] = rows
  return <table>
    <thead><tr>{header.map((cell, index) => <th key={index}>{cell}</th>)}</tr></thead>
    <tbody>{body.map((row, rowIndex) => <tr key={rowIndex}>
      {row.map((cell, cellIndex) => <td key={cellIndex}>{cell}</td>)}
    </tr>)}</tbody>
  </table>
}

function ReportDocument({ report }: { report: string }) {
  // Some model responses place a heading immediately after the preceding
  // sentence. Split that boundary before applying the line-level renderer.
  const lines = report.replace(/([。！？.!?])(?=#{1,6}\s)/g, '$1\n').split('\n')
  const content = []
  let index = 0
  while (index < lines.length) {
    const raw = lines[index]
    if (isReportTableLine(raw)) {
      const tableLines: string[] = []
      while (index < lines.length && isReportTableLine(lines[index])) {
        tableLines.push(lines[index])
        index += 1
      }
      const rows = tableLines.filter((line) => !isReportTableSeparator(line)).map(reportTableRow)
      if (rows.length > 0 && rows[0].length > 0) {
        content.push(<ReportTable key={`table-${index}`} rows={rows} />)
      }
      continue
    }

    const line = reportInlineText(raw)
    const heading = /^(#{1,6})\s+(.+)$/.exec(line)
    if (heading) {
      const text = heading[2]
      const level = heading[1].length
      if (level === 1) content.push(<h2 key={index}>{text}</h2>)
      else if (level === 2) content.push(<h3 key={index}>{text}</h3>)
      else if (level === 3) content.push(<h4 key={index}>{text}</h4>)
      else if (level === 4) content.push(<h5 key={index}>{text}</h5>)
      else content.push(<h6 key={index}>{text}</h6>)
    } else if (line.startsWith('- ')) {
      content.push(<p className="report-bullet" key={index}>{line.slice(2)}</p>)
    } else if (line) {
      content.push(<p key={index}>{line}</p>)
    } else {
      content.push(<div className="report-space" key={index} />)
    }
    index += 1
  }
  return <article className="report-document">{content}</article>
}

function DetailPanel({ status, caseCard, turns, tab, onTab, onReconnect, actionPending,
                       evidenceRef, evidence, evidencePending }: {
  status: SessionStatus | null; caseCard: CaseCard; turns: Record<number, CommittedTurn>;
  tab: DetailTab; onTab: (tab: DetailTab) => void;
  onReconnect: () => void; actionPending: boolean;
  evidenceRef: string | null; evidence: unknown; evidencePending: boolean
}) {
  const refs = Object.values(turns).flatMap((turn) => turn.evidence_refs)
  const uniqueRefs = [...new Set(refs)]
  return <aside className="detail-panel" aria-label="运行详情">
    <div className="section-heading"><div><span className="eyebrow">CURRENT RUN</span><h2>运行详情</h2></div>
      <div className="detail-heading-actions"><span className={`status-led ${status?.state || 'idle'}`} />
        <button type="button" className="text-button reconnect-button" onClick={onReconnect}
          disabled={actionPending}>断开/重连</button></div>
    </div>
    <div className="detail-tabs" role="tablist" aria-label="详情视图">
      {([['overview', '概览'], ['evidence', '证据']] as const).map(([value, label]) =>
        <button key={value} role="tab" aria-selected={tab === value} onClick={() => onTab(value)}>{label}</button>)}
    </div>
    {tab === 'overview' && <div className="detail-body">
      <section className="case-overview" aria-label="当前案例概览">
        <h3>{caseCard.title}</h3>
        <p className="case-overview-summary">{caseCard.summary}</p>
        <dl className="case-overview-facts">
          {([
            ['电网模型', caseCard.model_origin],
            ['分析步骤', `${caseCard.instructions.length} 步`],
            ['情景假设', caseCard.scenario_assumption],
            ['结果边界', caseCard.interpretation_boundary],
          ] as const).map(([label, value]) => <div
            className={`case-overview-fact${isLongCaseFact(value) ? ' is-long' : ''}`}
            key={label}>
            <dt>{label}</dt><dd>{value}</dd>
          </div>)}
        </dl>
      </section>
      <div className="status-card"><span className="detail-label">运行状态</span>
        <strong>{statusText(status)}</strong>
        <div className="progress-track"><div style={{ width: `${((status?.completed_turns ?? 0) / caseCard.instructions.length) * 100}%` }} /></div>
        <span className="progress-caption">{status?.completed_turns ?? 0} / {caseCard.instructions.length} 条指令</span></div>
      <div className="detail-metrics"><div><span>已提交回答</span><strong>{String(status?.completed_turns ?? 0).padStart(2, '0')}</strong></div>
        <div><span>证据引用</span><strong>{String(uniqueRefs.length).padStart(2, '0')}</strong></div></div>
      <div className="detail-section"><span className="detail-label">运行编号</span>
        <code className="run-id">{status?.run_id || '启动后生成'}</code></div>
      <div className="detail-section"><span className="detail-label">证据边界</span>
        <p>此处仅显示当前运行已提交回答关联的证据引用。选择证据可查看受限投影。</p></div>
    </div>}
    {tab === 'evidence' && <div className="detail-body">
      {evidenceRef ? <><div className="detail-label">证据投影</div><code className="evidence-ref">{evidenceRef}</code>
        {evidencePending ? <div className="working-line"><span className="spinner" />正在读取…</div>
          : evidence !== null ? <pre className="evidence-value">{JSON.stringify(evidence, null, 2)}</pre>
            : <p className="detail-hint">该引用尚无可读取的本轮投影。</p>}</>
        : <div className="empty-detail"><span className="empty-symbol">◇</span><strong>选择一条证据</strong>
          <p>在左侧已提交回答中选择证据引用，查看当前运行的受限投影。</p></div>}
    </div>}
    <div className="detail-footer"><span className="pulse-dot" /> 当前运行 · 可追溯</div>
  </aside>
}

function CaseWorkspace({ client, app, caseCard, visible, onInvalidToken }: {
  client: CapstoneClient; app: ApplicationCard; caseCard: CaseCard;
  visible: boolean; onInvalidToken: (message: string) => void
}) {
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [status, setStatus] = useState<SessionStatus | null>(null)
  const [turns, setTurns] = useState<Record<number, CommittedTurn>>({})
  const [progress, setProgress] = useState<string | null>(null)
  const [report, setReport] = useState<string | null>(null)
  const [result, setResult] = useState<unknown>(null)
  const [runDurationMs, setRunDurationMs] = useState<number | null>(null)
  const [tab, setTab] = useState<DetailTab>('overview')
  const [evidenceRef, setEvidenceRef] = useState<string | null>(null)
  const [evidence, setEvidence] = useState<unknown>(null)
  const [evidencePending, setEvidencePending] = useState(false)
  const [previewDiagram, setPreviewDiagram] = useState<NetworkDiagram | null>(null)
  const [previewUnavailable, setPreviewUnavailable] = useState(false)
  const [networkStory, setNetworkStory] = useState<NetworkStory | null>(null)
  const [selectedStoryOrdinal, setSelectedStoryOrdinal] = useState<number | null>(null)
  const [pending, setPending] = useState(false)
  const [restoring, setRestoring] = useState(() =>
    Boolean(readRun(app.application_id, caseCard.case_id)?.sessionId))
  const [error, setError] = useState<string | null>(null)
  const [automatic, setAutomatic] = useState(false)
  const [autoPaused, setAutoPaused] = useState(false)
  const autoController = useRef<AbortController | null>(null)
  const runStartedAt = useRef<number | null>(null)
  const stepStartedAt = useRef<number | null>(null)
  const measuredDurationMs = useRef(0)
  const measuredStepCount = useRef(0)
  const closingStartedAt = useRef<number | null>(null)
  const automaticKeys = useRef(new Map<string, string>())

  useEffect(() => () => autoController.current?.abort(), [])

  useEffect(() => {
    if (!error) return
    const timer = window.setTimeout(() => setError(null), 5000)
    return () => window.clearTimeout(timer)
  }, [error])

  useEffect(() => {
    const previous = readRun(app.application_id, caseCard.case_id)
    if (!previous?.sessionId) return
    let cancelled = false
    void client.status(previous.sessionId).then((current) => {
      if (cancelled) return
      if (current.application_id !== app.application_id) {
        forgetRun(app.application_id, caseCard.case_id)
        return
      }
      setSessionId(current.session_id)
      setStatus(current)
    }).catch((cause) => {
      if (cancelled) return
      if (cause instanceof ApiError && cause.status === 404) {
        forgetRun(app.application_id, caseCard.case_id)
      } else {
        setError('恢复上次运行失败，请重试连接。')
      }
    }).finally(() => { if (!cancelled) setRestoring(false) })
    return () => { cancelled = true }
  }, [client, app.application_id, caseCard.case_id])

  useEffect(() => {
    if (!visible || previewDiagram) return
    let cancelled = false
    void client.caseDiagram(app.application_id, caseCard.case_id).then((raw) => {
      if (cancelled) return
      const diagram = parseNetworkDiagram(raw)
      if (diagram) setPreviewDiagram(diagram)
      else setPreviewUnavailable(true)
    }).catch((cause) => {
      if (cancelled) return
      if (cause instanceof ApiError && cause.status === 401) onInvalidToken(cause.message)
      else setPreviewUnavailable(true)
    })
    return () => { cancelled = true }
  }, [visible, previewDiagram, client, app.application_id, caseCard.case_id, onInvalidToken])

  function stopAutomatic() {
    if (autoController.current) {
      autoController.current.abort()
      setAutoPaused(true)
    }
    autoController.current = null
    setAutomatic(false)
  }

  function clearRun(forgetStored = true) {
    stopAutomatic()
    setAutoPaused(false)
    if (forgetStored) forgetRun(app.application_id, caseCard.case_id)
    setSessionId(null); setStatus(null); setTurns({}); setProgress(null)
    setReport(null); setResult(null); setEvidenceRef(null); setEvidence(null); setTab('overview')
    setNetworkStory(null); setSelectedStoryOrdinal(null)
    runStartedAt.current = null; stepStartedAt.current = null
    measuredDurationMs.current = 0; measuredStepCount.current = 0
    closingStartedAt.current = null; setRunDurationMs(null)
  }

  function beginRunTimer() {
    if (runStartedAt.current === null) runStartedAt.current = Date.now()
  }

  function finishRunTimer() {
    const now = Date.now()
    if (measuredStepCount.current > 0) {
      setRunDurationMs(Math.max(0, measuredDurationMs.current
        + (stepStartedAt.current === null ? 0 : now - stepStartedAt.current)
        + (closingStartedAt.current === null ? 0 : now - closingStartedAt.current)))
    } else if (runStartedAt.current !== null) {
      setRunDurationMs(Math.max(0, now - runStartedAt.current))
    }
  }

  function activeElapsedMs(): number | null {
    if (runStartedAt.current === null && measuredStepCount.current === 0) return null
    if (measuredStepCount.current === 0) {
      return Math.max(0, Date.now() - (runStartedAt.current ?? Date.now()))
    }
    const now = Date.now()
    return Math.max(0, measuredDurationMs.current
      + (stepStartedAt.current === null ? 0 : now - stepStartedAt.current)
      + (closingStartedAt.current === null ? 0 : now - closingStartedAt.current))
  }

  function recordStepDuration(answer: CommittedTurn) {
    const reported = answer.duration_ms
    const duration = typeof reported === 'number' && Number.isFinite(reported)
      ? Math.max(0, reported)
      : stepStartedAt.current === null ? null : Math.max(0, Date.now() - stepStartedAt.current)
    if (duration === null) return
    measuredDurationMs.current += duration
    measuredStepCount.current += 1
    stepStartedAt.current = null
  }

  useEffect(() => {
    if (!client || !sessionId) return
    const controller = new AbortController()
    let cursor = 0
    const sid = sessionId
    async function complete() {
      const storyRequest = typeof (client as Partial<CapstoneClient>).networkStory === 'function'
        ? client!.networkStory(sid, controller.signal)
        : Promise.reject(new Error('拓扑故事接口不可用'))
      const outcomes = await Promise.allSettled([
        client!.report(sid), client!.result(sid), storyRequest,
      ])
      if (controller.signal.aborted) return
      if (outcomes[0].status === 'fulfilled') setReport(outcomes[0].value)
      if (outcomes[1].status === 'fulfilled') setResult(outcomes[1].value)
      if (outcomes[2].status === 'fulfilled') {
        setNetworkStory(outcomes[2].value)
        const steps = outcomes[2].value.steps
        setSelectedStoryOrdinal(steps.length ? steps[steps.length - 1].ordinal : null)
      }
    }
    async function run() {
      while (!controller.signal.aborted) {
        try {
          for await (const event of client!.events(sid, cursor, controller.signal)) {
            if (controller.signal.aborted) return
            cursor = event.sequence
            if (event.event === 'ready') {
              setStatus((before) => before && (isTerminal(before.state) ? before : { ...before,
                state: before.accepted_turns > before.completed_turns ? before.state : 'ready',
                run_id: typeof event.payload.run_id === 'string' ? event.payload.run_id : before.run_id }))
            } else if (event.event === 'progress') {
              const message = typeof event.payload.message === 'string' ? event.payload.message : null
              const elapsed = activeElapsedMs()
              setProgress(message === null ? null : `[${elapsed === null ? '—' : formatDuration(elapsed)}] ${message}`)
            } else if (event.event === 'answer_committed') {
              const answer = event.payload as CommittedTurn
              recordStepDuration(answer)
              setTurns((before) => ({ ...before, [answer.ordinal]: answer }))
              setStatus((before) => before && (isTerminal(before.state) ? before : { ...before, state: 'ready',
                completed_turns: answer.ordinal, accepted_turns: answer.ordinal }))
              setProgress(null)
            } else if (event.event === 'network_view' || event.event === 'network_layer' ||
              event.event === 'network_view_unavailable' || event.event === 'network_layer_unavailable') {
              // Keep optional projection events from affecting the real answer flow.
              if (ENABLE_NETWORK_STEP_LINK) {
                // Reserved for the separately validated network projection path.
              }
            } else if (event.event === 'completed') {
              setStatus((before) => before && { ...before, state: 'completed' })
              finishRunTimer()
              await complete()
              return
            } else if (event.event === 'failed') {
              setStatus((before) => before && { ...before, state: 'failed',
                error_code: typeof event.payload.code === 'string' ? event.payload.code : before.error_code })
              return
            }
          }
          const current = await client!.status(sid)
          if (controller.signal.aborted) return
          setStatus(current)
          if (current.state === 'completed') { finishRunTimer(); await complete(); return }
          if (current.state === 'failed' || current.state === 'interrupted') return
        } catch (cause) {
          if (controller.signal.aborted) return
          if (cause instanceof ApiError && cause.status === 401) {
            clearRun(false)
            onInvalidToken(cause.message)
            return
          }
          setError('事件连接暂时中断，正在恢复…')
        }
        await new Promise((resolve) => setTimeout(resolve, 800))
      }
    }
    void run()
    return () => controller.abort()
  }, [client, sessionId])

  async function start() {
    if (!client || !app || !caseCard || restoring) return
    setPending(true); setError(null); clearRun(false)
    beginRunTimer()
    try {
      const createKey = ensureCreateKey(app.application_id, caseCard.case_id)
      const created = await client.createSession(app.application_id, caseCard.case_id, createKey)
      rememberSession(app.application_id, caseCard.case_id, createKey, created.session_id)
      setStatus({ ...created, error_code: null, accepted_turns: 0, completed_turns: 0 })
      setSessionId(created.session_id)
      let ready: SessionStatus | null = null
      for (let attempt = 0; attempt < 150; attempt += 1) {
        const current = await client.status(created.session_id)
        setStatus((before) => before && before.session_id === current.session_id &&
          before.completed_turns > current.completed_turns ? before : current)
        if (current.state === 'ready') { ready = current; break }
        if (current.state === 'failed' || current.state === 'interrupted') {
          throw new Error('当前运行未能启动')
        }
        await new Promise((resolve) => setTimeout(resolve, 400))
      }
      if (!ready) throw new Error('等待当前运行超时')
      await client.submitTurn(created.session_id, caseCard.instructions[0], commandKey())
      stepStartedAt.current = Date.now()
      setStatus((before) => before && before.completed_turns === 0
        ? { ...before, state: 'executing', accepted_turns: 1 } : before)
    } catch (cause) { setError(cause instanceof Error ? cause.message : '启动失败') }
    finally { setPending(false) }
  }

  function startAutomatic() {
    if (!client || !app || !caseCard || restoring || autoController.current) return
    const existingSessionId = sessionId
    if (!existingSessionId) clearRun(false)
    const creationKey = existingSessionId ? undefined :
      ensureCreateKey(app.application_id, caseCard.case_id)
    const controller = new AbortController()
    autoController.current = controller
    beginRunTimer()
    setAutomatic(true); setAutoPaused(false); setError(null)
    void runAutomaticSession(
      client, app.application_id, caseCard.case_id,
      caseCard.instructions, existingSessionId, controller.signal, automaticKeys.current,
      (created) => {
        if (creationKey) rememberSession(app.application_id, caseCard.case_id,
                                         creationKey, created.session_id)
        setStatus({ ...created, error_code: null, accepted_turns: 0, completed_turns: 0 })
        setSessionId(created.session_id)
      },
      (current) => {
        if (current.state === 'executing' && current.accepted_turns > current.completed_turns &&
            stepStartedAt.current === null) {
          stepStartedAt.current = Date.now()
        }
        if (current.state === 'closing' && closingStartedAt.current === null) {
          closingStartedAt.current = Date.now()
        }
        setStatus((before) => before && before.session_id === current.session_id &&
          (isTerminal(before.state) || before.completed_turns > current.completed_turns ||
            before.accepted_turns > current.accepted_turns)
          ? before : current)
      },
      undefined,
      undefined,
      creationKey,
    ).then(async (sid) => {
      if (controller.signal.aborted || !autoController.current) return
      const current = await client.status(sid)
      if (current.state === 'completed') {
        finishRunTimer()
        const outcomes = await Promise.allSettled([client.report(sid), client.result(sid)])
        if (outcomes[0].status === 'fulfilled') setReport(outcomes[0].value)
        if (outcomes[1].status === 'fulfilled') setResult(outcomes[1].value)
      }
    }).catch((cause) => {
      if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : '自动执行失败')
    }).finally(() => {
      if (autoController.current === controller) {
        autoController.current = null
        setAutomatic(false)
      }
    })
  }

  async function submit() {
    if (!client || !sessionId || !caseCard || !status) return
    const ordinal = status.completed_turns + 1
    const instruction = caseCard.instructions[ordinal - 1]
    if (!instruction) return
    setPending(true); setAutoPaused(false); setError(null)
    beginRunTimer()
    try {
      await client.submitTurn(sessionId, instruction, commandKey())
      stepStartedAt.current = Date.now()
      setStatus((before) => before && before.completed_turns < ordinal
        ? { ...before, state: 'executing', accepted_turns: ordinal } : before)
    } catch (cause) { setError(cause instanceof Error ? cause.message : '提交失败') }
    finally { setPending(false) }
  }

  async function close() {
    if (!client || !sessionId) return
    setPending(true); setAutoPaused(false); setError(null)
    closingStartedAt.current = Date.now()
    try {
      await client.close(sessionId, commandKey())
      setStatus((before) => before && before.state !== 'completed'
        ? { ...before, state: 'closing' } : before)
    } catch (cause) {
      closingStartedAt.current = null
      setError(cause instanceof Error ? cause.message : '结束失败')
    }
    finally { setPending(false) }
  }

  async function disconnectAndReconnect() {
    if (!client || restoring) return
    setPending(true); setError(null); stopAutomatic()
    const previousSessionId = sessionId
    try {
      if (previousSessionId) {
        await client.disconnect(previousSessionId, `disconnect-${previousSessionId}`)
      }
      clearRun(true)
      const createKey = ensureCreateKey(app.application_id, caseCard.case_id)
      const created = await client.createSession(app.application_id, caseCard.case_id, createKey)
      rememberSession(app.application_id, caseCard.case_id, createKey, created.session_id)
      setStatus({ ...created, error_code: null, accepted_turns: 0, completed_turns: 0 })
      setSessionId(created.session_id)
      for (let attempt = 0; attempt < 150; attempt += 1) {
        const current = await client.status(created.session_id)
        setStatus(current)
        if (current.state === 'ready') return
        if (current.state === 'failed' || current.state === 'interrupted') {
          throw new Error('新会话未能启动')
        }
        await new Promise((resolve) => setTimeout(resolve, 400))
      }
      throw new Error('等待新会话超时')
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '断开并重连失败')
    } finally { setPending(false) }
  }

  async function showEvidence(ref: string) {
    if (!client || !sessionId) return
    setEvidenceRef(ref); setEvidence(null); setEvidencePending(true); setTab('evidence')
    try { setEvidence(await client.evidence(sessionId, ref)) }
    catch { setEvidence(null) }
    finally { setEvidencePending(false) }
  }

  const selectedStory = networkStory?.steps.find((step) => step.ordinal === selectedStoryOrdinal) ?? null
  const networkView: NetworkViewData | null = selectedStory && networkStory ? {
    schema: 'capstone-network-view/2.0', ordinal: selectedStory.ordinal,
    diagram: networkStory.diagram,
    layer: { schema: 'capstone-network-layer/1.0', ordinal: selectedStory.ordinal,
      diagram_ref: selectedStory.diagram_ref, model_revision: selectedStory.model_revision,
      focus_ids: selectedStory.current_focus_ids, next_focus_ids: [], overlay: selectedStory.overlay },
  } : null
  const networkFocusKey = `${sessionId ?? 'idle'}:${selectedStoryOrdinal ?? 'preview'}:${status?.state ?? 'new'}`
  const nextNetworkTask = false
  const networkUnavailable = false

  return <div style={{ display: visible ? 'contents' : 'none' }}>
    <div className="workspace-center">
      {error && <div className="workspace-alert" role="alert">{error}</div>}
      <CapstoneIntro />
      <RunPanel caseCard={caseCard} status={status}
        turns={turns} progress={progress} actionPending={pending || restoring}
        automatic={automatic} autoPaused={autoPaused}
        networkView={networkView} previewDiagram={previewDiagram}
        previewUnavailable={previewUnavailable} networkFocusKey={networkFocusKey}
        networkUnavailable={networkUnavailable} nextNetworkTask={nextNetworkTask}
        networkStory={networkStory} selectedStoryOrdinal={selectedStoryOrdinal}
        onStoryStep={setSelectedStoryOrdinal}
        report={report} result={result}
        runDurationMs={runDurationMs}
        onStart={() => void start()} onSubmit={() => void submit()} onClose={() => void close()}
        onAuto={startAutomatic} onRestart={clearRun} onStopAuto={stopAutomatic}
        onEvidence={(ref) => void showEvidence(ref)} />
    </div>
    <DetailPanel status={status} caseCard={caseCard} turns={turns}
      tab={tab} onTab={setTab} onReconnect={() => void disconnectAndReconnect()}
      actionPending={pending || restoring}
      evidenceRef={evidenceRef} evidence={evidence} evidencePending={evidencePending} />
  </div>
}

export default function App({ clientFactory = defaultClientFactory }: Props) {
  const [client, setClient] = useState<CapstoneClient | null>(null)
  const [catalog, setCatalog] = useState<Catalog | null>(null)
  const [selection, setSelection] = useState<Selection | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let active = true
    setLoading(true)
    setError(null)
    const bootstrap = new CapstoneClient(import.meta.env.VITE_API_ORIGIN || '', '')
    void (async () => {
      const token = await bootstrap.demoCredential()
      const nextClient = clientFactory(token)
      const nextCatalog = await nextClient.catalog()
      if (nextCatalog.schema !== 'capstone-catalog/1.0' || !nextCatalog.applications.length) {
        throw new Error('案例目录不可用')
      }
      const firstApp = nextCatalog.applications.find((item) => item.cases.length)
      if (!firstApp) throw new Error('没有可运行的案例')
      if (!active) return
      const previous = readSelection()
      const selected = previous && nextCatalog.applications.some((item) =>
        item.application_id === previous.applicationId &&
        item.cases.some((entry) => entry.case_id === previous.caseId))
        ? previous : { applicationId: firstApp.application_id, caseId: firstApp.cases[0].case_id }
      setCatalog(nextCatalog); setClient(nextClient); setSelection(selected)
    })().catch((cause) => {
      if (active) setError(cause instanceof Error ? cause.message : '连接失败')
    }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [clientFactory, attempt])

  function invalidate(message: string) {
    setClient(null); setCatalog(null); setSelection(null); setError(message)
  }

  function selectCase(value: Selection) {
    rememberSelection(value)
    setSelection(value)
  }

  return <div className="app-shell">
    <PageHeader />
    {!client || !catalog || !selection ?
      <main className="connection-state" aria-live="polite">
        {loading ? <strong>正在打开电网分析工作台…</strong> : <>
          <strong>演示服务暂时无法连接</strong>
          <p role="alert">{error || '请稍后重试。'}</p>
          <button className="primary-button" onClick={() => setAttempt((value) => value + 1)}>重试连接</button>
        </>}
      </main> :
      <div className="workspace">
        <CatalogPanel catalog={catalog} selection={selection}
          onSelect={selectCase} />
        {catalog.applications.flatMap((app) => app.cases.map((caseCard) =>
          <CaseWorkspace key={`${app.application_id}:${caseCard.case_id}`}
            client={client} app={app} caseCard={caseCard}
            visible={selection.applicationId === app.application_id &&
              selection.caseId === caseCard.case_id}
            onInvalidToken={invalidate} />,
        ))}
      </div>}
  </div>
}
