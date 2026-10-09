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
import ThreadRuntimeMenu from './ThreadRuntimeMenu'
import { parseThreadModelCommand, resolveThreadModelCommandReference, resolveThreadModelReference } from './threadCatalog'
import { parseModelControl } from './threadModelWorkspace'
import { commandKey } from './commandKey'
import { canReconnect, reconnectDelay } from './threadSessionState'
import type { ReactNode } from 'react'
import { enabledTools, effectiveTools, updateToolPreferences } from './threadToolPreferences'
import { useWorkbenchActivity, type PrepareConnection } from './useWorkbenchActivity'
import WorkbenchPreparation from './WorkbenchPreparationView'
import type { InputCatalog, InputSubmission } from './threadInput'

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
  prepareConnection?: PrepareConnection
}

export default function ThreadFixtureApp({ fixtureId, client, threadId: requestedThreadId, previewDiagram, storageKey, readOnly = false, headerActions, sessionNotice, disabledToolIds: sharedDisabledToolIds, onDisabledToolIdsChange, prepareConnection }: ThreadWorkspaceProps) {
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
  const [instructionLocation, setInstructionLocation] = useState<{ attemptId: string; nonce: number }>()
  const [taskReturn, setTaskReturn] = useState<{ contextId: string; attemptId?: string; nonce: number }>()
  const taskReturnGeneration = useRef(0)
  const commandInFlight = useRef(false)
  const composerSend = useRef(false)
  const composerCommands = useRef(new Set<string>())
  const [sending, setSending] = useState(false)
  const [modelBusy, setModelBusy] = useState(false)
  const [runtimeBusy, setRuntimeBusy] = useState(false)
  const [inputCatalog, setInputCatalog] = useState<InputCatalog>()
  const [inputCatalogLoading, setInputCatalogLoading] = useState(false)
  const catalogReading = useRef(false)
  async function refreshInputCatalog() {
    if (!client || catalogReading.current) return
    catalogReading.current = true
    setInputCatalogLoading(true)
    try { setInputCatalog(await client.inputCatalog(threadId)) }
    catch { setInputCatalog(undefined) }
    finally { catalogReading.current = false; setInputCatalogLoading(false) }
  }
  useEffect(() => { void refreshInputCatalog() }, [client, threadId, projection.snapshot?.runtimeMode,
    projection.snapshot?.activeModelContext.id, projection.snapshot?.activeModelContext.selectionRevision])
  const modelInFlight = useRef(false)
  const [acceptedDraft, setAcceptedDraft] = useState<{ text: string; commandId: string; submission?: InputSubmission }>()
  const reconnectFailures = useRef(0)
  const [pageVisible, setPageVisible] = useState(() => document.visibilityState !== 'hidden')
  const activity = useWorkbenchActivity(prepareConnection,
    loading || sending || modelBusy || projection.pendingCommands.some(item => !item.receipt)
      || Boolean(projection.snapshot?.currentAttempt && ACTIVE_PHASES.has(projection.snapshot.currentAttempt.phase)))

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
    if (!pageVisible || activity.paused) return () => { active = false; abort.abort(); unsubscribe() }
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
                const payload = entry.command.payload
                const submission = payload.input ? { input: payload.input,
                  ...(payload.resource_profile ? { resource_profile: payload.resource_profile } : {}),
                  context_selection: payload.context_selection || { include_refs: [], exclude_refs: [] } } as InputSubmission : undefined
                setAcceptedDraft({ text: entry.command.payload.text, commandId: entry.command.command_id, submission })
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
  }, [fixture, pageVisible, activity.paused, reload, store, threadId])

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
  const canSendText = !activity.paused && !readOnly && !loading && projection.connection === 'live' && !unresolvedCommand && !isHistorical && !isActive && !isInterrupted && !caseActive && !sending && !modelBusy && !runtimeBusy && !projection.resyncRequired
  const canRetry = !activity.paused && !readOnly && !loading && projection.connection === 'live' && !unresolvedCommand && !isHistorical && !isActive && !caseActive && !sending && !modelBusy && !projection.resyncRequired
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
  const currentModelTaskId = [...events].reverse().find(event => event.modelContextId === snapshot?.activeModelContext.id
    && event.attemptId && event.eventType === 'command_accepted' && ['send_auto', 'send_ordinary', 'send_professional'].includes(String(event.payload.kind)))?.attemptId
    || [...store.networkTasks].filter(task => task.context.id === snapshot?.activeModelContext.id).sort((a, b) => b.eventSeq - a.eventSeq)[0]?.attemptId
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
    if (activity.paused) {
      try {
        await activity.ensureReady()
        await store.load(threadId)
        await store.catchUp()
      } catch {
        return
      }
    }
    taskReturnGeneration.current++
    setInstructionLocation(undefined)
    setTaskReturn(undefined)
    if (readOnly) { addSystemNotice('这段对话已归档，可新建对话继续。', 'info', 'archive'); return }
    const latest = store.state.snapshot
    if (!latest) return
    const conversational = kind === 'send_auto' || kind === 'send_ordinary' || kind === 'send_professional'
    const initialCursor = store.state.eventSeq
    const contextIdentity = () => JSON.stringify([
      store.state.snapshot?.run, store.state.snapshot?.activeModelContext,
      store.state.snapshot?.runtimeMode,
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
      if (!(receipt.status === 'accepted' && (conversational || ['open_model', 'activate_model', 'close_model'].includes(kind)))) addSystemNotice(receiptNotice, receipt.status === 'rejected' ? 'error' : 'info', `receipt-${receipt.commandId}`, conversational && typeof payload.text === 'string' ? payload.text : undefined)
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
    taskReturnGeneration.current++
    setInstructionLocation(undefined)
    setTaskReturn(undefined)
    setSelectedNetworkAttempt(undefined)
    setFocusedElement(undefined)
    store.viewGridPage(pageId); setNotice(pageId === store.state.snapshot?.activeGridPageId ? '已返回当前模型页' : '已打开只读历史页'); sync()
    const page = store.state.gridPages.find((item) => item.pageId === pageId)
    if (page && !page.networkView && pageId !== store.state.snapshot?.activeGridPageId) {
      void store.restoreHistoricalNetwork(page.context.id).then((restored) => {
        if (store.state.viewedGridPageId !== pageId) return
        store.viewGridPage(restored); sync()
      }).catch(() => { if (store.state.viewedGridPageId === pageId) setNotice('该历史模型的电网图暂不可用。') })
    }
  }

  async function locateTaskInstruction(target: string, stillCurrent: () => boolean, generation: number) {
    const hasInstruction = () => store.publicEvents.some(event => event.attemptId === target && event.eventType === 'command_accepted'
      && ['send_auto', 'send_ordinary', 'send_professional'].includes(String(event.payload.kind)))
    for (let pages = 0; !hasInstruction() && store.state.hasOlderHistory && pages < 8; pages++) {
      await store.loadOlderHistory()
      if (!stillCurrent()) return
      sync()
    }
    if (!stillCurrent()) return
    if (hasInstruction()) setInstructionLocation({ attemptId: target, nonce: generation })
    else setNotice('该电网图对应的任务指令暂未加载。')
  }

  async function locateDisplayedTask() {
    const current = store.state.snapshot
    if (!current || !displayedTaskId) return
    const generation = ++taskReturnGeneration.current
    const contextId = selectedNetworkTask?.context.id || current.activeModelContext.id
    const stillCurrent = () => generation === taskReturnGeneration.current && store.state.snapshot?.threadId === current.threadId
    setTaskReturn({ contextId, attemptId: displayedTaskId, nonce: generation })
    setNotice(null)
    try { await locateTaskInstruction(displayedTaskId, stillCurrent, generation) }
    catch { if (stillCurrent()) setNotice('任务指令暂不可用，请重试。') }
  }

  async function returnCurrentTask() {
    const current = store.state.snapshot
    if (!current) return
    const generation = ++taskReturnGeneration.current
    const contextId = current.activeModelContext.id
    const target = currentModelTaskId
    const stillCurrent = () => generation === taskReturnGeneration.current && store.state.snapshot?.threadId === current.threadId
      && store.state.snapshot?.activeModelContext.id === contextId
    try {
      if (target && !store.networkTasks.some(task => task.attemptId === target && task.context.id === contextId)) {
        await store.restoreHistoricalNetwork(contextId, target)
      }
      if (!stillCurrent()) return
      store.viewGridPage(current.activeGridPageId)
      setSelectedNetworkAttempt(target)
      setFocusedElement(undefined)
      setTaskReturn({ contextId, attemptId: target, nonce: generation })
      setNotice(null)
      sync()
      if (!target) return
      await locateTaskInstruction(target, stillCurrent, generation)
    } catch {
      if (stillCurrent()) { setNotice('当前任务视图暂不可用，请重试。'); sync() }
    }
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
    if (inputCatalog?.operations.find(item => item.operation_id === 'start_case_execution')?.available === false) { addSystemNotice('当前执行角色或能力不支持此案例。', 'info'); return }
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

  async function sendConversation(mode: 'automatic' | 'ordinary' | 'professional', text: string, fromComposer = false, input?: InputSubmission): Promise<void> {
    if (commandInFlight.current || isHistorical) throw new MessageNotSentError('当前页面不可发送，请返回当前模型后重试。')
    commandInFlight.current = true
    composerSend.current = fromComposer
    setSending(true)
    try {
      await selectModelAndSend(mode, text, input)
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

  async function selectModelAndSend(mode: 'automatic' | 'ordinary' | 'professional', text: string, input?: InputSubmission): Promise<void> {
    const control = !input?.resource_profile && store.state.modelWorkspace ? parseModelControl(text) : null
    if (control && projection.catalog) {
      const workspace = store.state.modelWorkspace!
      const openedCatalog = { ...projection.catalog, models: workspace.models.map((model) => ({ ...model,
        authorityModelRef: model.authorityModelRef || model.modelId, diagramProviderId: model.diagramProviderId || model.implementationFamily })) }
      const openedResolution = resolveThreadModelReference(openedCatalog, control.reference)
      const opened = openedResolution.kind === 'resolved' ? workspace.models.filter((entry) => entry.modelId === openedResolution.model.modelId) : []
      let kind: 'open_model' | 'activate_model' | 'close_model' = control.kind
      let payload: Record<string, unknown>
      if (openedResolution.kind === 'ambiguous' || opened.length > 1) {
        addSystemNotice('已打开模型名称不唯一，请从模型列表选择。', 'error', undefined, text)
        throw new MessageNotSentError('模型名称不唯一。')
      }
      if (control.openedOnly || kind === 'close_model' || opened.length) {
        if (!opened.length) {
          addSystemNotice('这个模型尚未在当前会话中打开。请从模型列表选择或先打开它。', 'error', undefined, text)
          throw new MessageNotSentError('模型尚未打开。')
        }
        kind = kind === 'close_model' ? kind : 'activate_model'
        payload = { entry_id: opened[0].entryId }
      } else {
        const resolution = resolveThreadModelReference(projection.catalog, control.reference)
        if (resolution.kind !== 'resolved') {
          addSystemNotice(resolution.kind === 'ambiguous' ? '模型名称不唯一，请从目录选择。' : '未找到这个注册模型，请从目录选择。', 'error', undefined, text)
          throw new MessageNotSentError('模型未确定。')
        }
        kind = 'open_model'
        payload = { model_id: resolution.model.modelId }
      }
      if (!await changeModel(kind, payload)) throw new MessageNotSentError('模型操作未完成。')
      if (!control.task) return
      text = control.task
    }
    if (store.state.snapshot?.runtimeMode === 'pi_reference') {
      const receipt = await dispatch('send_auto', { text, ...input, input: input?.input || { kind: 'text', text } })
      if (receipt?.status !== 'accepted') throw new MessageNotSentError('指令未发送，请检查页面提示后重试。')
      return
    }
    let family = store.state.snapshot?.pendingModelSwitch?.implementationFamily || store.state.snapshot?.activeModelContext.implementationFamily || ''
    const intent = input?.resource_profile ? null : parseThreadModelCommand(text)
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
    const receipt = await dispatch(mode === 'professional' ? 'send_professional' : mode === 'ordinary' ? 'send_ordinary' : 'send_auto', { text, ...input, input: input?.input || { kind: 'text', text },
      ...(projection.catalog?.profiles.length ? { enabled_profiles: tools.map((profile) => ({ profile_id: profile.profileId, profile_version: profile.profileVersion })) } : {}),
    })
    if (receipt?.status !== 'accepted') throw new MessageNotSentError('指令未发送，请检查页面提示后重试。')
  }

  async function changeModel(kind: 'open_model' | 'activate_model' | 'close_model', payload: Record<string, unknown>): Promise<boolean> {
    taskReturnGeneration.current++
    setInstructionLocation(undefined)
    setTaskReturn(undefined)
    if (modelInFlight.current) return false
    modelInFlight.current = true
    setModelBusy(true)
    try {
    const before = store.state.modelWorkspace
    const entry = before?.models.find((item) => item.entryId === payload.entry_id)
    if (kind === 'activate_model' && payload.entry_id === before?.currentEntryId) {
      selectPage(store.state.snapshot!.activeGridPageId)
      return true
    }
    const receipt = await dispatch(kind, payload, kind === 'close_model' ? `已关闭${entry ? ` ${entry.displayName}` : '模型'}。` : '当前电网模型已切换。')
    if (receipt?.status !== 'accepted') return false
    if (receipt.acceptedEventSeq !== undefined) await store.catchUpThrough(receipt.acceptedEventSeq)
    await store.refreshModels()
    if (kind !== 'close_model') selectPage(store.state.snapshot!.activeGridPageId)
    else if (!isHistorical) setSelectedNetworkAttempt(undefined)
    setFocusedElement(undefined)
    sync()
    return true
    } finally { modelInFlight.current = false; setModelBusy(false) }
  }

  function requireEnabledTools(family: string, text: string) {
    const profiles = projection.catalog?.profiles || []
    if (disabledToolIds.length && !profiles.length) {
      addSystemNotice('工具目录暂不可用，请重新连接后重试。', 'error', undefined, text)
      throw new MessageNotSentError('工具目录暂不可用。')
    }
    const tools = effectiveTools(profiles, disabledToolIds, family)
    return tools
  }

  function controlButton(label: string, kind: string, enabled: boolean, payload: Record<string, unknown> = {}) {
    return <button type="button" className="thread-control-button" disabled={!enabled} onClick={() => void dispatch(kind, payload)}>{label}</button>
  }

  return <div className="thread-app-shell">
    {(activity.mode === 'preparing' || activity.mode === 'failed') && <div className="thread-resume-progress">
      <WorkbenchPreparation compact updates={activity.updates} error={activity.error}
        onRetry={() => { void activity.ensureReady().catch(() => {}) }} />
    </div>}
    <PageHeader className="thread-page-header" showThreadEntry={false} />
    {loading && !snapshot ? <main className="thread-loading" aria-live="polite"><span className="spinner" />正在恢复 Thread 投影…</main> : snapshot ? <main className="thread-app-main">
      <div className="thread-app-columns">
          <ThreadModelPane snapshot={snapshot} viewedPage={viewedPage || activePage || 'page_ieee39'} activePage={activePage || 'page_ieee39'} isHistorical={isHistorical}
          workingPages={projection.modelWorkspace ? store.modelWorkingPages : undefined} cameraStorageKey={`${storageKey || snapshot.threadId}.network-cameras`}
          gridPages={displayedGridPages}
          projectionEventSeq={projection.eventSeq} previewDiagram={currentDiagram}
          networkView={activeNetworkView}
          networkTaskId={selectedNetworkTask?.attemptId || networkTask?.attemptId}
          networkFailureCode={!selectedNetworkTask && networkTask?.eventType === 'network_layer_unavailable' && typeof networkTask.payload.code === 'string' ? networkTask.payload.code : undefined}
          instructionLabel={displayedTaskId ? instructionNumber && !projection.hasOlderHistory ? `指令 ${instructionNumber} 结果` : '历史指令结果' : '基础拓扑'}
          viewingInstruction={Boolean(selectedNetworkTask && selectedNetworkTask.attemptId !== currentModelTaskId)} onLatestInstruction={() => { void returnCurrentTask() }}
          onLocateInstruction={displayedTaskId ? () => { void locateDisplayedTask() } : undefined}
          returnCurrentTaskLabel={currentModelTaskId ? '回到当前任务' : '回到当前模型'}
          returnTaskRequest={taskReturn?.contextId === (selectedNetworkTask?.context.id || snapshot.activeModelContext.id)
            && taskReturn.attemptId === (selectedNetworkTask?.attemptId || networkTask?.attemptId) ? taskReturn.nonce : undefined}
          elementReference={fixture?.local_view.element_reference} modelOptions={modelOptions} resultProjection={displayedResultProjection || undefined} focusedElementId={focusedElementId}
          onSelectPage={selectPage} feedback={notice}
          modelBusy={activity.paused || modelBusy || readOnly || loading || isActive || isInterrupted || caseActive || unresolvedCommand || contextChangePending || sending || projection.connection !== 'live'}
          onOpenHistoricalModel={projection.modelWorkspace ? (modelId, revision) => { void changeModel('open_model', { model_id: modelId, model_revision: revision }).catch(() => addSystemNotice('历史模型无法打开，请重新连接。', 'error')) } : undefined} />
        <section className="thread-chat-pane" aria-label="Thread 对话区">
          <div className="thread-chat-heading"><div className="thread-chat-heading-title"><h2>智能体对话</h2><span className="thread-model-short">{snapshot.activeModelContext.modelId} · {snapshot.activeModelContext.implementationFamily}</span></div><div className="thread-chat-heading-meta">{projection.connection !== 'live' && <span className={`thread-connection-state is-${projection.connection}`}>{connectionLabel(projection.connection)}</span>}{activity.mode === 'idle' && <span className="thread-idle-state" title="页面暂未操作，继续使用时自动恢复连接。">按需连接</span>}<span inert={activity.paused}>{headerActions}</span></div></div>
          <CapstoneAssistantThread storageKey={storageKey} hasOlderHistory={projection.hasOlderHistory} historyLoading={projection.historyLoading}
            systemNotices={systemState.thread === threadId ? systemState.items : []} onSystemAction={() => setReload((value) => value + 1)}
            historyAtLatest={projection.historyAtLatest} onReturnLatest={() => setReload((value) => value + 1)}
            instructionLocation={instructionLocation}
            onLoadOlder={() => store.loadOlderHistory()} events={events} runtimeMode={(isActive && snapshot.currentAttempt?.runtimeMode) || snapshot.runtimeMode} disabled={!canSendText} isRunning={isActive} acceptedDraft={acceptedDraft} activity={projectAssistantActivity(events)} canRerunCompleted={canSendText && !contextChangePending}
            networkAttemptIds={[...new Set([...store.networkTasks.map((task) => task.attemptId), ...events.filter((event) => event.attemptId && (event.eventType === 'network_diagram' || projection.modelWorkspace && event.eventType === 'attempt_completed' && event.modelContextId)).map((event) => event.attemptId!)])]} onShowNetwork={(attemptId) => {
              taskReturnGeneration.current++
              setInstructionLocation(undefined)
              setTaskReturn(undefined)
              setFocusedElement(undefined)
              setSelectedNetworkAttempt(attemptId)
              setNotice(null)
              if (!store.networkTasks.some((task) => task.attemptId === attemptId)) {
                const contextId = events.find((event) => event.attemptId === attemptId && event.modelContextId)?.modelContextId
                if (contextId) void store.restoreHistoricalNetwork(contextId, attemptId).then(sync).catch(() => setNotice('该回答对应的历史电网图暂不可用。'))
              }
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
            caseStartDisabledReason={inputCatalog?.operations.find(item => item.operation_id === 'start_case_execution')?.available === false ? '当前执行角色或能力不支持案例' : !inputCatalog && snapshot.runtimeMode === 'pi_reference' ? '请先切换到 Capstone' : undefined}
            onCaseStart={startCase} onCaseAction={caseAction}
            composerControls={(historyActions) => <><ThreadControls catalog={projection.catalog} selectedProfiles={selectedTools}
              pendingModel={snapshot.pendingModelSwitch?.modelId} disabled={loading || caseActive || sending} historyActions={historyActions}
              onProfileSelection={(profiles) => setDisabledToolIds(updateToolPreferences(projection.catalog?.profiles || [], disabledToolIds, profiles))} />
              <ThreadRuntimeMenu value={snapshot.runtimeMode}
                disabled={!canSendText || runtimeBusy || contextChangePending}
                onChange={(mode) => {
                  if (runtimeBusy) return
                  setRuntimeBusy(true)
                  void dispatch('switch_runtime', { runtime_mode: mode }, `已切换至 ${mode === 'pi_reference' ? 'Pi' : 'Capstone'} 模式。`)
                    .then(async (receipt) => { if (receipt?.acceptedEventSeq !== undefined) await store.catchUpThrough(receipt.acceptedEventSeq) })
                    .catch(() => addSystemNotice('运行模式切换未完成，请重新连接。', 'error'))
                    .finally(() => setRuntimeBusy(false))
                }} />
              <ThreadModelDirectory models={modelOptions} currentModelId={snapshot.activeModelContext.modelId} target={modelTarget}
                disabled={activity.paused || readOnly || loading || unresolvedCommand || contextChangePending || isActive || isInterrupted || caseActive || sending || modelBusy || isHistorical && !projection.modelWorkspace || projection.connection !== 'live'} pending={contextChangePending}
                workspace={projection.modelWorkspace}
                onActivate={(entryId) => { void changeModel('activate_model', { entry_id: entryId }).catch(() => addSystemNotice('模型切换尚未完成，请重新连接。', 'error')) }}
                onClose={(entryId) => { void changeModel('close_model', { entry_id: entryId }).catch(() => addSystemNotice('模型关闭尚未完成，请重新连接。', 'error')) }}
                onTargetChange={setModelTarget} onSwitch={(modelId) => void (projection.modelWorkspace ? changeModel('open_model', { model_id: modelId }) : sendConversation('automatic', `打开 ${modelId} 电网模型`)).catch(() => {})} /></>}
            modelSummary={{ modelId: snapshot.activeModelContext.modelId, implementationFamily: snapshot.activeModelContext.implementationFamily, modelRevision: snapshot.activeModelContext.modelRevision, contextId: snapshot.activeModelContext.id }}
            instructionModels={[snapshot.activeModelContext, ...projection.gridPages.map(page => page.context), ...store.networkTasks.map(task => task.context)].map(context => ({ contextId: context.id, modelId: context.modelId }))}
            inputCatalog={inputCatalog?.context_id === snapshot.activeModelContext.id && inputCatalog?.selection_revision === snapshot.activeModelContext.selectionRevision ? inputCatalog : undefined}
            inputCatalogLoading={inputCatalogLoading} onRefreshInputCatalog={() => void refreshInputCatalog()}
            onSend={(mode, text, input) => sendConversation(mode, text, true, input)}
            onCancel={async () => { await dispatch('cancel_live_attempt', { attempt_id: attempt?.attemptId }) }}
            onRegenerate={canRetry ? async (attemptId, instruction) => {
              if (events.some((event) => event.attemptId === attemptId && event.eventType === 'attempt_completed')) {
                if (canSendText && !contextChangePending && instruction?.trim()) await sendConversation('automatic', instruction)
              } else {
                const acceptedMode = events.find(event => event.attemptId === attemptId && event.eventType === 'command_accepted')?.payload.runtime_mode
                if (acceptedMode !== 'pi_reference' && snapshot.activeModelContext.enabledProfiles.some((profile) => disabledToolIds.includes(profile.profileId))) {
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
