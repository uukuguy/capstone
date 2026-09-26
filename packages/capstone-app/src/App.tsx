import { useEffect, useRef, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import { ApiError, CapstoneClient } from './api'
import { runAutomaticSession } from './autoRun'
import { NetworkView } from './NetworkView'
import { parseNetworkView } from './networkValidation'
import type { ApplicationCard, CaseCard, Catalog, CommittedTurn, NetworkView as NetworkViewData, SessionStatus } from './types'

type Selection = { applicationId: string; caseId: string }
type DetailTab = 'overview' | 'evidence'
type Props = { clientFactory?: (token: string) => CapstoneClient }

const stateLabel: Record<SessionStatus['state'], string> = {
  pending: '等待工作进程', ready: '等待指令', executing: '分析中', closing: '整理结果中',
  completed: '已完成', failed: '运行失败', interrupted: '运行中断',
}

function Mark() {
  return <span className="mark" aria-hidden="true"><i /><i /><i /><i /></span>
}

function PageHeader({ connected, onDisconnect }: { connected: boolean; onDisconnect: () => void }) {
  return <header className="topbar">
    <div className="brand"><Mark /><span className="brand-name">CAPSTONE</span><span className="brand-divider" />
      <span className="brand-subtitle">分析工作台</span></div>
    <div className="topbar-right"><span className="product-tag">EVIDENCE-BACKED ANALYSIS</span>
      {connected && <button className="text-button" onClick={onDisconnect}>断开连接</button>}</div>
  </header>
}

function AccessGate({ onConnect, pending, error }: {
  onConnect: (token: string) => Promise<void>; pending: boolean; error: string | null
}) {
  const [value, setValue] = useState('')
  function submit(event: FormEvent) {
    event.preventDefault()
    if (!value.trim()) return
    void onConnect(value.trim()).then(() => setValue(''))
  }
  return <main className="access-shell">
    <div className="access-grid" aria-hidden="true" />
    <section className="access-card" aria-labelledby="access-title">
      <div className="eyebrow"><span className="eyebrow-line" /> OPERATOR ACCESS</div>
      <h1 id="access-title">进入分析工作台</h1>
      <p>选择已登记的应用案例，逐轮查看答案、报告与本次运行证据。</p>
      <form onSubmit={submit}>
        <label htmlFor="operator-token">访问凭证</label>
        <input id="operator-token" type="password" autoComplete="off" value={value}
          onChange={(event) => setValue(event.target.value)} placeholder="输入内部操作员凭证" />
        {error && <p className="form-error" role="alert">{error}</p>}
        <button className="primary-button access-submit" disabled={pending || !value.trim()}>
          {pending ? '正在连接…' : '连接工作台'} <span aria-hidden="true">↗</span>
        </button>
      </form>
      <div className="access-note"><span className="pulse-dot" /> 凭证仅保留在当前标签页内存中</div>
    </section>
    <div className="access-aside" aria-hidden="true"><Mark /><div>CAPABILITY / EVIDENCE / CONTROL</div></div>
  </main>
}

function CatalogPanel({ catalog, selection, onSelect }: {
  catalog: Catalog; selection: Selection | null; onSelect: (value: Selection) => void
}) {
  const total = catalog.applications.reduce((count, app) => count + app.cases.length, 0)
  return <aside className="catalog-panel" aria-label="案例目录">
    <div className="section-heading"><div><span className="eyebrow">WORKSPACE / 01</span><h2>案例库</h2></div>
      <span className="count-pill">{String(total).padStart(2, '0')}</span></div>
    <p className="panel-intro">从已登记的分析任务开始，每一步都保留在同一运行中。</p>
    <div className="application-list">
      {catalog.applications.map((app: ApplicationCard, appIndex) => <section key={app.application_id}>
        <div className="app-label"><span className="app-index">0{appIndex + 1}</span>{app.title}</div>
        <div className="case-list">{app.cases.map((caseCard: CaseCard) => {
          const active = selection?.applicationId === app.application_id && selection.caseId === caseCard.case_id
          return <button key={caseCard.case_id} className={`case-card ${active ? 'is-active' : ''}`}
            aria-current={active ? 'true' : undefined}
            onClick={() => onSelect({ applicationId: app.application_id, caseId: caseCard.case_id })}>
            <span className="case-card-top"><span className="case-card-title">{caseCard.title}</span><span aria-hidden="true">↗</span></span>
            <span className="case-card-summary">{caseCard.summary}</span>
            <span className="case-card-footer"><span>03 个步骤</span><span>已登记案例</span></span>
          </button>
        })}</div>
      </section>)}</div>
    <div className="catalog-footnote"><span className="footnote-rule" />
      所有数值与网络结论均以当前运行的权威结果为准。</div>
  </aside>
}

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return <div className="fact"><span>{label}</span><strong>{children}</strong></div>
}

