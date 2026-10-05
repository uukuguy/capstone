import { useEffect, useMemo, useRef, useState } from 'react'
import { MessageNotSentError } from '@assistant-ui/react'
import { buildThreadCommand, CapstoneThreadClient, type ThreadCommand } from './threadClient'
import { createFixtureTransport, instructionOrdinal, ThreadProjectionStore, type ThreadProjectionState } from './threadProjectionStore'
import { threadUiFixture, type ThreadUiFixture, type ThreadUiFixtureId } from './threadUiFixtures'
import CapstoneAssistantThread, { projectAssistantActivity } from './CapstoneAssistantThread'
import ThreadModelPane from './ThreadModelPane'
import ThreadModelDirectory, { modelUnavailableCopy } from './ThreadModelDirectory'
import { commandRejectionCopy } from './threadFeedback'
import { threadPreviewDiagram } from './threadModelDiagram'
import type { DiagramNetworkView, NetworkDiagram } from './types'
import type { ResultProjection } from './threadProtocol'
import { PageHeader } from './AppHeader'
import ThreadControls from './ThreadControls'
import { parseThreadModelCommand, resolveThreadModelCommandReference } from './threadCatalog'
import { commandKey } from './commandKey'

const ACTIVE_PHASES = new Set(['created', 'accepted', 'running', 'waiting', 'committing'])

function phaseLabel(phase: string | undefined): string {
  return {
    running: '正在运行', waiting: '等待确认', interrupted: '已中断', cancelled: '已取消',
    completed: '已完成', failed: '执行失败',
  }[phase || ''] || '空闲'
}

