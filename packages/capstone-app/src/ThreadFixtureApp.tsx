import { useEffect, useMemo, useRef, useState } from 'react'
import { CapstoneThreadClient, type ThreadCommand } from './threadClient'
import { createFixtureTransport, ThreadProjectionStore, type ThreadProjectionState } from './threadProjectionStore'
import { threadUiFixture, type ThreadUiFixture, type ThreadUiFixtureId } from './threadUiFixtures'

const ACTIVE_PHASES = new Set(['created', 'accepted', 'running', 'waiting', 'committing'])

function connectionLabel(state: ThreadProjectionState['connection']): string {
  return { live: '实时连接', reconnecting: '正在重连', resync_required: '需要重新同步', offline: '离线', connecting: '正在连接' }[state]
}

function phaseLabel(phase: string | undefined): string {
  return {
    running: '正在运行', waiting: '等待确认', interrupted: '已中断', cancelled: '已取消',
    completed: '已完成', failed: '执行失败',
  }[phase || ''] || '空闲'
}

function eventLabel(eventType: string): string {
  return {
    grid_page_registered: '已登记电网模型页', grid_page_viewed: '切换到历史电网页',
    attempt_progress: 'Attempt 进度更新', command_accepted: '命令已接收',
  }[eventType] || eventType.replaceAll('_', ' ')
}

function NetworkCanvas({ pageId, historical }: { pageId: string | null; historical: boolean }) {
  return <div className={`thread-network-canvas${historical ? ' is-historical' : ''}`}>
    <svg viewBox="0 0 640 360" role="img" aria-label={`${pageId || '当前'} 电网模型图`}>
      <path className="grid-edge" d="M104 180 L188 94 L310 126 L430 76 L548 162 L470 274 L318 236 L188 274 Z M188 94 L188 274 M310 126 L318 236 M430 76 L470 274 M104 180 L318 236 M548 162 L318 236" />
      <path className="grid-edge grid-edge-active" d="M188 94 L310 126 L430 76" />
      {[['104', '180', 'B01'], ['188', '94', 'B07'], ['310', '126', 'B12'], ['430', '76', 'B19'], ['548', '162', 'B24'], ['470', '274', 'B31'], ['318', '236', 'B27'], ['188', '274', 'B34']].map(([x, y, label]) => <g key={label}>
        <circle className="grid-node" cx={x} cy={y} r="12" /><text x={x} y={Number(y) + 31} textAnchor="middle">{label}</text>
      </g>)}
    </svg>
    <div className="thread-network-legend"><span><i className="legend-dot current" />当前模型投影</span><span><i className="legend-dot muted" />只读历史页</span></div>
  </div>
}

function PageButton({ active, historical, label, onClick }: { active: boolean; historical: boolean; label: string; onClick: () => void }) {
  return <button type="button" className={`thread-page-button${active ? ' is-active' : ''}${historical ? ' is-history' : ''}`} onClick={onClick}>
    <span className="thread-page-index">{active ? '●' : '○'}</span><span>{label}</span>{historical && <small>历史</small>}
  </button>
}

function statusCopy(state: ThreadProjectionState, fixture: ThreadUiFixture): string {
  if (state.connection === 'resync_required') return '服务器与本地事件光标不一致。已冻结命令，必须先重新同步。'
  if (fixture.fixture_id === 'interrupted-attempt') return '上一个 Attempt 已中断；重试会创建新的 Attempt，保留当前证据链。'
  if (fixture.fixture_id === 'historical-live-attempt') return '当前正在查看历史页，但 live Attempt 仍在运行。取消控制始终保留在对话区。'
  return '围绕当前电网模型发送普通指令或专业分析请求。每个命令都会绑定当前 Run 和事件光标。'
}