function AnswerCard({ turn, onEvidence }: {
  turn: CommittedTurn; onEvidence: (ref: string) => void
}) {
  return <div className="answer-card">
    <div className="answer-label"><span className="answer-check">✓</span> 已提交回答</div>
    <p className="answer-text">{turn.answer_output}</p>
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
      <div className="capstone-intro-art">
        <img src="/capstone-science-hero.png" alt="工业专业框架与 AI 智能体应用的连接示意" />
        <div className="capstone-intro-overlay">
          <span className="capstone-intro-kicker">电力科学AI / PHYSICS-DRIVEN AI</span>
          <strong>从专业仿真<br />到智能推演</strong>
          <div className="capstone-intro-frameworks"><span>pandapower</span><span>PyPSA</span></div>
          <div className="capstone-intro-disciplines" aria-label="电力科学AI模型方向">
            <span><b>神经算子</b>DeepONet · FNO</span>
            <span><b>动力学模型</b>Neural-DAE · Koopman</span>
            <span><b>物理图网络</b>GraphGPS · PI-GNN</span>
          </div>
        </div>
      </div>
      <p>CAPSTONE 为电力科学 AI 提供应用底座：把 pandapower、PyPSA 等专业框架封装为统一的领域能力，由智能体组织任务、权威系统完成计算。每一步的结果与证据随运行留存，形成可复用、可核查的分析过程。</p>
    </section>
}