function connectionLabel(connection: ThreadProjectionState['connection']): string {
  return connection === 'live' ? '实时连接' : connection === 'reconnecting' ? '重连中' : connection === 'resync_required' ? '需重同步' : connection === 'connecting' ? '连接中' : '离线'
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
  const [diagnosticsOpen, setDiagnosticsOpen] = useState(false)
  const [modelTarget, setModelTarget] = useState('ieee39')
  const [traceVisible, setTraceVisible] = useState(true)
  const [focusedElement, setFocusedElement] = useState<{ resultId: string; modelId: string; modelRevision: string; elementId: string }>()
  const [selectedNetworkAttempt, setSelectedNetworkAttempt] = useState<string>()
  const commandInFlight = useRef(false)
  const [sending, setSending] = useState(false)

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
        // React StrictMode mounts effects twice in development. An old load
        // must not continue into catch-up and race the active projection.
        if (!active) return
        if (fixture?.local_view.viewed_grid_page_id && fixture.local_view.viewed_grid_page_id !== store.state.snapshot?.activeGridPageId) {
          store.viewGridPage(fixture.local_view.viewed_grid_page_id)
        }
        if (!store.state.resyncRequired) {
          await store.catchUp()
          if (!active) return
        }
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
  useEffect(() => {
    if (snapshot) setModelTarget(snapshot.activeModelContext.modelId)
  }, [snapshot?.activeModelContext.modelId])
  const activePage = snapshot?.activeGridPageId || null
  const selectedNetworkTask = store.networkTasks.find((task) => task.attemptId === selectedNetworkAttempt)
  const viewedPage = selectedNetworkTask?.pageId || projection.viewedGridPageId || activePage
  const isHistorical = Boolean(activePage && viewedPage && (activePage !== viewedPage ||
    (selectedNetworkTask && selectedNetworkTask.context.id !== snapshot?.activeModelContext.id)))
  const activeNetworkView: DiagramNetworkView | null = !isHistorical ? selectedNetworkTask?.view || projection.networkView : null
  const displayedGridPages = selectedNetworkTask ? projection.gridPages.map((page) =>
    page.pageId === selectedNetworkTask.pageId ? { ...page, context: selectedNetworkTask.context, networkView: selectedNetworkTask.view } : page) : projection.gridPages
  const currentDiagram = activeNetworkView?.diagram ?? previewDiagram ?? (fixture ? threadPreviewDiagram : null)
  const currentDiagramElementIds = useMemo(() => new Set(
    currentDiagram ? [
      ...currentDiagram.buses.map((item) => item.id),
      ...currentDiagram.branches.map((item) => item.id),
    ] : [],
  ), [currentDiagram])
  const attempt = snapshot?.currentAttempt
  const isActive = Boolean(attempt && ACTIVE_PHASES.has(attempt.phase))
  const isInterrupted = attempt?.phase === 'interrupted'
  const contextChangePending = Boolean(snapshot?.pendingModelSwitch || snapshot?.pendingSelection)
  const caseExecution = snapshot?.applicationState?.caseExecution ?? null
  const displayedCaseExecution = caseExecution && isHistorical ? { ...caseExecution,
    actions: caseExecution.actions.map((action) => ({ ...action,
      enabled: action.enabled && (action.actionId === 'cancel_case' || action.actionId === 'view_case_details'),
    })),
  } : caseExecution
  const caseActive = Boolean(caseExecution && ['created', 'running', 'waiting_step', 'blocked'].includes(caseExecution.status))
  const canSendText = projection.connection === 'live' && !isHistorical && !isActive && !isInterrupted && !caseActive && !sending && !projection.resyncRequired
  const canRetry = projection.connection === 'live' && !isHistorical && !isActive && !caseActive && !sending && !projection.resyncRequired
  const modelOptions = useMemo(() => {
    const fromCatalog = projection.catalog?.models || []
    const active = snapshot ? {
      modelId: snapshot.activeModelContext.modelId,
      authorityModelRef: snapshot.activeModelContext.modelId,
      displayName: snapshot.activeModelContext.modelId,
      diagramProviderId: snapshot.activeModelContext.implementationFamily,
      implementationFamily: snapshot.activeModelContext.implementationFamily,
    } : null
    if (!active || fromCatalog.some((model) => model.modelId === active.modelId)) return fromCatalog
    return [active, ...fromCatalog]
  }, [projection.catalog?.models, snapshot])
  const events = store.publicEvents
  const networkTask = events.slice().reverse().find((event) =>
    ['network_layer', 'network_layer_unavailable'].includes(event.eventType) &&
    event.modelContextId === snapshot?.activeModelContext.id)
  const displayedTaskId = selectedNetworkTask?.attemptId || networkTask?.attemptId
  const instructionNumber = instructionOrdinal(events, displayedTaskId)
  const resultContext = selectedNetworkTask?.context || snapshot?.activeModelContext
  const activeResultProjection = snapshot?.resultProjections?.slice().reverse().find((item) =>
    item.modelContextId === resultContext?.id && item.modelId === resultContext.modelId && item.modelRevision === resultContext.modelRevision &&
    (!(selectedNetworkTask?.attemptId || networkTask?.attemptId) || item.attemptId === (selectedNetworkTask?.attemptId || networkTask?.attemptId)))
  const focusedProjection = focusedElement && snapshot?.resultProjections?.find((item) => item.resultId === focusedElement.resultId)
  const focusedElementId = focusedProjection && focusedProjection.modelContextId === snapshot?.activeModelContext.id && focusedProjection.modelId === snapshot.activeModelContext.modelId && focusedProjection.modelRevision === snapshot.activeModelContext.modelRevision
    ? focusedElement.elementId : undefined
  const displayedResultProjection = focusedElementId ? focusedProjection : activeResultProjection
  if (!loading && error && !snapshot) {
    return <div className="thread-app-shell"><PageHeader className="thread-page-header" showThreadEntry={false} /><main className="thread-error-shell" role="alert"><h1>Thread 暂时不可用</h1><p>{error}</p><button type="button" className="thread-primary-button" onClick={() => setReload((value) => value + 1)}>重新连接</button></main></div>
  }

  function sync() {
    setProjection({ ...store.state, pendingCommands: [...store.state.pendingCommands] })
  }

  async function dispatch(kind: string, payload: Record<string, unknown> = {}, successNotice?: string) {
    const latest = store.state.snapshot
    if (!latest) return
    const conversational = kind === 'send_auto' || kind === 'send_ordinary' || kind === 'send_professional'
    const initialCursor = store.state.eventSeq
    const contextIdentity = () => JSON.stringify([
      store.state.snapshot?.run, store.state.snapshot?.activeModelContext,
      store.state.snapshot?.pendingModelSwitch, store.state.snapshot?.pendingSelection,
      store.state.viewedGridPageId,
    ])
    const initialIdentity = contextIdentity()
    const makeCommand = (): ThreadCommand => {
      const current = store.state.snapshot!
      const key = commandKey()
      return buildThreadCommand({
        threadId: current.threadId, runId: current.run.runId, kind,
        expectedEventSeq: store.state.eventSeq, commandId: `cmd_ui_${key}`,
        idempotencyKey: `idem_ui_${key}`, payload,
      })
    }
    try {
      let receipt = await store.dispatch(makeCommand())
      if (receipt.status === 'rejected' && receipt.rejection === 'stale_event_seq') {
        // A definitive rejection created no turn. Restore missing events;
        // retry once only when the user's model and selection are unchanged.
        await store.catchUpThrough(store.state.eventSeq)
        const current = store.state.snapshot
        const phase = current?.currentAttempt?.phase
        const caseStatus = current?.applicationState?.caseExecution?.status
        if (conversational && store.state.eventSeq > initialCursor && contextIdentity() === initialIdentity
            && current?.run.state === 'open' && (!phase || (!ACTIVE_PHASES.has(phase) && phase !== 'interrupted'))
            && !['created', 'running', 'waiting_step', 'blocked'].includes(caseStatus || '')) {
          receipt = await store.dispatch(makeCommand())
        }
      }
      const receiptNotice = receipt.status === 'accepted'
        ? successNotice || '操作已提交。'
        : commandRejectionCopy(receipt.rejection)
      setNotice(conversational && receipt.status === 'accepted' ? null : receiptNotice); sync()
      if (receipt.status === 'accepted') {
        setError(null)
        if (conversational || kind === 'retry_new_attempt') {
          setFocusedElement(undefined)
          setSelectedNetworkAttempt(undefined)
        }
      }
      return receipt
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '命令未提交'); sync()
    }
  }

  function selectPage(pageId: string) {
    setSelectedNetworkAttempt(undefined)
    setFocusedElement(undefined)
    store.viewGridPage(pageId); setNotice(pageId === activePage ? '已返回当前模型页' : '已打开只读历史页'); sync()
  }

  function caseIdentity(): string | undefined {
    const steps = caseExecution?.steps || []
    for (const step of steps) {
      const value = step.details.case_execution_id
      if (typeof value === 'string' && value) return value
    }
    return undefined
  }

  function caseAction(actionId: 'retry_case_step' | 'cancel_case' | 'start_case' | 'view_case_details'): void {
    if (actionId === 'view_case_details' || actionId === 'start_case') return
    if (!caseExecution || !snapshot) return
    const executionId = caseIdentity()
    if (!executionId) {
      setNotice('案例身份尚未同步，请稍后重试')
      return
    }
    if (actionId === 'cancel_case') {
      void dispatch('cancel_case_execution', { case_execution_id: executionId })
      return
    }
    const ordinal = caseExecution.currentStep
    const step = ordinal ? caseExecution.steps[ordinal - 1] : undefined
    const failedAttemptId = step?.details.attempt_id || step?.details.failed_attempt_id
    if (!ordinal || typeof failedAttemptId !== 'string') {
      setNotice('案例步骤身份尚未同步，请稍后重试')
      return
    }
    void dispatch('retry_case_step', { case_execution_id: executionId, step_ordinal: ordinal, failed_attempt_id: failedAttemptId })
  }

  function startCase(caseId: string, caseVersion: string): void {
    void dispatch('start_case_execution', { case_id: caseId, case_version: caseVersion, strategy_id: 'sequential_batch' })
  }

  async function sendConversation(mode: 'automatic' | 'ordinary' | 'professional', text: string): Promise<void> {
    if (commandInFlight.current || isHistorical) throw new MessageNotSentError('当前页面不可发送，请返回当前模型后重试。')
    commandInFlight.current = true
    setSending(true)
    try {
      await selectModelAndSend(mode, text)
    } catch (cause) {
      if (cause instanceof MessageNotSentError) throw cause
      setError(cause instanceof Error ? cause.message : '指令未发送')
      throw new MessageNotSentError('指令未发送，请检查页面提示后重试。')
    } finally {
      commandInFlight.current = false
      setSending(false)
    }
  }

  async function selectModelAndSend(mode: 'automatic' | 'ordinary' | 'professional', text: string): Promise<void> {
    const intent = parseThreadModelCommand(text)
    if (intent && projection.catalog) {
      const resolution = resolveThreadModelCommandReference(projection.catalog, intent.reference)
      // Keep unresolved model requests on the conversation path. The agent
      // can consult its catalog and return a reply without a guessed switch.
      if (resolution.kind === 'ambiguous') {
        setNotice(`模型引用“${intent.reference}”不唯一：${resolution.candidates.map((item) => item.modelId).join('、')}。请使用完整模型 ID。`)
        throw new MessageNotSentError('模型引用不唯一，请使用完整模型 ID。')
      } else if (resolution.kind === 'resolved') {
        const model = resolution.model
        if (model.available === false) {
          setNotice(`${model.displayName}：${modelUnavailableCopy(model.unavailableReason)}。请从目录选择可用模型。${model.unavailableReason ? `（诊断代码：${model.unavailableReason}）` : ''}`)
          throw new MessageNotSentError('所选模型当前不可用。')
        }
        const pendingModel = store.state.snapshot?.pendingModelSwitch
        if (pendingModel && (pendingModel.modelId !== model.modelId ||
            (intent.action === 'reopen_model_context' && pendingModel.reason !== 'explicit_reopen'))) {
          setNotice('已有模型切换等待执行，请先完成或撤销该切换。')
          throw new MessageNotSentError('已有模型切换等待执行。')
        }
        if (!pendingModel && (intent.action === 'reopen_model_context' || model.modelId !== store.state.snapshot?.activeModelContext.modelId)) {
          const receipt = await dispatch(intent.action, {
            model_id: model.modelId,
            ...(intent.action === 'reopen_model_context' ? { reason: 'user_requested_fresh_context' } : {}),
          })
          if (receipt?.status !== 'accepted') throw new MessageNotSentError('模型切换未提交，请检查页面提示后重试。')
          // The activating turn must use the new ledger cursor, even when
          // SSE has not yet delivered the accepted selection events.
          if (receipt.acceptedEventSeq !== undefined) await store.catchUpThrough(receipt.acceptedEventSeq)
        }
      }
    }
    const receipt = await dispatch(mode === 'professional' ? 'send_professional' : 'send_auto', { text })
    if (receipt?.status !== 'accepted') throw new MessageNotSentError('指令未发送，请检查页面提示后重试。')
  }

  function controlButton(label: string, kind: string, enabled: boolean, payload: Record<string, unknown> = {}) {
    return <button type="button" className="thread-control-button" disabled={!enabled} onClick={() => void dispatch(kind, payload)}>{label}</button>
  }

  return <div className="thread-app-shell">
    <PageHeader className="thread-page-header" showThreadEntry={false} />
    {loading ? <main className="thread-loading" aria-live="polite"><span className="spinner" />正在恢复 Thread 投影…</main> : snapshot ? <main className="thread-app-main">
      <div className="thread-app-columns">
          <ThreadModelPane snapshot={snapshot} viewedPage={viewedPage || activePage || 'page_ieee39'} activePage={activePage || 'page_ieee39'} isHistorical={isHistorical}
          gridPages={displayedGridPages}
          projectionEventSeq={projection.eventSeq} previewDiagram={currentDiagram}
          networkView={activeNetworkView}
          networkTaskId={selectedNetworkTask?.attemptId || networkTask?.attemptId}
          networkFailureCode={!selectedNetworkTask && networkTask?.eventType === 'network_layer_unavailable' && typeof networkTask.payload.code === 'string' ? networkTask.payload.code : undefined}
          instructionLabel={instructionNumber ? `指令 ${instructionNumber}` : undefined}
          viewingInstruction={Boolean(selectedNetworkTask)} onLatestInstruction={() => selectPage(activePage!)}
          elementReference={fixture?.local_view.element_reference} modelOptions={modelOptions} resultProjection={displayedResultProjection || undefined} focusedElementId={focusedElementId}
          onSelectPage={selectPage} />
        <section className="thread-chat-pane" aria-label="Thread 对话区">
          <div className="thread-chat-heading"><div><span className="eyebrow">THREAD</span><h2>智能体对话</h2></div><div className="thread-chat-heading-meta"><span className="thread-model-short">{snapshot.activeModelContext.modelId} · {snapshot.activeModelContext.implementationFamily}</span><span className={`thread-connection-state is-${projection.connection}`}>{connectionLabel(projection.connection)}</span><span className="thread-run-state">{snapshot.run.state}</span><button type="button" className="thread-diagnostics-toggle" aria-label="查看 Thread 详情" aria-expanded={diagnosticsOpen} onClick={() => setDiagnosticsOpen((value) => !value)}>详情</button></div></div>
          {diagnosticsOpen && <div className="thread-diagnostics" role="region" aria-label="Thread 详情"><span>run <code>{snapshot.run.runId}</code></span><span>context <code>{snapshot.activeModelContext.id}</code></span><span>revision <code>{snapshot.activeModelContext.modelRevision}</code></span><span>selection <code>{snapshot.activeModelContext.selectionRevision}</code></span></div>}
          {(projection.connection !== 'live' || contextChangePending || attempt) && <div className={`thread-state-strip${projection.connection === 'resync_required' ? ' is-danger' : ''}`} role={projection.connection === 'resync_required' ? 'alert' : 'status'}><strong>{projection.connection === 'resync_required' ? '需要重新同步' : phaseLabel(attempt?.phase)}</strong><span>{statusCopy(projection, fixture)}</span></div>}
          {error && <div className="thread-inline-error" role="alert">{error}</div>}
          {notice && <div className="thread-inline-notice" role="status">{notice}</div>}
          {isInterrupted && <div className="thread-interrupted-banner" role="status"><strong>本次 Attempt 已中断</strong><span>重试将创建新的 Attempt，不覆盖旧 Attempt。</span></div>}
          <CapstoneAssistantThread events={events} disabled={!canSendText} isRunning={isActive} activity={projectAssistantActivity(events)} showActivity={traceVisible} canRerunCompleted={canSendText && !contextChangePending}
            networkAttemptIds={store.networkTasks.map((task) => task.attemptId)} onShowNetwork={(attemptId) => {
              setFocusedElement(undefined)
              setSelectedNetworkAttempt(attemptId)
              setNotice(null)
            }}
            selectedNetworkAttempt={selectedNetworkTask?.attemptId}
            resultProjections={snapshot.resultProjections} onFocusElement={(result: ResultProjection, elementId) => {
              if (isHistorical) {
                setNotice('历史页为只读视图，请返回当前模型后定位')
                return
              }
              if (result.modelContextId !== snapshot.activeModelContext.id || result.modelId !== snapshot.activeModelContext.modelId || result.modelRevision !== snapshot.activeModelContext.modelRevision) {
                setNotice('该结果属于历史模型修订，已保持只读，未改变当前电网图')
                return
              }
              if (!currentDiagramElementIds.has(elementId)) {
                setFocusedElement(undefined)
                setNotice('当前电网图中没有这个元件，无法定位')
                return
              }
              setFocusedElement({ resultId: result.resultId, modelId: result.modelId, modelRevision: result.modelRevision, elementId })
              setNotice(`已定位到 ${elementId}`)
            }}
            caseExecution={displayedCaseExecution} caseCatalog={projection.catalog?.cases || []} caseConnection={projection.connection}
            onCaseStart={startCase} onCaseAction={caseAction}
            composerControls={<><ThreadControls catalog={projection.catalog} activeFamily={snapshot.activeModelContext.implementationFamily}
              activeProfiles={snapshot.activeModelContext.enabledProfiles} pendingProfileSelection={snapshot.pendingSelection?.enabledProfiles}
              pendingModel={snapshot.pendingModelSwitch?.modelId} disabled={isHistorical || contextChangePending || caseActive || sending || projection.connection !== 'live'} traceVisible={traceVisible}
              onTraceToggle={() => setTraceVisible((value) => !value)} onProfileSelection={(profiles) => void dispatch('replace_selection', { enabled_profiles: profiles.map((profile) => ({ profile_id: profile.profileId, profile_version: profile.profileVersion })) })} />
              <ThreadModelDirectory models={modelOptions} currentModelId={snapshot.activeModelContext.modelId} target={modelTarget}
                disabled={isHistorical || contextChangePending || isActive || isInterrupted || caseActive || sending || projection.connection !== 'live'} pending={contextChangePending}
                onTargetChange={setModelTarget} onSwitch={(modelId) => void sendConversation('automatic', `打开 ${modelId} 电网模型`).catch(() => {})} /></>}
            modelSummary={{ modelId: snapshot.activeModelContext.modelId, implementationFamily: snapshot.activeModelContext.implementationFamily, modelRevision: snapshot.activeModelContext.modelRevision, contextId: snapshot.activeModelContext.id }}
            onSend={sendConversation}
            onCancel={async () => { await dispatch('cancel_live_attempt', { attempt_id: attempt?.attemptId }) }}
            onRegenerate={canRetry ? async (attemptId, instruction) => {
              if (events.some((event) => event.attemptId === attemptId && event.eventType === 'attempt_completed')) {
                if (canSendText && !contextChangePending && instruction?.trim()) await sendConversation('automatic', instruction)
              } else {
                await dispatch('retry_new_attempt', { attempt_id: attemptId })
              }
            } : undefined} />
          <div className="thread-control-row" aria-label="Thread 控制">
            {projection.connection === 'resync_required' ? <><button type="button" className="thread-primary-button" onClick={() => setReload((value) => value + 1)}>重新同步</button><button type="button" className="thread-secondary-button" onClick={() => setNotice('请检查服务连接与事件游标')}>帮助</button></> : projection.connection === 'reconnecting' ? <><button type="button" className="thread-primary-button" onClick={() => setReload((value) => value + 1)}>重新连接</button><button type="button" className="thread-secondary-button" onClick={() => setNotice('实时事件流暂时中断，Thread 状态仍保留。')}>帮助</button></> : <>
              {isInterrupted && controlButton('重试新 Attempt', 'retry_new_attempt', canRetry, { turn_id: attempt?.turnId })}
              {isHistorical && <button type="button" className="thread-control-button" onClick={() => selectPage(activePage || 'page_ieee39')}>返回当前模型</button>}
            </>}
          </div>
        </section>
      </div>
    </main> : null}
  </div>
}