export default function ThreadFixtureApp({ fixtureId }: { fixtureId: ThreadUiFixtureId }) {
  const fixture = useMemo(() => threadUiFixture(fixtureId), [fixtureId])
  const store = useMemo(() => new ThreadProjectionStore(new CapstoneThreadClient(createFixtureTransport(fixture))), [fixture])
  const [projection, setProjection] = useState<ThreadProjectionState>(store.state)
  const [draft, setDraft] = useState(fixture.local_view.draft)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [reload, setReload] = useState(0)
  const commandNumber = useRef(0)

  useEffect(() => {
    let active = true
    setLoading(true); setError(null); setNotice(null); setDraft(fixture.local_view.draft)
    void (async () => {
      try {
        await store.load('thr_demo_39')
        if (fixture.local_view.viewed_grid_page_id !== 'page_ieee39') store.viewGridPage(fixture.local_view.viewed_grid_page_id)
        if (!store.state.resyncRequired) await store.catchUp()
        if (active) setProjection({ ...store.state, pendingCommands: [...store.state.pendingCommands] })
      } catch (cause) {
        if (active) setError(cause instanceof Error ? cause.message : 'Thread 投影不可用')
      } finally {
        if (active) setLoading(false)
      }
    })()
    return () => { active = false }
  }, [fixture, reload, store])

  const snapshot = projection.snapshot
  const activePage = snapshot?.activeGridPageId || null
  const viewedPage = projection.viewedGridPageId || activePage
  const isHistorical = Boolean(activePage && viewedPage && activePage !== viewedPage)
  const attempt = snapshot?.currentAttempt
  const isActive = Boolean(attempt && ACTIVE_PHASES.has(attempt.phase))
  const isInterrupted = attempt?.phase === 'interrupted'
  const canSendText = projection.connection === 'live' && !isHistorical && !isActive && !isInterrupted && !projection.resyncRequired
  const pages = isHistorical ? ['page_ieee39', 'page_scigrid_2'] : ['page_ieee39']
  const eventDocument = fixture.events && typeof fixture.events === 'object' && !Array.isArray(fixture.events)
    ? fixture.events as Record<string, unknown> : {}
  const fixtureEvents = Array.isArray(eventDocument.events) ? eventDocument.events as Record<string, unknown>[] : []

  function sync() {
    setProjection({ ...store.state, pendingCommands: [...store.state.pendingCommands] })
  }

  async function dispatch(kind: string, payload: Record<string, unknown> = {}) {
    if (!snapshot) return
    commandNumber.current += 1
    const command: ThreadCommand = {
      schema: 'capstone-command/1', command_id: `cmd_ui_${commandNumber.current}`,
      idempotency_key: `idem_ui_${kind}_${commandNumber.current}`, thread_id: snapshot.threadId,
      run_id: snapshot.run.runId, kind, expected_event_seq: projection.eventSeq,
      payload,
    }
    try {
      const receipt = await store.dispatch(command)
      setNotice(`${kind} · ${receipt.status}`); sync()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '命令未提交'); sync()
    }
  }

  function selectPage(pageId: string) {
    store.viewGridPage(pageId); setNotice(pageId === activePage ? '已返回当前模型页' : '已打开只读历史页'); sync()
  }

  function controlButton(label: string, kind: string, enabled: boolean, payload: Record<string, unknown> = {}) {
    return <button type="button" className="thread-control-button" disabled={!enabled} onClick={() => void dispatch(kind, payload)}>{label}</button>
  }

  return <div className="thread-fixture-shell">
    <header className="thread-fixture-topbar">
      <div className="thread-brand"><span className="thread-brand-mark">◆</span><strong>CAPSTONE</strong><span>THREAD WORKSPACE</span></div>
      <div className={`thread-connection is-${projection.connection}`}><i />{connectionLabel(projection.connection)}</div>
    </header>
    {loading ? <main className="thread-loading" aria-live="polite"><span className="spinner" />正在恢复 Thread 投影…</main> : <main className="thread-workspace">
      <h1 className="thread-workspace-title">Thread / IEEE-39</h1>
      <section className="thread-grid-pane" aria-label="电网模型区">
        <div className="thread-pane-heading"><div><span className="eyebrow">MODEL / CURRENT GRID</span><h2>电网模型</h2></div><span className="thread-context-state">{isHistorical ? '历史查看' : '当前'}</span></div>
        <div className="thread-model-card"><div><strong>IEEE-39</strong><span>pandapower · revision 7</span></div><span className="thread-model-badge">{isHistorical ? 'READ ONLY' : 'ACTIVE'}</span></div>
        <div className="thread-page-tabs" aria-label="电网模型分页">
          {pages.map((pageId) => <PageButton key={pageId} active={viewedPage === pageId} historical={pageId !== activePage} label={pageId === 'page_ieee39' ? 'IEEE-39 · 当前模型' : 'SciGrid-2 · 事件历史'} onClick={() => selectPage(pageId)} />)}
        </div>
        <NetworkCanvas pageId={viewedPage} historical={isHistorical} />
        <div className="thread-grid-meta"><div><span>MODEL CONTEXT</span><strong>{snapshot?.activeModelContext.id || '—'}</strong></div><div><span>SELECTION</span><strong>{snapshot?.activeModelContext.selectionRevision || '—'}</strong></div><div><span>EVENT CURSOR</span><strong>#{projection.eventSeq}</strong></div></div>
        {isHistorical && <div className="thread-history-bar"><span>历史页 · 只读视图</span><button type="button" onClick={() => selectPage(activePage || 'page_ieee39')}>返回当前模型</button></div>}
        {fixture.local_view.element_reference && <div className="thread-element-reference"><span>ELEMENT REFERENCE</span><strong>{fixture.local_view.element_reference.element_kind} / {fixture.local_view.element_reference.element_id}</strong><small>{fixture.local_view.element_reference.model_id} · revision {fixture.local_view.element_reference.model_revision}</small></div>}
      </section>
      <section className="thread-conversation-pane" aria-label="Thread 对话区">
        <div className="thread-pane-heading"><div><span className="eyebrow">THREAD / RUN {snapshot?.run.runId || '—'}</span><h2>对话 Thread</h2></div><span className="thread-run-state">{snapshot?.run.state || '—'}</span></div>
        <div className={`thread-state-notice${projection.connection === 'resync_required' ? ' is-danger' : ''}`} role={projection.connection === 'resync_required' ? 'alert' : 'status'}><strong>{projection.connection === 'resync_required' ? '需要重新同步' : phaseLabel(attempt?.phase)}</strong><span>{statusCopy(projection, fixture)}</span></div>
        {error && <div className="thread-inline-error" role="alert">{error}</div>}
        {notice && <div className="thread-inline-notice" role="status">{notice}</div>}
        <div className="thread-events" aria-label="Thread 事件">
          <div className="thread-message is-system"><span className="thread-message-role">SYSTEM · CONTEXT</span><p>当前模型已绑定 <strong>{snapshot?.activeModelContext.implementationFamily}</strong>，工具选择 revision <strong>{snapshot?.activeModelContext.selectionRevision}</strong>。</p></div>
          {fixtureEvents.map((event) => <div className="thread-message" key={String(event.event_id)}><span className="thread-message-role">EVENT · #{String(event.event_seq)}</span><p>{eventLabel(String(event.event_type))}</p><small>来源：capstone-harness · public projection</small></div>)}
          {isInterrupted && <div className="thread-message is-warning"><span className="thread-message-role">ATTEMPT · INTERRUPTED</span><p>本次 Attempt 已中断</p><small>重试将创建新 Attempt，不覆盖旧 Attempt。</small></div>}
        </div>
        <div className="thread-composer">
          <textarea aria-label="Thread 指令" value={draft} onChange={(event) => setDraft(event.target.value)} disabled={!canSendText} placeholder={canSendText ? '围绕当前电网模型输入指令…' : '当前状态暂不可提交新指令'} rows={3} />
          <div className="thread-composer-footer"><span>Cursor #{projection.eventSeq} · Context {snapshot?.activeModelContext.id || '—'}</span><div className="thread-send-actions">{canSendText && <><button type="button" className="thread-secondary-button" onClick={() => void dispatch('send_ordinary', { text: draft })} disabled={!draft.trim()}>发送普通指令</button><button type="button" className="thread-primary-button" onClick={() => void dispatch('send_professional', { text: draft })} disabled={!draft.trim()}>发送专业请求</button></>}</div></div>
        </div>
        <div className="thread-control-row" aria-label="Thread 控制">
          {projection.connection === 'resync_required' ? <>{<button type="button" className="thread-primary-button" onClick={() => setReload((value) => value + 1)}>重新同步</button>}<button type="button" className="thread-secondary-button" onClick={() => setNotice('请检查服务连接与事件游标')}>帮助</button></> : <>
            {isActive && controlButton('取消当前计算', 'cancel_live_attempt', projection.connection === 'live', { attempt_id: attempt?.attemptId })}
            {isInterrupted && controlButton('重试新 Attempt', 'retry_new_attempt', projection.connection === 'live', { turn_id: attempt?.turnId })}
            {isHistorical && <button type="button" className="thread-control-button" onClick={() => selectPage(activePage || 'page_ieee39')}>返回当前模型</button>}
            {(isActive || isInterrupted) && <button type="button" className="thread-control-button" onClick={() => setNotice('回放入口将在真实事件流接入后启用')}>打开回放</button>}
          </>}
        </div>
      </section>
    </main>}
  </div>
}