function RunPanel({ app, caseCard, status, turns, progress, actionPending, automatic, onStart,
                    onSubmit, onClose, onAuto, onStopAuto, onEvidence,
                    networkView, networkFocusKey, networkUnavailable, nextNetworkTask,
                    selectedStep, onSelectStep, report, result }: {
  app: ApplicationCard; caseCard: CaseCard; status: SessionStatus | null;
  turns: Record<number, CommittedTurn>; progress: string | null; actionPending: boolean;
  automatic: boolean; onAuto: () => void; onStopAuto: () => void;
  onStart: () => void; onSubmit: () => void; onClose: () => void;
  onEvidence: (ref: string) => void
  networkView: NetworkViewData | null; networkFocusKey: string;
  networkUnavailable: boolean; nextNetworkTask: boolean;
  selectedStep: number | null; onSelectStep: (ordinal: number | null) => void
  report: string | null; result: unknown
}) {
  const next = (status?.completed_turns ?? 0) + 1
  return <main className="run-panel">
    <div className="run-breadcrumb"><span>案例分析</span><span className="breadcrumb-separator">/</span>
      <span>{app.title}</span><span className="breadcrumb-separator">/</span><strong>{caseCard.title}</strong></div>
    <div className="run-title-row"><div>
      <span className="eyebrow">REGISTERED ANALYSIS / 0{caseCard.instructions.length} STEPS</span>
      <h1>{caseCard.title}</h1><p className="run-summary">{caseCard.summary}</p>
    </div><div className="run-title-glyph" aria-hidden="true"><Mark /></div></div>
    <div className="context-strip">
      <Fact label="模型来源">{caseCard.model_origin}</Fact>
      <Fact label="情景假设">{caseCard.scenario_assumption}</Fact>
    </div>
    <div className="boundary-note"><span className="boundary-icon" aria-hidden="true">i</span>
      <div><strong>解释边界</strong><p>{caseCard.interpretation_boundary}</p></div></div>
    <NetworkView view={networkView} modelName={caseCard.model_origin} focusKey={networkFocusKey}
      unavailable={networkUnavailable} nextTask={nextNetworkTask} />
    <div className="timeline-heading"><div><span className="eyebrow">EXECUTION / TIMELINE</span><h2>分析过程</h2></div>
      <div className="timeline-heading-actions">{selectedStep !== null &&
        <button type="button" className="timeline-latest" onClick={() => onSelectStep(null)}>回到最新步骤</button>}
        <span className="timeline-count">{status?.completed_turns ?? 0} / {caseCard.instructions.length} 已完成</span></div></div>
    <ol className="timeline">
      {caseCard.instructions.map((instruction, index) => {
        const ordinal = index + 1
        const answer = turns[ordinal]
        const isNext = status?.state === 'ready' && ordinal === next
        const isExecuting = status?.state === 'executing' && ordinal === next
        return <li key={ordinal} className={`timeline-item ${answer ? 'is-complete' : ''} ${isNext || isExecuting ? 'is-current' : ''}`}>
          {answer ? <button className="timeline-number" type="button"
            aria-label={`查看指令 ${ordinal} 的电网`} aria-pressed={selectedStep === ordinal}
            onClick={() => onSelectStep(ordinal)}>{String(ordinal).padStart(2, '0')}</button>
            : <span className="timeline-number">{String(ordinal).padStart(2, '0')}</span>}
          <div className="timeline-content"><div className="timeline-item-head">{answer
            ? <button type="button" className="timeline-title" aria-pressed={selectedStep === ordinal}
                onClick={() => onSelectStep(ordinal)}>指令 {ordinal}</button>
            : <strong>指令 {ordinal}</strong>}
            <span>{answer ? '已完成' : isExecuting ? '分析中' : isNext ? '下一步' : '待执行'}</span></div>
            <p className="instruction-text">{instruction}</p>
            {answer && <AnswerCard turn={answer} onEvidence={onEvidence} />}
            {isExecuting && <div className="working-line"><span className="spinner" />{progress || '正在执行已登记的分析步骤…'}</div>}
          </div>
        </li>
      })}
    </ol>
    <div className="run-action-bar">
      {!status && <><div><strong>准备开始</strong><span>选择逐步执行，或自动完成全部指令。</span></div>
        <div className="action-buttons"><button className="secondary-button" onClick={onStart} disabled={actionPending}>逐步执行</button>
          <button className="primary-button" onClick={onAuto} disabled={actionPending}>自动完成 <span aria-hidden="true">↗</span></button></div></>}
      {status?.state === 'pending' && <div className="working-line"><span className="spinner" />正在准备当前运行…</div>}
      {status?.state === 'ready' && next <= caseCard.instructions.length && <><div><strong>指令 {next} 已就绪</strong>
        <span>{automatic ? '自动执行会等待本轮回答后继续。' : '可逐步提交，或由系统自动完成剩余步骤。'}</span></div>
        {!automatic && <div className="action-buttons"><button className="secondary-button" onClick={onSubmit} disabled={actionPending}>执行指令 {next}</button>
          <button className="primary-button" onClick={onAuto} disabled={actionPending}>自动完成 <span aria-hidden="true">↗</span></button></div>}</>}
      {status?.state === 'executing' && <div className="working-line"><span className="spinner" />{progress || '正在执行当前指令…'}</div>}
      {status?.state === 'ready' && next > caseCard.instructions.length && <><div><strong>全部指令已完成</strong>
        <span>结束本轮后生成最终结果与报告。</span></div>
        {!automatic && <div className="action-buttons"><button className="primary-button" onClick={onClose} disabled={actionPending}>生成报告 <span aria-hidden="true">↗</span></button></div>}</>}
      {status?.state === 'closing' && <div className="working-line"><span className="spinner" />正在整理本轮结果与报告…</div>}
      {status?.state === 'completed' && <div className="completion-message"><span>✓</span><div><strong>本轮分析已完成</strong>
        <small>{report ? '报告见下方，证据可在右侧查看。' : '已提交答案保留在本次运行中。'}</small></div></div>}
      {(status?.state === 'failed' || status?.state === 'interrupted') && <div className="failure-message"><strong>{stateLabel[status.state]}</strong><span>已提交的回答仍可查看。</span></div>}
      {automatic && <button className="secondary-button stop-auto" onClick={onStopAuto}>停止自动执行</button>}
    </div>
    {report && <section className="run-report" aria-label="本轮分析报告">
      <div className="timeline-heading"><div><span className="eyebrow">CURRENT RUN / REPORT</span><h2>本轮分析报告</h2></div></div>
      <div className="run-report-paper"><ReportDocument report={report} />
        {result !== null && <details className="result-details"><summary>查看结构化结果</summary>
          <pre>{JSON.stringify(result, null, 2)}</pre></details>}</div>
    </section>}
  </main>
}

