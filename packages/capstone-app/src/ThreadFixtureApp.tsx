import { useEffect, useMemo, useRef, useState } from 'react'
import { MessageNotSentError } from '@assistant-ui/react'
import { buildThreadCommand, CapstoneThreadClient, type ThreadCommand } from './threadClient'
import { createFixtureTransport, instructionOrdinal, ThreadProjectionStore, type ThreadProjectionState } from './threadProjectionStore'
import { threadUiFixture, type ThreadUiFixtureId } from './threadUiFixtures'
import CapstoneAssistantThread, { projectAssistantActivity } from './CapstoneAssistantThread'
import ThreadModelPane from './ThreadModelPane'
import ThreadModelDirectory, { modelUnavailableCopy } from './ThreadModelDirectory'
import { commandRejectionCopy } from './threadFeedback'
import { upsertSystemNotice, type ThreadSystemNotice } from './threadSystemNotices'
import { threadPreviewDiagram } from './threadModelDiagram'
import type { DiagramNetworkView, NetworkDiagram } from './types'
import type { ResultProjection } from './threadProtocol'
import { PageHeader } from './AppHeader'
import ThreadControls from './ThreadControls'
import { parseThreadModelCommand, resolveThreadModelCommandReference } from './threadCatalog'
import { commandKey } from './commandKey'
import { canReconnect, reconnectDelay } from './threadSessionState'
import type { ReactNode } from 'react'
import { enabledTools, effectiveTools, updateToolPreferences } from './threadToolPreferences'

const ACTIVE_PHASES = new Set(['created', 'accepted', 'running', 'waiting', 'committing'])

function connectionLabel(connection: ThreadProjectionState['connection']): string {
  return connection === 'live' ? '实时连接' : connection === 'reconnecting' ? '重连中' : connection === 'resync_required' ? '需重同步' : connection === 'connecting' ? '连接中' : '离线'
}

export type ThreadWorkspaceProps = {
  fixtureId?: ThreadUiFixtureId
  client?: CapstoneThreadClient
  threadId?: string
  previewDiagram?: NetworkDiagram | null
  storageKey?: string
  readOnly?: boolean
  headerActions?: ReactNode
  sessionNotice?: string | null
  disabledToolIds?: string[]
  onDisabledToolIdsChange?: (ids: string[]) => void
}

