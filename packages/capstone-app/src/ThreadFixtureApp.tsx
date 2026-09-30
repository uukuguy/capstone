import { useEffect, useMemo, useRef, useState } from 'react'
import { buildThreadCommand, CapstoneThreadClient, type ThreadCommand } from './threadClient'
import { createFixtureTransport, ThreadProjectionStore, type ThreadProjectionState } from './threadProjectionStore'
import { threadUiFixture, type ThreadUiFixture, type ThreadUiFixtureId } from './threadUiFixtures'
import CapstoneAssistantThread from './CapstoneAssistantThread'
import ThreadModelPane from './ThreadModelPane'
import { threadPreviewDiagram } from './threadModelDiagram'
import type { NetworkDiagram } from './types'

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
    model_context_change_pending: '模型切换已挂起', model_context_activated: '模型上下文已激活',
    model_context_reverted: '模型切换已回滚', selection_change_pending: '能力选择已挂起',
  }[eventType] || eventType.replaceAll('_', ' ')
}

function modelLabel(modelId: string | undefined): string {
  return { ieee39: 'IEEE-39', pypsa39: 'PyPSA-39' }[modelId || ''] || modelId || '当前模型'
}

function statusCopy(state: ThreadProjectionState, fixture: ThreadUiFixture | null): string {
  if (state.connection === 'resync_required') return '服务器与本地事件光标不一致。已冻结命令，必须先重新同步。'
  if (fixture?.fixture_id === 'interrupted-attempt') return '上一个 Attempt 已中断；重试会创建新的 Attempt，保留当前证据链。'
  if (fixture?.fixture_id === 'historical-live-attempt') return '当前正在查看历史页，但 live Attempt 仍在运行。取消控制始终保留在对话区。'
  return '围绕当前电网模型发送普通指令或专业分析请求。每个命令都会绑定当前 Run 和事件光标。'
}

export type ThreadWorkspaceProps = {
  fixtureId?: ThreadUiFixtureId
  client?: CapstoneThreadClient
  threadId?: string
  previewDiagram?: NetworkDiagram | null
}