function ReportDocument({ report }: { report: string }) {
  return <article className="report-document">{report.split('\n').map((raw, index) => {
    const line = raw.replace(/\[([^\]]+)\]\([^)]+\)/g, '$1').replace(/`([^`]+)`/g, '$1')
    if (line.startsWith('### ')) return <h4 key={index}>{line.slice(4)}</h4>
    if (line.startsWith('## ')) return <h3 key={index}>{line.slice(3)}</h3>
    if (line.startsWith('# ')) return <h2 key={index}>{line.slice(2)}</h2>
    if (line.startsWith('- ')) return <p className="report-bullet" key={index}>{line.slice(2)}</p>
    return line ? <p key={index}>{line}</p> : <div className="report-space" key={index} />
  })}</article>
}

function DetailPanel({ status, caseCard, turns, tab, onTab,
                       evidenceRef, evidence, evidencePending }: {
  status: SessionStatus | null; caseCard: CaseCard; turns: Record<number, CommittedTurn>;
  tab: DetailTab; onTab: (tab: DetailTab) => void;
  evidenceRef: string | null; evidence: unknown; evidencePending: boolean
}) {
  const refs = Object.values(turns).flatMap((turn) => turn.evidence_refs)
  const uniqueRefs = [...new Set(refs)]
  return <aside className="detail-panel" aria-label="运行详情">
    <div className="section-heading"><div><span className="eyebrow">CURRENT RUN / 02</span><h2>运行详情</h2></div>
      <span className={`status-led ${status?.state || 'idle'}`} />
    </div>
    <div className="detail-tabs" role="tablist" aria-label="详情视图">
      {([['overview', '概览'], ['evidence', '证据']] as const).map(([value, label]) =>
        <button key={value} role="tab" aria-selected={tab === value} onClick={() => onTab(value)}>{label}</button>)}
    </div>
    {tab === 'overview' && <div className="detail-body">
      <div className="status-card"><span className="detail-label">运行状态</span>
        <strong>{status ? stateLabel[status.state] : '尚未开始'}</strong>
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
  const [tab, setTab] = useState<DetailTab>('overview')
  const [evidenceRef, setEvidenceRef] = useState<string | null>(null)
  const [evidence, setEvidence] = useState<unknown>(null)
  const [evidencePending, setEvidencePending] = useState(false)
  const [networkViews, setNetworkViews] = useState<Record<number, NetworkViewData>>({})
  const [unavailableViews, setUnavailableViews] = useState<number[]>([])
  const [selectedStep, setSelectedStep] = useState<number | null>(null)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [automatic, setAutomatic] = useState(false)
  const autoController = useRef<AbortController | null>(null)
  const automaticKeys = useRef(new Map<string, string>())

  useEffect(() => () => autoController.current?.abort(), [])

  function stopAutomatic() {
    autoController.current?.abort()
    autoController.current = null
    setAutomatic(false)
  }

  function clearRun() {
    stopAutomatic()
    setSessionId(null); setStatus(null); setTurns({}); setProgress(null)
    setReport(null); setResult(null); setEvidenceRef(null); setEvidence(null); setTab('overview')
    setNetworkViews({}); setUnavailableViews([]); setSelectedStep(null)
  }

  useEffect(() => {
    if (!client || !sessionId) return
    const controller = new AbortController()
    let cursor = 0
    const admittedByOrdinal = new Map<number, string[]>()
    const sid = sessionId
    async function complete() {
      const outcomes = await Promise.allSettled([client!.report(sid), client!.result(sid)])
      if (controller.signal.aborted) return
      if (outcomes[0].status === 'fulfilled') setReport(outcomes[0].value)
      if (outcomes[1].status === 'fulfilled') setResult(outcomes[1].value)
    }
    async function run() {
      while (!controller.signal.aborted) {
        try {
          for await (const event of client!.events(sid, cursor, controller.signal)) {
            if (controller.signal.aborted) return
            cursor = event.sequence
            if (event.event === 'ready') {
              setStatus((before) => before && { ...before, state: 'ready',
                run_id: typeof event.payload.run_id === 'string' ? event.payload.run_id : before.run_id })
            } else if (event.event === 'progress') {
              setProgress(typeof event.payload.message === 'string' ? event.payload.message : null)
            } else if (event.event === 'answer_committed') {
              const answer = event.payload as CommittedTurn
              admittedByOrdinal.set(answer.ordinal, Array.isArray(answer.result_refs) ? answer.result_refs : [])
              setTurns((before) => ({ ...before, [answer.ordinal]: answer }))
              setStatus((before) => before && { ...before, state: 'ready',
                completed_turns: answer.ordinal, accepted_turns: answer.ordinal })
              setProgress(null)
              setSelectedStep(null)
            } else if (event.event === 'network_view' || event.event === 'network_layer') {
              const ordinal = event.payload.ordinal
              if (Number.isInteger(ordinal) && Number(ordinal) >= 1 && Number(ordinal) <= 3) {
                try {
                  const raw = await client!.network(sid, Number(ordinal))
                  if (controller.signal.aborted) return
                  const view = parseNetworkView(raw, Number(ordinal),
                    admittedByOrdinal.get(Number(ordinal)) || [])
                  if (view) {
                    setNetworkViews((before) => ({ ...before, [view.ordinal]: view }))
                  } else {
                    setUnavailableViews((before) => [...new Set([...before, Number(ordinal)])])
                  }
                } catch {
                  // A missing optional view cannot veto the committed answer.
                  setUnavailableViews((before) => [...new Set([...before, Number(ordinal)])])
                }
              }
            } else if (event.event === 'network_view_unavailable' || event.event === 'network_layer_unavailable') {
              const ordinal = event.payload.ordinal
              if (Number.isInteger(ordinal) && Number(ordinal) >= 1 && Number(ordinal) <= 3) {
                setUnavailableViews((before) => [...new Set([...before, Number(ordinal)])])
              }
            } else if (event.event === 'completed') {
              setStatus((before) => before && { ...before, state: 'completed' })
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
          if (current.state === 'completed') { await complete(); return }
          if (current.state === 'failed' || current.state === 'interrupted') return
        } catch (cause) {
          if (controller.signal.aborted) return
          if (cause instanceof ApiError && cause.status === 401) {
            clearRun()
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
    if (!client || !app || !caseCard) return
    setPending(true); setError(null); clearRun()
    try {
      const created = await client.createSession(app.application_id, caseCard.case_id)
      setStatus({ ...created, error_code: null, accepted_turns: 0, completed_turns: 0 })
      setSessionId(created.session_id)
    } catch (cause) { setError(cause instanceof Error ? cause.message : '启动失败') }
    finally { setPending(false) }
  }

  function startAutomatic() {
    if (!client || !app || !caseCard || autoController.current) return
    const existingSessionId = sessionId
    if (!existingSessionId) clearRun()
    const controller = new AbortController()
    autoController.current = controller
    setAutomatic(true); setError(null)
    void runAutomaticSession(
      client, app.application_id, caseCard.case_id,
      caseCard.instructions, existingSessionId, controller.signal, automaticKeys.current,
      (created) => {
        setStatus({ ...created, error_code: null, accepted_turns: 0, completed_turns: 0 })
        setSessionId(created.session_id)
      },
      (current) => setStatus((before) => before && before.session_id === current.session_id &&
        (before.completed_turns > current.completed_turns || before.accepted_turns > current.accepted_turns)
        ? before : current),
    ).then(async (sid) => {
      if (controller.signal.aborted || !autoController.current) return
      const current = await client.status(sid)
      if (current.state === 'completed') {
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
    setPending(true); setError(null)
    try {
      await client.submitTurn(sessionId, instruction, crypto.randomUUID())
      setStatus((before) => before && before.completed_turns < ordinal
        ? { ...before, state: 'executing', accepted_turns: ordinal } : before)
    } catch (cause) { setError(cause instanceof Error ? cause.message : '提交失败') }
    finally { setPending(false) }
  }

  async function close() {
    if (!client || !sessionId) return
    setPending(true); setError(null)
    try {
      await client.close(sessionId, crypto.randomUUID())
      setStatus((before) => before && before.state !== 'completed'
        ? { ...before, state: 'closing' } : before)
    } catch (cause) { setError(cause instanceof Error ? cause.message : '结束失败') }
    finally { setPending(false) }
  }

  async function showEvidence(ref: string) {
    if (!client || !sessionId) return
    setEvidenceRef(ref); setEvidence(null); setEvidencePending(true); setTab('evidence')
    try { setEvidence(await client.evidence(sessionId, ref)) }
    catch { setEvidence(null) }
    finally { setEvidencePending(false) }
  }

  const displayedOrdinal = selectedStep ?? status?.completed_turns ?? 0
  const exactNetworkView = displayedOrdinal > 0 ? networkViews[displayedOrdinal] ?? null : null
  const previousOrdinal = Object.keys(networkViews).map(Number).filter((ordinal) => ordinal < displayedOrdinal)
    .sort((a, b) => b - a)[0]
  const previousNetworkView = previousOrdinal === undefined ? null : networkViews[previousOrdinal]
  const networkView: NetworkViewData | null = exactNetworkView || (previousNetworkView?.schema === 'capstone-network-view/2.0'
    ? { ...previousNetworkView, ordinal: displayedOrdinal,
      layer: { ...previousNetworkView.layer, ordinal: displayedOrdinal, focus_ids: [], next_focus_ids: [], overlay: null } }
    : previousNetworkView ? { ...previousNetworkView, ordinal: displayedOrdinal,
      focus_ids: [], next_focus_ids: [], overlay: null } : null)
  const networkFocusKey = `${sessionId ?? 'idle'}:${displayedOrdinal}:${status?.state ?? 'new'}`
  const nextNetworkTask = selectedStep === null && status?.state === 'executing' && displayedOrdinal > 0
  const networkUnavailable = displayedOrdinal > 0 && unavailableViews.includes(displayedOrdinal) && !networkView

  return <div style={{ display: visible ? 'contents' : 'none' }}>
    <div className="workspace-center">
      {error && <div className="workspace-alert" role="alert">{error}</div>}
      <CapstoneIntro />
      <RunPanel app={app} caseCard={caseCard} status={status}
        turns={turns} progress={progress} actionPending={pending} automatic={automatic}
        networkView={networkView} networkFocusKey={networkFocusKey}
        networkUnavailable={networkUnavailable} nextNetworkTask={nextNetworkTask}
        selectedStep={selectedStep} onSelectStep={setSelectedStep}
        report={report} result={result}
        onStart={() => void start()} onSubmit={() => void submit()} onClose={() => void close()}
        onAuto={startAutomatic} onStopAuto={stopAutomatic}
        onEvidence={(ref) => void showEvidence(ref)} />
    </div>
    <DetailPanel status={status} caseCard={caseCard} turns={turns}
      tab={tab} onTab={setTab}
      evidenceRef={evidenceRef} evidence={evidence} evidencePending={evidencePending} />
  </div>
}

export default function App({ clientFactory = (token) => new CapstoneClient(
  import.meta.env.VITE_API_ORIGIN || '', token,
) }: Props) {
  const [client, setClient] = useState<CapstoneClient | null>(null)
  const [catalog, setCatalog] = useState<Catalog | null>(null)
  const [selection, setSelection] = useState<Selection | null>(null)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function connect(token: string) {
    setPending(true); setError(null)
    try {
      const nextClient = clientFactory(token)
      const nextCatalog = await nextClient.catalog()
      if (nextCatalog.schema !== 'capstone-catalog/1.0' || !nextCatalog.applications.length) {
        throw new Error('案例目录不可用')
      }
      const firstApp = nextCatalog.applications.find((item) => item.cases.length)
      if (!firstApp) throw new Error('没有可运行的案例')
      setCatalog(nextCatalog); setClient(nextClient)
      setSelection({ applicationId: firstApp.application_id, caseId: firstApp.cases[0].case_id })
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '连接失败')
    } finally { setPending(false) }
  }

  function disconnect(message: string | null = null) {
    setClient(null); setCatalog(null); setSelection(null); setError(message)
  }

  return <div className="app-shell">
    <PageHeader connected={!!client} onDisconnect={() => disconnect()} />
    {!client || !catalog || !selection ?
      <AccessGate onConnect={connect} pending={pending} error={error} /> :
      <div className="workspace">
        <CatalogPanel catalog={catalog} selection={selection}
          onSelect={setSelection} />
        {catalog.applications.flatMap((app) => app.cases.map((caseCard) =>
          <CaseWorkspace key={`${app.application_id}:${caseCard.case_id}`}
            client={client} app={app} caseCard={caseCard}
            visible={selection.applicationId === app.application_id &&
              selection.caseId === caseCard.case_id}
            onInvalidToken={disconnect} />,
        ))}
      </div>}
  </div>
}