export default function ThreadFixtureApp({ fixtureId, client, threadId: requestedThreadId, previewDiagram, storageKey, readOnly = false, headerActions, sessionNotice, disabledToolIds: sharedDisabledToolIds, onDisabledToolIdsChange }: ThreadWorkspaceProps) {
  const [localDisabledToolIds, setLocalDisabledToolIds] = useState<string[]>([])
  const disabledToolIds = sharedDisabledToolIds ?? localDisabledToolIds
  const setDisabledToolIds = onDisabledToolIdsChange ?? setLocalDisabledToolIds
  const fixture = useMemo(() => fixtureId ? threadUiFixture(fixtureId) : null, [fixtureId])
  const store = useMemo(() => {
    if (client) return new ThreadProjectionStore(client, storageKey)
    if (fixture) return new ThreadProjectionStore(new CapstoneThreadClient(createFixtureTransport(fixture)))
    throw new Error('Thread workspace requires a client or fixture')
  }, [client, fixture, storageKey])
  const threadId = requestedThreadId || (fixture ? String((fixture.snapshot as { thread_id: string }).thread_id) : '')
  const [projection, setProjection] = useState<ThreadProjectionState>(store.state)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [systemState, setSystemState] = useState<{ thread: string; items: ThreadSystemNotice[] }>({ thread: threadId, items: [] })
  function addSystemNotice(text: string, tone: 'info' | 'error' = 'info', id = commandKey(), instruction?: string, action?: ThreadSystemNotice['action']) {
    const item = { id, afterEventSeq: store.state.eventSeq, text, tone, instruction, action }
    setSystemState((state) => ({ thread: threadId, items: upsertSystemNotice(state.thread === threadId ? state.items : [], item) }))
  }
  const [reload, setReload] = useState(0)
  const [modelTarget, setModelTarget] = useState('ieee39')
  const [focusedElement, setFocusedElement] = useState<{ resultId: string; modelId: string; modelRevision: string; elementId: string }>()
  const [selectedNetworkAttempt, setSelectedNetworkAttempt] = useState<string>()
  const commandInFlight = useRef(false)
  const composerSend = useRef(false)
  const composerCommands = useRef(new Set<string>())
  const [sending, setSending] = useState(false)
  const [acceptedDraft, setAcceptedDraft] = useState<{ text: string; commandId: string }>()
  const reconnectFailures = useRef(0)
  const [pageVisible, setPageVisible] = useState(() => document.visibilityState !== 'hidden')

  useEffect(() => {
    const changed = () => setPageVisible(document.visibilityState !== 'hidden')
    document.addEventListener('visibilitychange', changed)
    return () => document.removeEventListener('visibilitychange', changed)
  }, [])

  useEffect(() => {
    let active = true
    const abort = new AbortController()
    let reconnectTimer: ReturnType<typeof setTimeout> | undefined
    let stableTimer: ReturnType<typeof setTimeout> | undefined
    function recover(cause: unknown) {
      if (!active || abort.signal.aborted || !canReconnect(cause)) return
      reconnectTimer = setTimeout(() => {
        if (active) setReload((value) => value + 1)
      }, reconnectDelay(reconnectFailures.current++))
    }
    const unsubscribe = store.subscribe(() => {
      if (active) setProjection({ ...store.state, pendingCommands: [...store.state.pendingCommands] })
    })
    if (!pageVisible) return () => { active = false; abort.abort(); unsubscribe() }
    setLoading(true); setError(null); setNotice(null)
    void (async () => {
      try {
        await store.load(threadId)
        for (const entry of store.state.pendingCommands) {
          if (!entry.receipt && ['send_auto', 'send_ordinary', 'send_professional'].includes(entry.command.kind)) composerCommands.current.add(entry.command.command_id)
        }
        // React StrictMode mounts effects twice in development. An old load
        // must not continue into catch-up and race the active projection.
        if (!active) return
        if (fixture?.local_view.viewed_grid_page_id && fixture.local_view.viewed_grid_page_id !== store.state.snapshot?.activeGridPageId) {
          store.viewGridPage(fixture.local_view.viewed_grid_page_id)
        }
        if (!store.state.resyncRequired) {
          await store.catchUp()
          if (!active) return
          // Reconcile only commands whose receipt was lost. Preserve the
          // original cursor and identity even if SSE already shows their Turn.
          for (const entry of store.state.pendingCommands.filter((item) => !item.receipt)) {
            const receipt = await store.dispatch(entry.command)
            if (!active) return
            if (receipt.status === 'accepted') {
              if (composerCommands.current.has(entry.command.command_id)
                  && ['send_auto', 'send_ordinary', 'send_professional'].includes(entry.command.kind)
                  && typeof entry.command.payload.text === 'string') {
                setAcceptedDraft({ text: entry.command.payload.text, commandId: entry.command.command_id })
              }
              addSystemNotice('已确认原操作提交成功。', 'info', `receipt-${entry.command.command_id}`)
            } else {
              addSystemNotice(commandRejectionCopy(receipt.rejection), 'error', `receipt-${entry.command.command_id}`, typeof entry.command.payload.text === 'string' ? entry.command.payload.text : undefined)
            }
          }
        }
        if (active) setProjection({ ...store.state, pendingCommands: [...store.state.pendingCommands] })
        if (active && store.canStreamEvents) {
          stableTimer = setTimeout(() => { reconnectFailures.current = 0 }, 30_000)
          void store.consumeEvents(abort.signal).catch((cause) => {
            if (stableTimer) clearTimeout(stableTimer)
            if (active && !(cause instanceof DOMException && cause.name === 'AbortError')) {
              setError('实时连接暂不可用。')
              recover(cause)
            }
          })
        }
      } catch (cause) {
        if (active) setError('工作台状态暂不可用，请重新连接。')
        recover(cause)
      } finally {
        if (active) setLoading(false)
      }
    })()
    return () => { active = false; abort.abort(); if (reconnectTimer) clearTimeout(reconnectTimer); if (stableTimer) clearTimeout(stableTimer); unsubscribe() }
  }, [fixture, pageVisible, reload, store, threadId])

  const snapshot = projection.snapshot
  const selectedTools = useMemo(() => enabledTools(projection.catalog?.profiles || [], disabledToolIds), [projection.catalog?.profiles, disabledToolIds])
  useEffect(() => {
    if (!snapshot) return
    const connection = projection.connection
    if (connection === 'offline' || connection === 'reconnecting' || connection === 'resync_required' || error) {
      setSystemState((state) => {
        const items = state.thread === threadId ? state.items : []
        // A lost command receipt already explains this interruption and owns
        // its recovery button. Do not repeat it as a second connection error.
        if (connection !== 'resync_required' && items.some((item) => item.id.startsWith('receipt-') && item.action === 'reconnect')) return state
        return { thread: threadId, items: upsertSystemNotice(items, { id: 'connection', afterEventSeq: store.state.eventSeq,
          text: connection === 'resync_required' ? '需要重新同步' : '连接暂时中断，输入和已加载消息仍保留。', tone: 'error', action: connection === 'resync_required' ? 'resync' : 'reconnect' }) }
      })
    } else if (connection === 'live') {
      setSystemState((state) => state.thread === threadId && state.items.some((item) => item.id === 'connection')
        ? { ...state, items: upsertSystemNotice(state.items, { id: 'connection', afterEventSeq: store.state.eventSeq, text: '连接已恢复。', tone: 'info' }) } : state)
    }
  }, [projection.connection, error, snapshot?.threadId])
  useEffect(() => {
    if (sessionNotice) addSystemNotice(sessionNotice, 'error', 'session')
    if (readOnly) addSystemNotice('这段对话已归档，可新建对话继续。', 'info', 'archive')
  }, [sessionNotice, readOnly, threadId])
  useEffect(() => {
    const attempt = snapshot?.currentAttempt
    if (attempt?.phase === 'interrupted' && !store.publicEvents.some((event) => event.attemptId === attempt.attemptId && event.eventType === 'attempt_interrupted')) {
      addSystemNotice('本次 Attempt 已中断', 'info', `interrupted-${attempt.attemptId}`)
    }
  }, [snapshot?.currentAttempt?.attemptId, snapshot?.currentAttempt?.phase])
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
  const unresolvedCommand = projection.pendingCommands.some((entry) => !entry.receipt)
  const canSendText = !readOnly && !loading && projection.connection === 'live' && !unresolvedCommand && !isHistorical && !isActive && !isInterrupted && !caseActive && !sending && !projection.resyncRequired
  const canRetry = !readOnly && !loading && projection.connection === 'live' && !unresolvedCommand && !isHistorical && !isActive && !caseActive && !sending && !projection.resyncRequired
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
  const networkTask = store.latestNetworkEvent
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
    if (readOnly) { addSystemNotice('这段对话已归档，可新建对话继续。', 'info', 'archive'); return }
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
    let submittedCommand: ThreadCommand | undefined
    const makeCommand = (): ThreadCommand => {
      const current = store.state.snapshot!
      const key = commandKey()
      const command = buildThreadCommand({
        threadId: current.threadId, runId: current.run.runId, kind,
        expectedEventSeq: store.state.eventSeq, commandId: `cmd_ui_${key}`,
        idempotencyKey: `idem_ui_${key}`, payload,
      })
      if (conversational && composerSend.current) composerCommands.current.add(command.command_id)
      submittedCommand = command
      return command
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
      if (!(conversational && receipt.status === 'accepted')) addSystemNotice(receiptNotice, receipt.status === 'rejected' ? 'error' : 'info', `receipt-${receipt.commandId}`, conversational && typeof payload.text === 'string' ? payload.text : undefined)
      sync()
      if (receipt.status === 'accepted') {
        setError(null)
        if (conversational || kind === 'retry_new_attempt') {
          setFocusedElement(undefined)
          setSelectedNetworkAttempt(undefined)
        }
      }
      return receipt
    } catch (cause) {
      addSystemNotice('操作提交结果尚未确认。请重新连接核对原操作，输入内容已保留。', 'error', submittedCommand ? `receipt-${submittedCommand.command_id}` : undefined, typeof payload.text === 'string' ? payload.text : undefined, 'reconnect'); sync()
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
    if (actionId === 'retry_case_step' && snapshot.activeModelContext.enabledProfiles.some((profile) => disabledToolIds.includes(profile.profileId))) {
      addSystemNotice('工具选择已改变，请启用案例所需工具后重试。', 'error')
      return
    }
    const executionId = caseIdentity()
    if (!executionId) {
      addSystemNotice('案例身份尚未同步，请稍后重试', 'error')
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
      addSystemNotice('案例步骤身份尚未同步，请稍后重试', 'error')
      return
    }
    void dispatch('retry_case_step', { case_execution_id: executionId, step_ordinal: ordinal, failed_attempt_id: failedAttemptId })
  }

  function startCase(caseId: string, caseVersion: string): void {
    const entry = projection.catalog?.cases?.find((item) => item.caseId === caseId && item.caseVersion === caseVersion)
    const families = projection.catalog?.models.filter((model) => entry?.modelIds.includes(model.modelId)).map((model) => model.implementationFamily) || []
    const needed = projection.catalog?.profiles.filter((profile) => profile.implementationFamilies.some((family) => families.includes(family))) || []
    if (needed.some((profile) => disabledToolIds.includes(profile.profileId)) ||
        (disabledToolIds.length > 0 && (!entry || !needed.length))) {
      addSystemNotice('案例所需的计算分析工具已关闭。请在设置中启用后重试。', 'error')
      return
    }
    void dispatch('start_case_execution', { case_id: caseId, case_version: caseVersion, strategy_id: 'sequential_batch' })
  }

  async function sendConversation(mode: 'automatic' | 'ordinary' | 'professional', text: string, fromComposer = false): Promise<void> {
    if (commandInFlight.current || isHistorical) throw new MessageNotSentError('当前页面不可发送，请返回当前模型后重试。')
    commandInFlight.current = true
    composerSend.current = fromComposer
    setSending(true)
    try {
      await selectModelAndSend(mode, text)
    } catch (cause) {
      if (cause instanceof MessageNotSentError) throw cause
      setError(cause instanceof Error ? cause.message : '指令未发送')
      throw new MessageNotSentError('指令未发送，请检查页面提示后重试。')
    } finally {
      commandInFlight.current = false
      composerSend.current = false
      setSending(false)
    }
  }

  async function selectModelAndSend(mode: 'automatic' | 'ordinary' | 'professional', text: string): Promise<void> {
    let family = store.state.snapshot?.pendingModelSwitch?.implementationFamily || store.state.snapshot?.activeModelContext.implementationFamily || ''
    const intent = parseThreadModelCommand(text)
    if (intent && projection.catalog) {
      const resolution = resolveThreadModelCommandReference(projection.catalog, intent.reference)
      // Keep unresolved model requests on the conversation path. The agent
      // can consult its catalog and return a reply without a guessed switch.
      if (resolution.kind === 'ambiguous') {
        addSystemNotice(`模型引用“${intent.reference}”不唯一：${resolution.candidates.map((item) => item.modelId).join('、')}。请使用完整模型 ID。`, 'error', undefined, text)
        throw new MessageNotSentError('模型引用不唯一，请使用完整模型 ID。')
      } else if (resolution.kind === 'resolved') {
        const model = resolution.model
        family = model.implementationFamily
        if (model.available === false) {
          addSystemNotice(`${model.displayName}：${modelUnavailableCopy(model.unavailableReason)}。请从目录选择可用模型。${model.unavailableReason ? `（诊断代码：${model.unavailableReason}）` : ''}`, 'error', undefined, text)
          throw new MessageNotSentError('所选模型当前不可用。')
        }
        const pendingModel = store.state.snapshot?.pendingModelSwitch
        if (pendingModel && (pendingModel.modelId !== model.modelId ||
            (intent.action === 'reopen_model_context' && pendingModel.reason !== 'explicit_reopen'))) {
          addSystemNotice('已有模型切换等待执行，请先完成或撤销该切换。', 'error', undefined, text)
          throw new MessageNotSentError('已有模型切换等待执行。')
        }
        if (!pendingModel && (intent.action === 'reopen_model_context' || model.modelId !== store.state.snapshot?.activeModelContext.modelId)) {
          requireEnabledTools(family, text)
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
    const tools = requireEnabledTools(family, text)
    const receipt = await dispatch(mode === 'professional' ? 'send_professional' : 'send_auto', { text,
      ...(projection.catalog?.profiles.length ? { enabled_profiles: tools.map((profile) => ({ profile_id: profile.profileId, profile_version: profile.profileVersion })) } : {}),
    })
    if (receipt?.status !== 'accepted') throw new MessageNotSentError('指令未发送，请检查页面提示后重试。')
  }

  function requireEnabledTools(family: string, text: string) {
    const profiles = projection.catalog?.profiles || []
    if (disabledToolIds.length && !profiles.length) {
      addSystemNotice('工具目录暂不可用，请重新连接后重试。', 'error', undefined, text)
      throw new MessageNotSentError('工具目录暂不可用。')
    }
    const tools = effectiveTools(profiles, disabledToolIds, family)
    // The current Pi runtime still requires a prepared Pack. Keep the global
    // preference, retain the draft and fail before any default can re-enable it.
    if (profiles.length && !tools.length) {
      addSystemNotice('未启用适用于此模型的计算分析工具。请在设置中启用后重试。', 'error', undefined, text)
      throw new MessageNotSentError('未启用适用于此模型的计算分析工具。')
    }
    return tools
  }

  function controlButton(label: string, kind: string, enabled: boolean, payload: Record<string, unknown> = {}) {
    return <button type="button" className="thread-control-button" disabled={!enabled} onClick={() => void dispatch(kind, payload)}>{label}</button>
  }

  return <div className="thread-app-shell">
    <PageHeader className="thread-page-header" showThreadEntry={false} />
    {loading && !snapshot ? <main className="thread-loading" aria-live="polite"><span className="spinner" />正在恢复 Thread 投影…</main> : snapshot ? <main className="thread-app-main">
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
          onSelectPage={selectPage} feedback={notice} />
        <section className="thread-chat-pane" aria-label="Thread 对话区">
          <div className="thread-chat-heading"><div className="thread-chat-heading-title"><h2>智能体对话</h2><span className="thread-model-short">{snapshot.activeModelContext.modelId} · {snapshot.activeModelContext.implementationFamily}</span></div><div className="thread-chat-heading-meta">{projection.connection !== 'live' && <span className={`thread-connection-state is-${projection.connection}`}>{connectionLabel(projection.connection)}</span>}{headerActions}</div></div>
          <CapstoneAssistantThread storageKey={storageKey} hasOlderHistory={projection.hasOlderHistory} historyLoading={projection.historyLoading}
            systemNotices={systemState.thread === threadId ? systemState.items : []} onSystemAction={() => setReload((value) => value + 1)}
            historyAtLatest={projection.historyAtLatest} onReturnLatest={() => setReload((value) => value + 1)}
            onLoadOlder={() => store.loadOlderHistory()} events={events} disabled={!canSendText} isRunning={isActive} acceptedDraft={acceptedDraft} activity={projectAssistantActivity(events)} canRerunCompleted={canSendText && !contextChangePending}
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
            composerControls={(historyActions) => <><ThreadControls catalog={projection.catalog} selectedProfiles={selectedTools}
              pendingModel={snapshot.pendingModelSwitch?.modelId} disabled={loading || caseActive || sending} historyActions={historyActions}
              onProfileSelection={(profiles) => setDisabledToolIds(updateToolPreferences(projection.catalog?.profiles || [], disabledToolIds, profiles))} />
              <ThreadModelDirectory models={modelOptions} currentModelId={snapshot.activeModelContext.modelId} target={modelTarget}
                disabled={readOnly || loading || unresolvedCommand || isHistorical || contextChangePending || isActive || isInterrupted || caseActive || sending || projection.connection !== 'live'} pending={contextChangePending}
                onTargetChange={setModelTarget} onSwitch={(modelId) => void sendConversation('automatic', `打开 ${modelId} 电网模型`).catch(() => {})} /></>}
            modelSummary={{ modelId: snapshot.activeModelContext.modelId, implementationFamily: snapshot.activeModelContext.implementationFamily, modelRevision: snapshot.activeModelContext.modelRevision, contextId: snapshot.activeModelContext.id }}
            onSend={(mode, text) => sendConversation(mode, text, true)}
            onCancel={async () => { await dispatch('cancel_live_attempt', { attempt_id: attempt?.attemptId }) }}
            onRegenerate={canRetry ? async (attemptId, instruction) => {
              if (events.some((event) => event.attemptId === attemptId && event.eventType === 'attempt_completed')) {
                if (canSendText && !contextChangePending && instruction?.trim()) await sendConversation('automatic', instruction)
              } else {
                if (snapshot.activeModelContext.enabledProfiles.some((profile) => disabledToolIds.includes(profile.profileId))) {
                  addSystemNotice('工具选择已改变，请发送新指令使用当前设置。', 'error')
                  return
                }
                await dispatch('retry_new_attempt', { attempt_id: attemptId })
              }
            } : undefined} />
          <div className="thread-control-row" aria-label="Thread 控制">
            {projection.connection === 'live' && <>
              {isInterrupted && controlButton('重试新 Attempt', 'retry_new_attempt', canRetry && !snapshot.activeModelContext.enabledProfiles.some((profile) => disabledToolIds.includes(profile.profileId)), { turn_id: attempt?.turnId })}
              {isHistorical && <button type="button" className="thread-control-button" onClick={() => selectPage(activePage || 'page_ieee39')}>返回当前模型</button>}
            </>}
          </div>
        </section>
      </div>
    </main> : null}
  </div>
}
