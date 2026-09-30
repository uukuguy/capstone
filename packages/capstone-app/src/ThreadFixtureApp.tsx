import { useEffect, useMemo, useRef, useState } from 'react'
import { buildThreadCommand, CapstoneThreadClient, type ThreadCommand } from './threadClient'
import { createFixtureTransport, ThreadProjectionStore, type ThreadProjectionState } from './threadProjectionStore'
import { threadUiFixture, type ThreadUiFixture, type ThreadUiFixtureId } from './threadUiFixtures'
import CapstoneAssistantThread, { projectAssistantActivity } from './CapstoneAssistantThread'
import ThreadModelPane from './ThreadModelPane'
import { threadPreviewDiagram } from './threadModelDiagram'
import type { NetworkDiagram } from './types'
import { PageHeader } from './AppHeader'

const ACTIVE_PHASES = new Set(['created', 'accepted', 'running', 'waiting', 'committing'])

function phaseLabel(phase: string | undefined): string {
  return {
    running: '正在运行', waiting: '等待确认', interrupted: '已中断', cancelled: '已取消',
    completed: '已完成', failed: '执行失败',
  }[phase || ''] || '空闲'
}

function statusCopy(state: ThreadProjectionState, fixture: ThreadUiFixture | null): string {
  if (state.connection === 'resync_required') return '服务器与本地事件光标不一致。已冻结命令，必须先重新同步。'
  if (fixture?.fixture_id === 'interrupted-attempt') return '上一个 Attempt 已中断；重试会创建新的 Attempt，保留当前证据链。'
  if (fixture?.fixture_id === 'historical-live-attempt') return '当前正在查看历史页，但 live Attempt 仍在运行。取消控制始终保留在对话区。'
  return '围绕当前电网模型发送指令或专业分析请求。默认自动识别意图，每个命令都会绑定当前 Run 和事件光标。'
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
  const lastConversationText = [...events].reverse().find((event) => event.eventType === 'command_accepted' && ['send_auto', 'send_ordinary', 'send_professional'].includes(String(event.payload.kind)))
  const lastConversationPayload = lastConversationText?.payload.payload
  const lastConversationInstruction = lastConversationPayload && typeof lastConversationPayload === 'object' && !Array.isArray(lastConversationPayload) && typeof (lastConversationPayload as Record<string, unknown>).text === 'string'
    ? String((lastConversationPayload as Record<string, unknown>).text) : null

  if (!loading && error && !snapshot) {
    return <div className="thread-app-shell"><PageHeader className="thread-page-header" showThreadEntry={false} /><main className="thread-error-shell" role="alert"><h1>Thread 暂时不可用</h1><p>{error}</p><button type="button" className="thread-primary-button" onClick={() => setReload((value) => value + 1)}>重新连接</button></main></div>
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
      const conversational = kind === 'send_auto' || kind === 'send_ordinary' || kind === 'send_professional'
      setNotice(conversational ? null : `${kind} · ${receipt.status}`); sync()
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
    <PageHeader className="thread-page-header" showThreadEntry={false} />
    {loading ? <main className="thread-loading" aria-live="polite"><span className="spinner" />正在恢复 Thread 投影…</main> : snapshot ? <main className="thread-app-main">
      <div className="thread-app-columns">
        <ThreadModelPane snapshot={snapshot} viewedPage={viewedPage || activePage || 'page_ieee39'} activePage={activePage || 'page_ieee39'} isHistorical={isHistorical}
          projectionEventSeq={projection.eventSeq} modelTarget={modelTarget} contextChangePending={contextChangePending}
          controlsDisabled={isHistorical || isActive || contextChangePending || projection.connection !== 'live'} previewDiagram={previewDiagram ?? (fixture ? threadPreviewDiagram : null)}
          elementReference={fixture?.local_view.element_reference} onModelTargetChange={setModelTarget}
          onSwitchModel={() => void dispatch('switch_model', { model_id: modelTarget })} onSelectPage={selectPage} />
        <section className="thread-chat-pane" aria-label="Thread 对话区">
          <div className="thread-chat-heading"><div><span className="eyebrow">THREAD / RUN {snapshot.run.runId}</span><h2>对话 Thread</h2></div><span className="thread-run-state">{snapshot.run.state}</span></div>
          {(projection.connection !== 'live' || contextChangePending || attempt) && <div className={`thread-state-strip${projection.connection === 'resync_required' ? ' is-danger' : ''}`} role={projection.connection === 'resync_required' ? 'alert' : 'status'}><strong>{projection.connection === 'resync_required' ? '需要重新同步' : phaseLabel(attempt?.phase)}</strong><span>{statusCopy(projection, fixture)}</span></div>}
          {error && <div className="thread-inline-error" role="alert">{error}</div>}
          {notice && <div className="thread-inline-notice" role="status">{notice}</div>}
          {isInterrupted && <div className="thread-interrupted-banner" role="status"><strong>本次 Attempt 已中断</strong><span>重试将创建新的 Attempt，不覆盖旧 Attempt。</span></div>}
          <CapstoneAssistantThread events={events} disabled={!canSendText} isRunning={isActive} activity={projectAssistantActivity(events)}
            onSend={async (mode, text) => { await dispatch(mode === 'professional' ? 'send_professional' : 'send_auto', { text }) }}
            onCancel={async () => { await dispatch('cancel_live_attempt', { attempt_id: attempt?.attemptId }) }}
            onRegenerate={async () => { if (lastConversationInstruction) await dispatch('send_auto', { text: lastConversationInstruction }) }} />
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