export default function ThreadFixtureApp({ fixtureId, client, threadId: requestedThreadId, previewDiagram }: ThreadWorkspaceProps) {
  const fixture = useMemo(() => fixtureId ? threadUiFixture(fixtureId) : null, [fixtureId])
  const store = useMemo(() => {
    if (client) return new ThreadProjectionStore(client)
    if (fixture) return new ThreadProjectionStore(new CapstoneThreadClient(createFixtureTransport(fixture)))
    throw new Error('Thread workspace requires a client or fixture')
  }, [client, fixture])
  const threadId = requestedThreadId || (fixture ? String((fixture.snapshot as { thread_id: string }).thread_id) : '')
  const [projection, setProjection] = useState<ThreadProjectionState>(store.state)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [reload, setReload] = useState(0)
  const [modelTarget, setModelTarget] = useState('pypsa39')
  const commandNumber = useRef(0)

  useEffect(() => {
    let active = true
    const abort = new AbortController()
    const unsubscribe = store.subscribe(() => {
      if (active) setProjection({ ...store.state, pendingCommands: [...store.state.pendingCommands] })
    })
    setLoading(true); setError(null); setNotice(null)
    void (async () => {
      try {
        await store.load(threadId)
        if (fixture?.local_view.viewed_grid_page_id && fixture.local_view.viewed_grid_page_id !== store.state.snapshot?.activeGridPageId) {
          store.viewGridPage(fixture.local_view.viewed_grid_page_id)
        }
        if (!store.state.resyncRequired) await store.catchUp()
        if (active) setProjection({ ...store.state, pendingCommands: [...store.state.pendingCommands] })
        if (active && store.canStreamEvents) {
          void store.consumeEvents(abort.signal).catch((cause) => {
            if (active && !(cause instanceof DOMException && cause.name === 'AbortError')) {
              setError(cause instanceof Error ? cause.message : 'Thread 事件流不可用')
            }
          })
        }
      } catch (cause) {
        if (active) setError(cause instanceof Error ? cause.message : 'Thread 投影不可用')
      } finally {
        if (active) setLoading(false)
      }
    })()
    return () => { active = false; abort.abort(); unsubscribe() }
  }, [fixture, reload, store, threadId])

  const snapshot = projection.snapshot
  const activePage = snapshot?.activeGridPageId || null
  const viewedPage = projection.viewedGridPageId || activePage
  const isHistorical = Boolean(activePage && viewedPage && activePage !== viewedPage)
  const attempt = snapshot?.currentAttempt
  const isActive = Boolean(attempt && ACTIVE_PHASES.has(attempt.phase))
  const isInterrupted = attempt?.phase === 'interrupted'
  const contextChangePending = Boolean(snapshot?.pendingModelSwitch || snapshot?.pendingSelection)
  const canSendText = projection.connection === 'live' && !isHistorical && !isActive && !isInterrupted && !projection.resyncRequired
  const events = store.publicEvents

  if (!loading && error && !snapshot) {
    return <div className="thread-fixture-shell"><header className="thread-fixture-topbar">
      <div className="thread-brand"><span className="thread-brand-mark">◆</span><strong>CAPSTONE</strong><span>THREAD WORKSPACE</span></div>
      <div className="thread-connection is-offline"><i />连接失败</div>
    </header><main className="thread-error-shell" role="alert"><h1>Thread 暂时不可用</h1><p>{error}</p><button type="button" className="thread-primary-button" onClick={() => setReload((value) => value + 1)}>重新连接</button></main></div>
  }

  function sync() {
    setProjection({ ...store.state, pendingCommands: [...store.state.pendingCommands] })
  }

  async function dispatch(kind: string, payload: Record<string, unknown> = {}) {
    if (!snapshot) return
    commandNumber.current += 1
    const command: ThreadCommand = buildThreadCommand({
      threadId: snapshot.threadId, runId: snapshot.run.runId, kind,
      expectedEventSeq: projection.eventSeq, commandId: `cmd_ui_${commandNumber.current}`,
      idempotencyKey: `idem_ui_${kind}_${commandNumber.current}`, payload,
    })
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

  return <div className="thread-app-shell">
    <header className="thread-app-topbar">
      <div className="thread-app-brand"><span className="thread-app-mark" aria-hidden="true"><i /><i /><i /><i /></span><strong>CAPSTONE</strong><span>THREAD WORKSPACE</span></div>
      <div className={`thread-app-connection is-${projection.connection}`}><i />{connectionLabel(projection.connection)}</div>
    </header>
    {loading ? <main className="thread-loading" aria-live="polite"><span className="spinner" />正在恢复 Thread 投影…</main> : snapshot ? <main className="thread-app-main">
      <div className="thread-app-title"><div><span className="eyebrow">CAPSTONE / AGENT WORKSPACE</span><h1>Thread / {modelLabel(snapshot.activeModelContext.modelId)}</h1></div><span className="thread-run-chip">RUN {snapshot.run.runId}</span></div>
      <div className="thread-app-columns">
        <ThreadModelPane snapshot={snapshot} viewedPage={viewedPage || activePage || 'page_ieee39'} activePage={activePage || 'page_ieee39'} isHistorical={isHistorical}
          projectionEventSeq={projection.eventSeq} modelTarget={modelTarget} contextChangePending={contextChangePending}
          controlsDisabled={isHistorical || isActive || contextChangePending || projection.connection !== 'live'} previewDiagram={previewDiagram ?? (fixture ? threadPreviewDiagram : null)}
          elementReference={fixture?.local_view.element_reference} onModelTargetChange={setModelTarget}
          onSwitchModel={() => void dispatch('switch_model', { model_id: modelTarget })} onSelectPage={selectPage} />
        <section className="thread-chat-pane" aria-label="Thread 对话区">
          <div className="thread-chat-heading"><div><span className="eyebrow">THREAD / RUN {snapshot.run.runId}</span><h2>对话 Thread</h2></div><span className="thread-run-state">{snapshot.run.state}</span></div>
          <div className={`thread-state-notice${projection.connection === 'resync_required' ? ' is-danger' : ''}`} role={projection.connection === 'resync_required' ? 'alert' : 'status'}><strong>{projection.connection === 'resync_required' ? '需要重新同步' : phaseLabel(attempt?.phase)}</strong><span>{statusCopy(projection, fixture)}</span></div>
          {error && <div className="thread-inline-error" role="alert">{error}</div>}
          {notice && <div className="thread-inline-notice" role="status">{notice}</div>}
          {isInterrupted && <div className="thread-interrupted-banner" role="status"><strong>本次 Attempt 已中断</strong><span>重试将创建新的 Attempt，不覆盖旧 Attempt。</span></div>}
          <CapstoneAssistantThread events={events} disabled={!canSendText} isRunning={isActive} activity={events.filter((event) => ['tool_started', 'tool_completed', 'attempt_progress'].includes(event.eventType)).map((event) => `${eventLabel(event.eventType)} · capstone-harness`)}
            onSend={async (mode, text) => { await dispatch(mode === 'professional' ? 'send_professional' : 'send_ordinary', { text }) }}
            onCancel={async () => { await dispatch('cancel_live_attempt', { attempt_id: attempt?.attemptId }) }} />
          <div className="thread-control-row" aria-label="Thread 控制">
            {projection.connection === 'resync_required' ? <><button type="button" className="thread-primary-button" onClick={() => setReload((value) => value + 1)}>重新同步</button><button type="button" className="thread-secondary-button" onClick={() => setNotice('请检查服务连接与事件游标')}>帮助</button></> : projection.connection === 'reconnecting' ? <><button type="button" className="thread-primary-button" onClick={() => setReload((value) => value + 1)}>重新连接</button><button type="button" className="thread-secondary-button" onClick={() => setNotice('实时事件流暂时中断，Thread 状态仍保留。')}>帮助</button></> : <>
              {isActive && controlButton('取消当前计算', 'cancel_live_attempt', projection.connection === 'live', { attempt_id: attempt?.attemptId })}
              {isInterrupted && controlButton('重试新 Attempt', 'retry_new_attempt', projection.connection === 'live', { turn_id: attempt?.turnId })}
              {isHistorical && <button type="button" className="thread-control-button" onClick={() => selectPage(activePage || 'page_ieee39')}>返回当前模型</button>}
              {(isActive || isInterrupted) && <button type="button" className="thread-control-button" onClick={() => setNotice('回放入口将在真实事件流接入后启用')}>打开回放</button>}
            </>}
          </div>
        </section>
      </div>
    </main> : null}
  </div>
}
