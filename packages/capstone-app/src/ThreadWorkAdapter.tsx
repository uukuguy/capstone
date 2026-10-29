import {isWorkspaceActive} from './workspaceName'
import {applicationCapacity,rethrowDebugCapacity} from './applicationCapacity'
import { useCallback, useEffect, useMemo, useRef, useState, type Dispatch, type SetStateAction } from 'react'
import { MessageNotSentError } from '@assistant-ui/react'
import { Plus, RefreshCw } from 'lucide-react'
import ThreadWorkspace from './ThreadWorkspace'
import {WorkspaceGatewayStatus,SessionConnectionStatus} from './WorkspaceConnectionStatus'
import {resultProjectionHistoryText} from './threadSystemNotices'
import CapstoneAssistantThread, { projectAssistantActivity } from './CapstoneAssistantThread'
import { commandKey } from './commandKey'
import { buildWorkCommand, buildStartWorkCommand, buildCancelWorkCommand, buildSendMessageCommand, parseStoredWorkCommand, parseWorkSnapshot, type WorkCommand } from './threadWorkProtocol'
import { HttpThreadTransport } from './threadHttpTransport'
import type { ThreadListPage } from './threadManagement'
import { CapstoneThreadClient } from './threadClient'
import { ThreadProjectionStore } from './threadProjectionStore'
import { canReconnect, readPendingCommands, reconnectDelay, writePendingCommands } from './threadSessionState'
import { projectWorkConversation } from './threadWorkMessages'
import SessionNavigation,{SessionAdjacentControls,navigateSession} from './SessionNavigation'
import {sessionManagement} from './sessionManagement'
import {useSessionCatalog,mergeSessionPage} from './sessionCatalog'
import {readWorkspacePanels} from './workspaceEntry'
import ThreadProductsWorkspace,{type ProductRequest} from './ThreadProductsWorkspace'
import type {ContextProductRef} from './threadProducts'
import AnswerDetailSheet from './AnswerDetailSheet'
import AttemptRecordPanel from './AttemptRecordPanel'
import SessionNewPopover from './SessionNewPopover'
import type {InputCatalog,InputSubmission} from './threadInput'
import {sessionTypeNames} from './SessionEntry'
import ProcessProductWorkspace from './ProcessProductWorkspace'
import type {ProcessProduct} from './processProducts'
import SessionHeading from './SessionHeading'
import {displaySessionTitle} from './sessionTitle'
import {parseCommandReceipt,type EventEnvelope} from './threadProtocol'
import NativeArtifactsWorkspace from './NativeArtifactsWorkspace'
import TaskDeliveriesWorkspace from './TaskDeliveriesWorkspace'
import {parseNativeArtifact,projectNativeArtifacts,type NativeArtifact} from './nativeArtifacts'
import ThreadMaterialUpload from './ThreadMaterialUpload'
import type {StoredResource} from './resourceUploads'
import ThreadSettingsMenu from './ThreadSettingsMenu'
import {useSessionViewState,useSessionViewRef} from './workspaceSessionCache'
import ThreadModelDirectory from './ThreadModelDirectory'
import ThreadModelPane from './ThreadModelPane'
import type {ModelWorkspace} from './threadModelWorkspace'
import {buildModelWorkspaceCommand} from './threadWorkProtocol'
import GridSourceWorkspace from './GridSourceWorkspace'
import ElectricalModelWorkspace from './ElectricalModelWorkspace'
import type {GridSourceView} from './gridSource'
import {parseThreadDisplayRequest,selectThreadViewProposal,type ThreadDisplayRequest} from './threadViewRouting'

const statusCopy: Record<string, string> = { ready: '已保存，待执行', queued: '已排队', running: '执行中', completed: '已完成', failed: '执行失败', cancelled: '已取消', interrupted: '执行已中断', blocked: '执行不可用' }
class CommandRejectedError extends Error {}
type InstructionViewState={attemptId:string|null;manual:boolean;appliedSeq:number;automatic:'source'|'model'|null;requestedSource?:ThreadDisplayRequest;requestNonce:number}
const reasonCopy: Record<string, string> = { execution_unavailable: '当前任务的执行能力尚未接通，仍可保存目标和资料。', model_context_required: '当前任务没有专业模型，仍可保存资料。', capability_required: '当前任务尚未启用执行所需的业务能力，仍可保存目标和资料。', attempt_in_progress: '当前会话已有任务正在执行。', case_execution_active: '当前会话已有案例正在执行。', case_context_locked: '当前案例正在使用任务上下文，请等待其完成。', context_change_pending: '任务上下文正在更新，请稍后重试。', thread_archived: '此会话已归档。', run_not_open: '当前运行已关闭。' }

/** Data adapter for the existing workspace and assistant-ui presentation. */
export default function ThreadWorkAdapter({ transport, threadId, namespace, recoveryOnly = false,preparedStore }: {
  transport: HttpThreadTransport; threadId: string; namespace: string; recoveryOnly?: boolean
  preparedStore?:ThreadProjectionStore
}) {
  const [localId, setCurrentId] = useState(threadId)
  const currentId=recoveryOnly?threadId:localId
  const [sessions,setSessions]=useSessionCatalog(namespace)
  useEffect(()=>setCurrentId(threadId),[threadId])
  useEffect(() => {
    if(recoveryOnly)return
    const navigate = () => { const id = new URLSearchParams(window.location.search).get('thread'); if (id) setCurrentId(id) }
    window.addEventListener('popstate', navigate)
    return () => window.removeEventListener('popstate', navigate)
  }, [recoveryOnly])
  return <WorkThreadSession key={currentId} transport={transport} threadId={currentId} namespace={namespace} onNavigate={setCurrentId} recoveryOnly={recoveryOnly} sessions={sessions} setSessions={setSessions} preparedStore={currentId===threadId?preparedStore:undefined}/>
}

function WorkThreadSession({ transport, threadId: currentId, namespace, onNavigate, recoveryOnly,sessions,setSessions,preparedStore }: {
  transport: HttpThreadTransport; threadId: string; namespace: string; onNavigate: (id: string) => void; recoveryOnly: boolean
  sessions:ThreadListPage|null;setSessions:Dispatch<SetStateAction<ThreadListPage|null>>
  preparedStore?:ThreadProjectionStore
}) {
  const mounted = useRef(true)
  useEffect(() => { mounted.current = true; return () => { mounted.current = false } }, [])
  const commandStorageKey = `${namespace}.${currentId}`
  const client=useMemo(()=>new CapstoneThreadClient(transport),[transport])
  const store = useMemo(() => preparedStore??new ThreadProjectionStore(client, commandStorageKey, { protocolVersion: '2' }), [client, commandStorageKey,preparedStore])
  const [projection, setProjection] = useState(store.state)
  const snapshot = projection.workSnapshot
  const professional = snapshot
    ? snapshot.modelContext && projection.snapshot &&
      JSON.stringify(snapshot.modelContext)===JSON.stringify(projection.snapshot.activeModelContext)
      ? projection.snapshot : snapshot.professionalSnapshot??null
    : projection.snapshot
  const nativeChat=!!snapshot&&(snapshot.sessionType==='general-chat'||snapshot.sessionType==='enterprise-research'||snapshot.works.some(work=>work.conversationMode)||(!snapshot.modelContext&&snapshot.nativeExecution!==undefined))
  const conversationExecutionAvailable=Boolean(snapshot?.modelContext)||snapshot?.nativeExecution?.available===true
  const [modelWorkspace,setModelWorkspace]=useState<ModelWorkspace|null>(null)
  const [modelTarget,setModelTarget]=useState('')
  const [modelViewIssue,setModelViewIssue]=useState<string|null>(null)
  const modelRefreshChain=useRef(Promise.resolve())
  const modelPageGeneration=useRef(0)
  useEffect(()=>{
    const context=professional?.activeModelContext
    if(!context)return
    let live=true
    const generation=++modelPageGeneration.current
    setModelViewIssue(null)
    // A reopened Context can have the same model/revision as an old view.
    // Restore its own admitted page even when the store retains another view.
    modelRefreshChain.current=modelRefreshChain.current.catch(()=>{}).then(async()=>{
      if(!live||store.state.snapshot?.activeModelContext.id!==context.id)return
      try{
        await store.restoreHistoricalNetwork(context.id)
        if(!live||store.state.snapshot?.activeModelContext.id!==context.id)return
        await store.refreshModels()
      }catch(cause){
        rethrowDebugCapacity(cause)
        if(live&&generation===modelPageGeneration.current&&store.state.snapshot?.activeModelContext.id===context.id)setModelViewIssue('电气拓扑暂时无法恢复；当前模型选择已保留，请重新连接后重试。')
      }
    })
    return()=>{live=false}
  },[store,currentId,professional?.activeModelContext.id,professional?.activeModelContext.modelRevision])
  useEffect(()=>{
    if(!nativeChat||!snapshot)return
    let live=true
    void client.models(currentId).then(workspace=>{
      if(!live)return
      const entry=workspace?.models.find(model=>model.entryId===workspace.currentEntryId)
      const context=snapshot.modelContext
      if(workspace?.runId!==snapshot.runId || (context ? !entry||entry.modelId!==context.modelId||entry.modelRevision!==context.modelRevision||entry.implementationFamily!==context.implementationFamily : Boolean(entry))) {
        setModelWorkspace(null);return
      }
      setModelWorkspace(workspace)
    }).catch(cause=>{rethrowDebugCapacity(cause);if(live)setModelWorkspace(null)})
    return()=>{live=false}
  },[client,currentId,nativeChat,snapshot?.lastEventSeq,snapshot?.modelContext?.id])
  const recovery=recoveryOnly&&!nativeChat
  const materialRevision=Math.max(0,...store.publicEvents.filter(event=>['material_uploaded','material_removed'].includes(event.eventType)).map(event=>event.eventSeq))
  const [inputCatalog,setInputCatalog]=useState<InputCatalog>()
  const [catalogLoading,setCatalogLoading]=useState(false)
  const [catalogReload,setCatalogReload]=useState(0)
  const [uploadBusy,setUploadBusy]=useState(false)
  const [attachments,setAttachments]=useState<StoredResource[]>([])
  const [attachmentsLoading,setAttachmentsLoading]=useState(true)
  const [attachmentReload,setAttachmentReload]=useState(0)
  useEffect(()=>setUploadBusy(false),[currentId])
  const [productsOpen,setProductsOpen]=useSessionViewState('resource.open',()=>readWorkspacePanels(currentId).resource??false)
  const [resourceView,setResourceView]=useSessionViewState('resource.view',client.supportsProductIndex?'products':'process-products')
  const [instructionView,setInstructionView]=useSessionViewState<InstructionViewState>('resource.instruction-view',{attemptId:null,manual:false,appliedSeq:0,automatic:null,requestNonce:0})
  const instructionViewRef=useRef(instructionView);instructionViewRef.current=instructionView
  const saveInstructionView=useCallback((value:InstructionViewState)=>{instructionViewRef.current=value;setInstructionView(value)},[setInstructionView])
  const [requestedProduct,setRequestedProduct]=useState<ProductRequest>()
  const [requestedReference,setRequestedReference]=useState<{selection:ContextProductRef;nonce:number}>()
  const [inspectedProductAttempt,setInspectedProductAttempt]=useState<string>()
  const [requestedArtifact,setRequestedArtifact]=useState<{attemptId:string;artifactId:string;nonce:number}>()
  const [selectedDeliveryFile,setSelectedDeliveryFile]=useState<NativeArtifact>()
  const [indexedArtifacts,setIndexedArtifacts]=useState<NativeArtifact[]>([])
  const artifactBaseline=useRef<number|null>(null)
  const artifactOpened=useSessionViewRef('resource.touched',false)
  const completedArtifactOpened=useRef(new Set<string>())
  const [processReference,setProcessReference]=useState<ProcessProduct>()
  const [instructionLocation,setInstructionLocation]=useState<{attemptId:string;nonce:number}>()
  const locationGeneration=useRef(0)
  const [reload, setReload] = useState(0)
  const [selected, setSelected] = useState('new')
  const [initialText, setInitialText] = useState('')
  const [restoredKey, setRestoredKey] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [connectionError,setConnectionError]=useState<string>()
  const [connectionRecovering,setConnectionRecovering]=useState(false)
  const [notice, setNotice] = useState('')
  const [acceptedDraft,setAcceptedDraft]=useState<{text:string;commandId:string;submission?:InputSubmission}>()
  const pendingCommand = projection.pendingCommands.find(item => !item.receipt)?.command
  const pending = pendingCommand?.schema === 'capstone-command/2' ? pendingCommand : undefined
  const pendingMessage = pending?.kind === 'work_message' || pending?.kind === 'revise_goal' || pending?.kind === 'send_message' ? pending : undefined
  const drafts = useRef<Record<string, string>>({})
  const [sessionError, setSessionError] = useState(false)
  const [listReload,setListReload]=useState(0)
  const writing = useRef(false)
  const key = `${namespace}.${currentId}.work-draft`
  const persist = useCallback((target: string) => {
    if (!mounted.current) return
    try { sessionStorage.setItem(key, JSON.stringify({ selected: target, drafts: drafts.current })) }
    catch (cause) { rethrowDebugCapacity(cause); /* Keep the current session draft in memory. */ }
  }, [key])
  const onDraftChange = useCallback((text: string) => {
    if (!mounted.current || store.state.pendingCommands.some(item => !item.receipt && ['work_message', 'revise_goal','send_message'].includes(item.command.kind))) return
    drafts.current[selected] = text
    persist(selected)
  }, [selected, persist, store])
  useEffect(()=>{
    if(!nativeChat)return
    const controller=new AbortController()
    setAttachmentsLoading(true)
    void transport.readStoredResources(currentId,controller.signal,true).then(files=>{
      if(!controller.signal.aborted){setAttachments(files);setAttachmentsLoading(false)}
    }).catch(cause=>{if(!controller.signal.aborted)setError(`待发送附件读取失败：${cause.message}`)})
    return()=>controller.abort()
  },[transport,currentId,nativeChat,attachmentReload])
  useEffect(()=>{
    if(!nativeChat)return
    const conversationWork=snapshot?.works.find(work=>work.conversationMode)
    if(conversationWork&&selected==='new'&&!pending){
      setSelected(conversationWork.workId);setInitialText(drafts.current[conversationWork.workId]||drafts.current.new||'');persist(conversationWork.workId)
    }
  },[nativeChat,snapshot,selected,pending,persist])
  useEffect(()=>{
    if(!nativeChat)return
    let live=true
    setCatalogLoading(true)
    void client.inputCatalog(currentId).then(async value=>{
      if(live)setInputCatalog(value)
      if(!value)return
      try{const resources=await transport.readStoredResources(currentId);if(live)setInputCatalog({...value,stored_resources:resources})}catch(cause){rethrowDebugCapacity(cause) /* Keep the existing input catalog available. */}
    }).catch(cause=>{rethrowDebugCapacity(cause);if(live)setInputCatalog(undefined)}).finally(()=>{if(live)setCatalogLoading(false)})
    return()=>{live=false}
  },[client,currentId,nativeChat,catalogReload,materialRevision])
  useEffect(() => {
    const refresh=()=>setListReload(value=>value+1)
    window.addEventListener('capstone-session-renamed',refresh)
    return()=>window.removeEventListener('capstone-session-renamed',refresh)
  },[])
  useEffect(() => {
    setError(null); setNotice('')
    const controller = new AbortController()
    let target = 'new'
    drafts.current = {}
    try {
      const saved = JSON.parse(sessionStorage.getItem(key) || 'null')
      if (saved?.drafts && typeof saved.drafts === 'object') {
        drafts.current = Object.fromEntries(Object.entries(saved.drafts).filter((entry): entry is [string, string] => typeof entry[1] === 'string'))
      }
      if (typeof saved?.selected === 'string') target = saved.selected
      if (saved?.pending && !readPendingCommands(commandStorageKey, currentId).length) writePendingCommands(commandStorageKey, [parseStoredWorkCommand(saved.pending, currentId)])
      const command = readPendingCommands(commandStorageKey, currentId)[0]
      if (command?.schema === 'capstone-command/2') {
        target = command.target.id
        if (command.kind === 'work_message' || command.kind === 'revise_goal'||command.kind==='send_message') drafts.current[target] = String(command.payload.text)
      }
    } catch { /* Invalid local state cannot create or submit a command. */ }
    setSelected(target); setInitialText(drafts.current[target] || ''); setRestoredKey(key)
    return () => controller.abort()
  }, [key, currentId, commandStorageKey])
  useEffect(() => {
    const controller = new AbortController()
    void transport.listThreads(false, undefined, controller.signal).then(page => {
      if (!controller.signal.aborted) { setSessions(previous=>mergeSessionPage(previous,page)); setSessionError(false) }
    }).catch(() => { if (!controller.signal.aborted) setSessionError(true) })
    return () => controller.abort()
  }, [transport, currentId,listReload,snapshot?.sessionTitle?.revision])
  useEffect(() => {
    if (currentId === 'new') return
    let live = true
    const controller = new AbortController()
    let timer: ReturnType<typeof setTimeout> | undefined
    let failures = 0
    const unsubscribe = store.subscribe(() => { if (live) setProjection({ ...store.state }) })
    async function connect() {
      try {
        if(!preparedStore||reload>0)await store.load(currentId)
        if (!live) return
        void store.restoreConversationHistory(controller.signal).catch(()=>{
          if(!controller.signal.aborted)setNotice('部分历史正文暂未读取完成，刷新会话可重试。')
        })
        if(artifactBaseline.current===null)artifactBaseline.current=store.state.eventSeq
        await store.catchUp()
        if (!live) return
        setConnectionError(undefined)
        setConnectionRecovering(false)
        if (store.canStreamEvents) await store.consumeEvents(controller.signal)
      } catch (cause) {
        if (!live || controller.signal.aborted) return
        setConnectionError(cause instanceof Error ? cause.message : '实时连接暂不可用。')
        setConnectionRecovering(canReconnect(cause))
        if (canReconnect(cause)) timer = setTimeout(() => { if (live) void connect() }, reconnectDelay(failures++))
      }
    }
    void connect()
    return () => { live = false; controller.abort(); if (timer) clearTimeout(timer); unsubscribe(); store.dispose() }
  }, [store, currentId, reload])
  function selectWork(target: string) {
    if (pending || writing.current) return
    persist(target); setSelected(target); setInitialText(drafts.current[target] || '')
  }
  async function create() {
    if (writing.current) return
    writing.current = true; setBusy(true); setError(null)
    try {
      const next = parseWorkSnapshot(await transport.createWorkThread())
      if (!mounted.current||!isWorkspaceActive(transport.workspaceName)) return
      const url = new URL(window.location.href)
      url.searchParams.set('workspace', transport.workspaceName); url.searchParams.set('thread', next.threadId)
      window.history.pushState({}, '', url); onNavigate(next.threadId)
    } catch (cause) { setError(cause instanceof Error ? cause.message : '创建失败，请重试。') }
    finally { writing.current = false; setBusy(false) }
  }
  async function prepareSourceQuestion(view: GridSourceView, question: string) {
    if(writing.current)throw new Error('请等待当前操作完成。')
    writing.current=true;setBusy(true)
    let createdId: string | undefined
    try {
      const next=parseWorkSnapshot(await transport.createSession({session_type:'enterprise-research'}))
      createdId=next.threadId
      if(!mounted.current||!isWorkspaceActive(transport.workspaceName))return
      const material={schema:'capstone-grid-source-observation/1',purpose:'frozen_source_observation',
        source_id:view.page.source_id,view_ref:view.page.view_ref,scope:view.page.scope,
        selection:view.page.selection,source_snapshot:view.page.source_snapshot,provenance:view.page.provenance,
        display_grouping_only:view.page.display_grouping_only,electrical_equivalence_performed:false,
        node_kind_counts:view.nodes.reduce<Record<string,number>>((counts,item)=>{counts[item.kind]=(counts[item.kind]||0)+1;return counts},{}),
        edge_kind_counts:view.edges.reduce<Record<string,number>>((counts,item)=>{counts[item.kind]=(counts[item.kind]||0)+1;return counts},{}),
        total_nodes:view.page.total_nodes,total_edges:view.page.total_edges,complete_view_loaded:view.complete,
        source_gaps:view.page.source_gaps,gaps:view.page.gaps,boundary_object_ids:view.page.boundary_object_ids,
        unresolved_endpoint_count:view.unresolvedEndpoints.length,
        record_sample_only:true,sample_limit_per_kind:50,nodes:view.nodes.slice(0,50),edges:view.edges.slice(0,50),
        limitations:['This source display is not a calculation model.','Record samples cannot establish rankings or full connectivity.']}
      await transport.uploadThreadMaterial(next.threadId,new File([JSON.stringify(material,null,2)],'grid-source-observation.json',{type:'application/json'}))
      if(!mounted.current||!isWorkspaceActive(transport.workspaceName))return
      const text=`${question}\n\n请依据所附 grid-source-observation.json 的冻结来源摘要回答；区分完整视图总数与抽样对象，说明源质量缺口，不推断未提供的潮流或电气连通性。`
      sessionStorage.setItem(`${namespace}.${next.threadId}.work-draft`,JSON.stringify({selected:'new',drafts:{new:text}}))
      const url=new URL(window.location.href);url.searchParams.set('workspace',transport.workspaceName);url.searchParams.set('thread',next.threadId)
      setProductsOpen(false);setResourceView('products')
      window.history.pushState({},'',url);onNavigate(next.threadId)
    } catch(cause) {
      throw new Error(`${cause instanceof Error?cause.message:'源资料准备失败。'}${createdId?` 已创建会话 ${createdId}，可从历史会话继续。`:''}`)
    } finally {writing.current=false;if(mounted.current)setBusy(false)}
  }
  const selectedWork = snapshot?.works.find(work => work.workId === selected)
  const viewingLegacy=nativeChat&&!!selectedWork&&!selectedWork.conversationMode
  const liveConversation=nativeChat&&!viewingLegacy
  const legacyWorks=nativeChat?snapshot?.works.filter(work=>!work.conversationMode):snapshot?.works
  const active = selectedWork?.status === 'queued' || selectedWork?.status === 'running'
  const currentAttempt=snapshot?.currentAttempt||professional?.currentAttempt
  const canStop = active && selectedWork.latestAttemptId === currentAttempt?.attemptId
  async function dispatch(command: WorkCommand) {
    if ((recovery||viewingLegacy) && !(pending && JSON.stringify(command) === JSON.stringify(pending)) && !(command.kind === 'cancel_work' && canStop && !pending)) throw new Error('此入口只可确认原请求或停止已有执行。')
    if (writing.current) throw new Error('请等待当前操作完成。')
    writing.current = true; setBusy(true); setError(null); setNotice('')
    try {
      const receipt = await store.dispatch(command)
      if (!mounted.current) return
      if (receipt.status === 'rejected') throw new CommandRejectedError(receipt.rejection === 'revision_conflict' ? '任务已更新，请核对最新内容后再次提交。' : receipt.rejection === 'product_context_unavailable' ? '引用的成果暂时无法加入本轮资料。指令未执行，请检查引用后重试。' : `未保存：${receipt.rejection || '请求被拒绝'}`)
      if (receipt.status !== 'accepted') throw new Error('操作结果待确认，请重试原请求。')
      if(command.kind==='send_message'){
        const payload=command.payload as {text:string}&Partial<InputSubmission>
        setAttachments(files=>files.filter(file=>!payload.attachment_refs?.includes(file.resource_id)))
        setCatalogReload(value=>value+1)
        const submission=payload.input&&payload.context_selection?{input:payload.input,context_selection:payload.context_selection,...(payload.llm_profile_id===undefined?{}:{llm_profile_id:payload.llm_profile_id}),...(payload.deep_research===undefined?{}:{deep_research:payload.deep_research}),...(payload.resource_profile?{resource_profile:payload.resource_profile}:{}),...(payload.material_refs!==undefined?{material_refs:payload.material_refs}:{}),...(payload.context_product_refs!==undefined?{context_product_refs:payload.context_product_refs}:{})}:undefined
        setAcceptedDraft({text:payload.text,commandId:command.command_id,submission})
      }
      if (command.kind === 'work_message' || command.kind === 'revise_goal'||command.kind==='send_message') { drafts.current[selected] = ''; persist(selected) }
      setNotice(command.target.kind==='model_workspace'?'模型选择已更新。':command.kind==='send_message'?'':command.kind === 'start_work' ? '执行请求已接收；排队、执行与结果以实际任务状态为准。' : command.kind === 'cancel_work' ? active ? '停止请求已接收，正在等待实际执行停止。' : '停止请求已确认。' : '任务已保存。保存资料不会自动启动分析。')
      await store.refreshWorkSnapshot().catch(cause => { if (mounted.current) setError(cause.message) })
      if (!mounted.current) return
      if (command.target.kind==='work' && selected === 'new' && typeof receipt.target?.id === 'string' && receipt.target.id !== 'new') {
        const id = receipt.target.id; setSelected(id); setInitialText(drafts.current[id] || ''); persist(id)
      }
    } catch (cause) {
      if (mounted.current) setError(cause instanceof Error ? cause.message : '操作结果待确认，请重试原请求。')
      if (mounted.current && !(cause instanceof CommandRejectedError) && canReconnect(cause)) setReload(value => value + 1)
      throw cause
    } finally { writing.current = false; if (mounted.current) setBusy(false) }
  }
  async function changeModel(kind:'open_model'|'activate_model'|'close_model',payload:Record<string,string>) {
    if(!snapshot||!modelWorkspace)throw new Error('请先同步模型目录。')
    try{
      await dispatch(buildModelWorkspaceCommand(currentId,snapshot.runId,`cmd_${commandKey()}`,`idem_${commandKey()}`,modelWorkspace.eventSeq,kind,payload))
      markManualView()
      if(kind==='open_model'||kind==='activate_model'){
        artifactOpened.current=true;setResourceView('model');setProductsOpen(true)
        if(store.state.snapshot)store.viewGridPage(store.state.snapshot.activeGridPageId)
      }
    }
    catch{/* dispatch retains the error and exact request for recovery. */}
  }
  async function send(text: string,submission?:InputSubmission) {
    if(nativeChat&&!pendingMessage){
      if(attachmentsLoading)throw new MessageNotSentError('正在确认待发送附件，请稍后发送。')
      submission={...(submission||{input:{kind:'text',text},context_selection:{include_refs:[],exclude_refs:[]}}),attachment_refs:attachments.map(file=>file.resource_id)}
    }
    const runId = snapshot?.runId ?? professional?.run.runId
    if (!runId) throw new MessageNotSentError('请先连接会话。')
    try {
      await dispatch(pendingMessage || (nativeChat?buildSendMessageCommand(currentId,runId,`cmd_${commandKey()}`,`idem_${commandKey()}`,selected,selectedWork?.revision||0,text,submission,processReference?.threadId===currentId?processReference.attemptId:undefined):buildWorkCommand(currentId, runId, `cmd_${commandKey()}`, `idem_${commandKey()}`, selected, selectedWork?.revision || 0, text)))
    } catch (cause) { throw new MessageNotSentError(cause instanceof Error ? cause.message : '保存结果待确认。') }
  }
  async function start() {
    if (!selectedWork || !snapshot || ((recovery||nativeChat) && pending?.kind !== 'start_work')) return
    try {
      await dispatch(pending?.kind === 'start_work' ? pending : buildStartWorkCommand(currentId, snapshot.runId, `cmd_${commandKey()}`, `idem_${commandKey()}`, selectedWork.workId, selectedWork.revision))
    } catch { /* The shared store retains uncertain requests for explicit retry. */ }
  }
  async function cancel() {
    if (!selectedWork || !snapshot || (pending?.kind !== 'cancel_work' && !canStop)) return
    try {
      await dispatch(pending?.kind === 'cancel_work' ? pending : buildCancelWorkCommand(currentId, snapshot.runId, `cmd_${commandKey()}`, `idem_${commandKey()}`, selectedWork.workId, selectedWork.revision))
    } catch { /* The original cancel request remains recoverable through the shared command store. */ }
  }
  async function recoverLegacyCommand() {
    if (!pendingCommand || pendingCommand.schema !== 'capstone-command/1' || writing.current) return
    writing.current = true; setBusy(true)
    try {
      const receipt = await store.dispatch(pendingCommand)
      if (!mounted.current) return
      setNotice(receipt.status === 'rejected' ? '原对话请求未获接收，请核对历史记录。' : '原对话请求已确认。')
      await store.refreshWorkSnapshot()
    } catch (cause) {
      if (mounted.current) { setError(cause instanceof Error ? cause.message : '原请求结果待确认。'); if (canReconnect(cause)) setReload(value => value + 1) }
    } finally { writing.current = false; if (mounted.current) setBusy(false) }
  }
  const conversation = projectWorkConversation(store.conversationEvents, selectedWork, snapshot?.works, !snapshot)
  const latestAcceptedInstruction=useMemo(()=>store.publicEvents.reduce<EventEnvelope|undefined>((latest,event)=>
    event.eventType==='command_accepted'&&event.attemptId&&['send_message','send_auto','send_ordinary','send_professional'].includes(String(event.payload.kind))&&(!latest||event.eventSeq>latest.eventSeq)?event:latest,undefined),[store,projection])
  const declaredAttemptId=selectedWork?.latestAttemptId||currentAttempt?.attemptId
  const latestInstructionAttempt=latestAcceptedInstruction&&(!declaredAttemptId||latestAcceptedInstruction.eventSeq>(snapshot?.lastEventSeq??0))?latestAcceptedInstruction.attemptId:declaredAttemptId
  const viewProposal=useMemo(()=>selectThreadViewProposal({events:store.publicEvents,networkTasks:store.networkTasks,attemptId:latestInstructionAttempt,currentContext:professional?.activeModelContext}),[store,projection,latestInstructionAttempt,professional?.activeModelContext])
  // Reconstruct associations from admitted events, including loaded history.
  // Selecting a saved presentation never dispatches a business command.
  const instructionViews=useMemo(()=>{
    const attempts=new Set(store.publicEvents.map(event=>event.attemptId).filter((id):id is string=>!!id))
    return new Map([...attempts].flatMap(attemptId=>{
      const proposal=selectThreadViewProposal({events:store.publicEvents,networkTasks:store.networkTasks,attemptId,currentContext:professional?.activeModelContext})
      return proposal?[[attemptId,proposal] as const]:[]
    }))
  },[store,projection,professional?.activeModelContext])
  function showInstructionNetwork(attemptId:string){
    const proposal=instructionViews.get(attemptId)
    if(!proposal)return
    markManualView()
    if(proposal.kind==='source'){
      saveInstructionView({...instructionViewRef.current,requestedSource:proposal.request,requestNonce:instructionViewRef.current.requestNonce+1})
      setResourceView('source-topology')
    }else{
      store.viewGridPage(proposal.pageId);setResourceView('model')
    }
    setProductsOpen(true)
  }
  function markManualView(){
    saveInstructionView({...instructionViewRef.current,attemptId:latestInstructionAttempt??null,manual:true,automatic:null})
    artifactOpened.current=true
  }
  function selectResourceView(id:string){markManualView();setResourceView(id);setProductsOpen(true)}
  function browseElectricalModels(){
    markManualView()
    saveInstructionView({...instructionViewRef.current,requestedSource:undefined,requestNonce:instructionViewRef.current.requestNonce+1})
  }
  function setResourcePanelOpen(open:boolean){markManualView();setProductsOpen(open)}
  useEffect(()=>{
    if(!liveConversation||!latestInstructionAttempt)return
    let state=instructionViewRef.current
    if(state.attemptId!==latestInstructionAttempt){
      // Refresh can first replay an older history page. It is not a new instruction.
      if(latestAcceptedInstruction&&latestAcceptedInstruction.eventSeq<=state.appliedSeq)return
      // Reading and background model downloads outlive one agent instruction.
      // Reset proposal ownership without closing the user's current resource.
      state={...state,attemptId:latestInstructionAttempt,manual:state.attemptId===null&&state.manual,appliedSeq:0,automatic:null}
      saveInstructionView(state)
    }
    if(state.manual||!viewProposal||viewProposal.eventSeq<=state.appliedSeq)return
    if(viewProposal.kind==='source'){
      const identical=state.automatic==='source'&&JSON.stringify(state.requestedSource)===JSON.stringify(viewProposal.request)
      saveInstructionView({...state,appliedSeq:viewProposal.eventSeq,automatic:'source',requestedSource:viewProposal.request,requestNonce:state.requestNonce+(identical?0:1)})
      setResourceView('source-topology')
    }else{
      saveInstructionView({...state,appliedSeq:viewProposal.eventSeq,automatic:'model'})
      store.viewGridPage(viewProposal.pageId);setResourceView('model')
    }
    artifactOpened.current=true;setProductsOpen(true)
  },[liveConversation,latestInstructionAttempt,latestAcceptedInstruction,viewProposal,resourceView,store,saveInstructionView,client.supportsProductIndex])
  const requestedSourceView=parseThreadDisplayRequest(instructionView.requestedSource)??undefined
  const nativeFiles=projectNativeArtifacts(conversation.events)
  const attemptLabels=Object.fromEntries(conversation.events.filter(event=>event.eventType==='command_accepted'&&event.attemptId).flatMap(event=>{
    const nested=event.payload.payload as Record<string,unknown>|undefined
    const text=typeof event.payload.text==='string'?event.payload.text:typeof nested?.text==='string'?nested.text:undefined
    return text?[[event.attemptId!,`${new Date(event.occurredAt).toLocaleString('zh-CN',{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false})} · ${text}`]]:[]
  }))
  const nativeAttemptIds=[...new Set([...nativeFiles.map(file=>file.attempt_id),...conversation.events.filter(event=>event.attemptId&&!event.modelContextId).map(event=>event.attemptId!),...(selectedWork?.conversationMode&&selectedWork.latestAttemptId?[selectedWork.latestAttemptId]:[])])]
  function openArtifact(file:NativeArtifact,manual=true) {
    if(manual)markManualView()
    artifactOpened.current=true
    setRequestedArtifact({attemptId:file.attempt_id,artifactId:file.artifact_id,nonce:Date.now()})
    setRequestedProduct({origin:'native_file',attemptId:file.attempt_id,artifactId:file.artifact_id,workId:file.work_id,nonce:Date.now()});setResourceView(client.supportsProductIndex?'products':'native-files');setProductsOpen(true)
  }
  useEffect(()=>{
    // The completed index ranks the final primary set. An early publication may
    // be a CSV; passing it as a request would pin it like a manual selection.
    if(client.supportsProductIndex||!nativeChat||artifactOpened.current||artifactBaseline.current===null)return
    const newFiles=projectNativeArtifacts(conversation.events.filter(event=>event.eventSeq>artifactBaseline.current!))
    const primary=newFiles.find(file=>file.presentation_role==='primary')
    if(primary)openArtifact(primary,false)
  },[client.supportsProductIndex,nativeChat,projection.eventSeq,selected])
  async function locateInstruction(attemptId:string) {
    const generation=++locationGeneration.current
    const found=()=>store.publicEvents.some(event=>event.attemptId===attemptId&&event.eventType==='command_accepted')
    try{
      for(let page=0;!found()&&store.state.hasOlderHistory&&page<applicationCapacity('artifact_initial_pages');page++){
        await store.loadOlderHistory()
        if(!mounted.current||generation!==locationGeneration.current)return
      }
      if(!mounted.current||generation!==locationGeneration.current)return
      if(found()){markManualView();setInstructionLocation({attemptId,nonce:generation});setProductsOpen(false)}
      else setNotice('原指令尚未加载，可继续读取更早的历史。')
    }catch(cause){rethrowDebugCapacity(cause);if(mounted.current&&generation===locationGeneration.current)setError('原指令暂时无法定位，请重试。')}
  }
  const startReason = selectedWork?.startUnavailableReason || selectedWork?.blockedReason
  const terminalRevision=Math.max(0,...store.publicEvents.filter(event=>['attempt_completed','attempt_failed','attempt_cancelled','attempt_interrupted','native_artifact_published','delivery_published'].includes(event.eventType)).map(event=>event.eventSeq))
  const processPanel=<ProcessProductWorkspace client={client} threadId={currentId} revision={terminalRevision} onReference={setProcessReference} onLocate={attemptId=>void locateInstruction(attemptId)} />
  const filesPanel=<NativeArtifactsWorkspace client={client} threadId={currentId} attemptIds={nativeAttemptIds} revision={terminalRevision} requestedArtifact={requestedArtifact} attemptLabels={attemptLabels} onAdopt={file=>{markManualView();setSelectedDeliveryFile(file);setResourceView('deliveries');setProductsOpen(true)}}/>
  const productsPanel=<ThreadProductsWorkspace key={currentId} client={client} threadId={currentId} workId={selectedWork?.workId} revision={terminalRevision} requested={requestedProduct}
    onIndexLoaded={entries=>{
      const files=entries.flatMap(entry=>{
        if(entry.ref.origin!=='native_file'||!entry.ref.attempt_id||entry.ref.thread_id!==currentId||entry.ref.work_id!==selectedWork?.workId)return []
        try{const file=parseNativeArtifact(entry.source,currentId,entry.ref.attempt_id);return file.sha256===entry.ref.digest&&file.work_id===entry.ref.work_id?[file]:[]}catch{return []}
      })
      setIndexedArtifacts(previous=>JSON.stringify(previous)===JSON.stringify(files)?previous:files)
    }}
    primaryAttemptId={selectedWork?.status==='completed'?selectedWork.latestAttemptId||undefined:undefined}
    onPrimaryReady={entry=>{
      const attempt=entry.ref.attempt_id
      if(!attempt||completedArtifactOpened.current.has(attempt)||(productsOpen&&artifactOpened.current)||instructionViewRef.current.manual&&instructionViewRef.current.attemptId===latestInstructionAttempt)return
      completedArtifactOpened.current.add(attempt);artifactOpened.current=true
      setResourceView('products');setProductsOpen(true)
    }}
    onReference={(entry,excerpt)=>setRequestedReference({selection:{ref:entry.ref,purpose:'historical-context',...(excerpt?{excerpt}:{})},nonce:Date.now()})}
    onAdopt={file=>{markManualView();setSelectedDeliveryFile(file);setResourceView('deliveries');setProductsOpen(true)}} onLocate={attemptId=>void locateInstruction(attemptId)} onBrowse={markManualView} onInspect={setInspectedProductAttempt}
    fallback={<><details open={requestedProduct?.origin==='native_file'}><summary>指令文件</summary>{filesPanel}</details><details><summary>任务交付</summary><TaskDeliveriesWorkspace client={client} threadId={currentId} revision={terminalRevision}/></details><details><summary>过程记录</summary>{processPanel}</details></>}/>
  const materials=inputCatalog?.materials||[]
  const remainingMaterialBytes=Math.max(0,applicationCapacity('inline_material_bytes')-materials.reduce((sum,item)=>sum+(item.size_bytes||0),0))
  const activeModelPage=professional?.activeGridPageId
  const viewedModelPage=projection.viewedGridPageId||activeModelPage
  // A stale page with the active page ID is not an intentional history view.
  const modelGridPages=projection.gridPages.filter(page=>page.pageId!==activeModelPage
    ||page.context.id===professional?.activeModelContext.id)
  const historicalModel=Boolean(professional&&viewedModelPage!==activeModelPage)
  const automaticModelView=instructionView.automatic==='model'&&!instructionView.manual&&instructionView.attemptId===latestInstructionAttempt&&viewProposal?.kind==='model'?viewProposal:undefined
  const currentModelView=automaticModelView?.view||(professional?modelGridPages.find(page=>
    page.context.id===professional.activeModelContext.id&&page.pageId===activeModelPage)?.networkView:null)
  const displayedModelPage=modelGridPages.find(page=>page.pageId===viewedModelPage)
  const displayedModelView=historicalModel?displayedModelPage?.networkView:currentModelView
  const displayedModelContext=historicalModel?displayedModelPage?.context:professional?.activeModelContext
  // Ordinal 1 also belongs to taskless base diagrams. Only an exact admitted
  // task/view identity can associate the displayed layer with an Attempt.
  const displayedModelTask=displayedModelView?store.networkTasks.find(task=>
    task.presentationSource!=='historical_baseline'&&task.context.id===displayedModelContext?.id&&task.pageId===viewedModelPage&&task.view===displayedModelView):undefined
  async function selectModelPage(pageId:string){
    markManualView()
    const generation=++modelPageGeneration.current
    store.viewGridPage(pageId);setModelViewIssue(null)
    const page=store.state.gridPages.find(item=>item.pageId===pageId)
    if(!page||page.networkView)return
    try{
      const restoredPage=await store.restoreHistoricalNetwork(page.context.id)
      if(mounted.current&&generation===modelPageGeneration.current&&store.state.viewedGridPageId===pageId)store.viewGridPage(restoredPage)
    }
    catch(cause){
      rethrowDebugCapacity(cause)
      if(mounted.current&&generation===modelPageGeneration.current)setModelViewIssue('该历史模型没有可验证的电气拓扑，请重新连接后重试。')
    }
  }
  const formalModelPanel=professional&&activeModelPage&&viewedModelPage?<>
    {modelGridPages.length>1&&<label>电气拓扑视图<select aria-label="电气拓扑视图" value={viewedModelPage} onChange={event=>void selectModelPage(event.target.value)}>
      {modelGridPages.map(page=><option key={page.pageId} value={page.pageId}>{projection.catalog?.models.find(model=>model.modelId===page.context.modelId)?.displayName||page.context.modelId}{page.context.id===professional.activeModelContext.id?' · 当前模型':' · 历史只读'}</option>)}
    </select></label>}
    <ThreadModelPane snapshot={professional} activePage={activeModelPage} viewedPage={viewedModelPage}
      gridPages={modelGridPages} workingPages={store.modelWorkingPages} isHistorical={historicalModel}
      projectionEventSeq={projection.eventSeq} previewDiagram={null} networkView={currentModelView}
      instructionLabel={displayedModelTask?'已保存任务图层':'模型基础拓扑'} networkTaskId={displayedModelTask?.attemptId}
      cameraStorageKey={`${commandStorageKey}.network-cameras`} modelOptions={projection.catalog?.models||[]}
      onSelectPage={pageId=>void selectModelPage(pageId)} feedback={modelViewIssue}
      modelBusy={busy||active||!!currentAttempt||projection.connection!=='live'}
      onOpenHistoricalModel={(modelId,revision)=>void changeModel('open_model',{model_id:modelId,model_revision:revision})}/>
  </>:null
  return <ThreadWorkspace sessionKey={currentId} conversationOnly subtitle="企业任务工作台"
    headerActions={<SessionConnectionStatus state={projection.connection} error={connectionError} recovering={connectionRecovering} pending={!!pending}/>}
    navigationFooter={<WorkspaceGatewayStatus transport={transport}/>}
    resourcePanel={nativeChat?(client.supportsProductIndex?productsPanel:client.supportsProcessProducts?processPanel:undefined):undefined}
    resourceViews={nativeChat?client.supportsProductIndex?[...(formalModelPanel?[{id:'model',label:'电气拓扑',content:formalModelPanel,description:'注册计算模型的母线与支路；来源和修订保持实际绑定。'}]:[]),{id:'products',label:'Artifacts',content:productsPanel,description:'任务交付与指令产物，保留真实来源和版本。'},...(resourceView==='source-topology'?[{id:'source-topology',label:'电网图',content:resourceView==='source-topology'&&productsOpen?(requestedSourceView?.schema==='capstone-grid-source-view-request/1'?<><button onClick={browseElectricalModels}>浏览电网模型目录</button><GridSourceWorkspace key={requestedSourceView.scope_id} transport={transport} onQuestion={prepareSourceQuestion} requestedView={requestedSourceView} requestNonce={instructionView.requestNonce} onManualNavigate={markManualView}/></>:<ElectricalModelWorkspace storageKey={`${namespace}.${currentId}.electrical-view`} transport={transport} requestedView={requestedSourceView} requestNonce={instructionView.requestNonce} onManualNavigate={markManualView}/>):null,description:'源拓扑、显示分组与来源质量。'}]:[]),...(selectedDeliveryFile?[{id:'deliveries',label:'采用为任务交付',content:<TaskDeliveriesWorkspace client={client} threadId={currentId} revision={terminalRevision} requestedArtifact={selectedDeliveryFile} onPublished={()=>{setResourceView('products');window.dispatchEvent(new Event('capstone-session-renamed'))}}/>}]:[])]:[{id:'process-products',label:'过程制品',content:processPanel,description:'指令执行结果与未完成记录，保留原始归属。'},
      {id:'native-files',label:'指令文件',content:<NativeArtifactsWorkspace client={client} threadId={currentId} attemptIds={nativeAttemptIds} revision={terminalRevision} requestedArtifact={requestedArtifact} attemptLabels={attemptLabels} onAdopt={file=>{markManualView();setSelectedDeliveryFile(file);setResourceView('deliveries');setProductsOpen(true)}}/>,description:'本轮执行生成并保存的真实文件。'},
      {id:'deliveries',label:'任务交付',content:<TaskDeliveriesWorkspace client={client} threadId={currentId} revision={terminalRevision} requestedArtifact={selectedDeliveryFile} onPublished={()=>{setResourceView('deliveries');window.dispatchEvent(new Event('capstone-session-renamed'))}}/>,description:'按用户提出的交付要求组织和修订。'}]:undefined}
    selectedResourceView={resourceView} onResourceViewChange={selectResourceView}
    resourceLabel={resourceView==='model'?'电气拓扑':resourceView==='source-topology'?'电网图':resourceView==='products'?'Artifacts':resourceView==='native-files'?'指令文件':resourceView==='deliveries'?'任务交付':'过程制品'} resourcePanelOpen={productsOpen} onResourcePanelOpenChange={setResourcePanelOpen}
    sidebar={<nav className="thread-session-navigation" aria-label="任务与会话">
      {currentId==='new'&&!recoveryOnly&&!nativeChat?<button className="thread-session-new" disabled={busy} onClick={()=>void create()}><Plus aria-hidden="true" size={16}/>新建任务会话</button>:<SessionNewPopover onCreated={navigateSession} />}
      {snapshot&&(!nativeChat||!!legacyWorks?.length)&&<h2>{nativeChat?'历史保存记录':'当前会话'}</h2>}
      {viewingLegacy&&<button type="button" disabled={busy||!!pending} onClick={()=>selectWork(snapshot?.works.find(work=>work.conversationMode)?.workId||'new')}>返回当前对话</button>}
      {!recoveryOnly&&!nativeChat && <button aria-pressed={selected === 'new'} disabled={busy || !!pending} onClick={() => selectWork('new')}>新的任务目标</button>}
      {legacyWorks?.map((work, index) => <button key={work.workId} aria-pressed={selected === work.workId}
        disabled={busy || !!pending} onClick={() => selectWork(work.workId)} title={work.goal}>{String(index + 1).padStart(2, '0')} · {work.goal}</button>)}
      {sessionError && <p role="status">会话列表暂不可用，当前任务仍可使用。</p>}
      <SessionNavigation items={sessions?.threads||[]} currentId={currentId} storageKey={namespace} actions={sessionManagement(transport,change=>{if(change)setSessions(previous=>previous?{...previous,threads:previous.threads.filter(item=>item.threadId!==change.remove)}:null);setListReload(value=>value+1)})} />
    </nav>}
    workspaceActions={currentId !== 'new' && <><SessionAdjacentControls items={sessions?.threads||[]} currentId={currentId} storageKey={namespace}/><button type="button" className="thread-control-button thread-session-refresh" aria-label="刷新任务" title="刷新会话状态，不重新执行任务" onClick={() => setReload(value => value + 1)}><RefreshCw aria-hidden="true" size={16} /></button></>}
    heading={<><div className="thread-chat-heading"><SessionHeading title={(snapshot?.sessionTitle&&displaySessionTitle(snapshot.sessionTitle))||(nativeChat?(snapshot.sessionType&&sessionTypeNames[snapshot.sessionType])||'工作会话':'历史任务会话')}
      subtitle={nativeChat?undefined:selectedWork ? `修订 ${selectedWork.goalRevision} · ${selectedWork.cancelRequested ? '停止请求中' : statusCopy[selectedWork.status] || selectedWork.status}` : '对话与任务记录'}
      onSave={snapshot?async text=>{
        const request=commandKey()
        const receipt=parseCommandReceipt(await transport.renameSession(currentId,snapshot.runId,snapshot.sessionTitle?.revision||0,text,`cmd_${request}`,`idem_${request}`))
        if(receipt.status!=='accepted')throw new Error('会话名称尚未保存。')
        if(receipt.acceptedEventSeq)await store.catchUpThrough(receipt.acceptedEventSeq)
        await store.refreshWorkSnapshot()
        window.dispatchEvent(new Event('capstone-session-renamed'))
      }:undefined} />
      <div className="thread-chat-heading-meta">
        {nativeChat&&pending?.kind==='send_message'&&<button type="button" className="thread-control-button" disabled={busy||projection.connection!=='live'} onClick={()=>void send(String(pending.payload.text)).catch(()=>{})}>重试发送请求</button>}
        {pending?.kind === 'cancel_work' && !canStop && <button type="button" className="thread-control-button" disabled={busy || projection.connection !== 'live'} onClick={() => void cancel()}>重试停止请求</button>}
        {pendingCommand?.schema === 'capstone-command/1' && <button type="button" className="thread-control-button" disabled={busy || projection.connection !== 'live'} onClick={() => void recoverLegacyCommand()}>重试原对话请求</button>}
        {selectedWork && ((!recovery&&!nativeChat) || pending?.kind === 'start_work') && <button type="button" className="thread-primary-button" disabled={busy || (!!pending && pending.kind !== 'start_work') || (!selectedWork.startAvailable && pending?.kind !== 'start_work') || projection.connection !== 'live'}
          aria-describedby={!selectedWork.startAvailable ? 'work-start-reason' : undefined} onClick={() => void start()}>{pending?.kind === 'start_work' ? '重试执行请求' : '开始任务'}</button>}
      </div>
    </div>
      {inspectedProductAttempt&&<AnswerDetailSheet title="执行详情" answerLabel="所选成果的来源指令" onClose={()=>setInspectedProductAttempt(undefined)}><AttemptRecordPanel attemptId={inspectedProductAttempt} read={(id,after)=>client.attemptRecords(currentId,id,after)}/></AnswerDetailSheet>}
      {recovery && <p role="status">此会话使用旧版任务协议，可查看历史、保留草稿、确认原请求及停止已有执行；当前入口尚不能继续发送。可新建会话继续工作。</p>}
      {viewingLegacy&&<p role="status">正在查看历史保存记录，可保留草稿、确认原请求及停止已有执行。返回当前对话后可继续发送。</p>}
      {nativeChat&&!conversationExecutionAvailable&&<p role="status">当前会话的执行能力暂不可用，可保留草稿并稍后重试。</p>}
      {pending?.target.kind==='model_workspace'&&<button type="button" className="thread-control-button" disabled={busy||projection.connection!=='live'} onClick={()=>void dispatch(pending).catch(()=>{})}>重试模型选择请求</button>}
      {error && <p role="alert">{error}</p>}
      {!nativeChat&&selectedWork && !selectedWork.startAvailable && <p id="work-start-reason" role="status">{startReason ? reasonCopy[startReason] || '当前任务暂不可启动，请刷新后查看最新状态。仍可保存目标和资料。' : '当前任务暂不可启动，仍可保存资料。'}</p>}
      {notice && <p role="status">{notice}</p>}
      {conversation.hasUnattributedHistory && <p role="status">部分历史执行记录尚未确认任务归属。可加载更早的记录后查看。</p>}
    </>}
  >
    {restoredKey === key && (snapshot || professional || currentId === 'new') && <CapstoneAssistantThread nativeArtifactProjections={indexedArtifacts} resultHistoryNotice={resultProjectionHistoryText(professional)} key={liveConversation?`${key}.conversation`:`${key}.${selected}`} events={conversation.events}
      productReferenceReader={(ref,signal)=>client.resolveProduct(ref,signal)} requestedProductReference={requestedReference?.selection.ref.thread_id===currentId?requestedReference:undefined}
      projectedMessages={conversation.messages} composerMode={liveConversation?undefined:'text'} composerLabel={viewingLegacy?'历史记录草稿':nativeChat?undefined:selected === 'new' ? '任务目标' : '补充任务资料'}
      onOpenNativeArtifact={nativeChat?openArtifact:undefined}
      composerPlaceholder={snapshot?.sessionType==='enterprise-research'?'提出研究问题，或上传资料开始分析…':snapshot?.sessionType==='general-chat'?'输入问题，或聊聊你的想法…':undefined}
      onOpenAnswerDetail={nativeChat?()=>setResourcePanelOpen(false):undefined}
      runtimeMode={snapshot?.runtimeMode} connectionState={projection.connection} instructionLocation={instructionLocation}
      networkAttemptIds={[...instructionViews.keys()]} onShowNetwork={showInstructionNetwork}
      acceptedDraft={nativeChat?acceptedDraft:undefined}
      composerControls={liveConversation?(historyActions,inputActions)=><>{modelWorkspace&&<ThreadModelDirectory models={projection.catalog?.models||[]} currentModelId={snapshot?.modelContext?.modelId||''} target={modelTarget} onTargetChange={setModelTarget} disabled={busy||active||!!currentAttempt||projection.connection!=='live'} pending={!!pending} workspace={modelWorkspace} allowEmpty={snapshot?.sessionType==='enterprise-research'||snapshot?.sessionType==='general-chat'} onSwitch={modelId=>void changeModel('open_model',{model_id:modelId})} onActivate={entryId=>void changeModel('activate_model',{entry_id:entryId})} onClose={entryId=>void changeModel('close_model',{entry_id:entryId})}/>}
      <ThreadMaterialUpload threadId={currentId} upload={(file,signal)=>client.uploadThreadMaterial(currentId,file,signal)} resourceUpload={(file,options)=>transport.uploadThreadResource(currentId,file,options)} cancelResource={id=>transport.cancelResourceUpload(currentId,id)} disabled={busy||active||!!pending} remainingFiles={Math.max(0,applicationCapacity('inline_material_count')-materials.length)} remainingBytes={materials.length>=applicationCapacity('inline_material_count')?0:remainingMaterialBytes} onBusyChange={setUploadBusy} onUploaded={material=>{inputActions.addMaterial(material.material_id);setCatalogReload(value=>value+1)}}
        attachments={attachments} onResourceUploaded={()=>setAttachmentReload(value=>value+1)} onRemoveAttachment={async id=>{
          await transport.cancelResourceUpload(currentId,id.replace('resource_','upload_'))
          setAttachments(files=>files.filter(file=>file.resource_id!==id))
        }}/>{processReference&&<span className="process-reference" title={processReference.instruction}>引用：{processReference.instruction.slice(0,36)}<button type="button" aria-label="移除指令引用" onClick={()=>setProcessReference(undefined)}>×</button></span>}<ThreadSettingsMenu>{historyActions}</ThreadSettingsMenu></>:undefined}
      onRemoveMaterial={nativeChat?async id=>{const result=await client.removeThreadMaterial(currentId,id) as {removed?:string};if(result?.removed!==id)throw new Error('资料尚未移除。');setCatalogReload(value=>value+1)}:undefined}
      inputCatalog={inputCatalog} inputCatalogLoading={catalogLoading} onRefreshInputCatalog={()=>setCatalogReload(value=>value+1)} inputControlsDisabled={busy||active||!!pending||uploadBusy}
      sendLabel={viewingLegacy?'确认原保存请求':nativeChat?pendingMessage?'重试发送':'发送':pendingMessage ? '重试保存' : '保存任务'} initialText={initialText} onDraftChange={onDraftChange}
      storageKey={liveConversation?`${key}.conversation`:`${key}.${selected}`} disabled={((recovery||viewingLegacy) && !pendingMessage) || (nativeChat&&!conversationExecutionAvailable&&!pendingMessage) || busy || uploadBusy || (!snapshot && !professional) || ((!nativeChat||!pendingMessage)&&(!!currentAttempt||active)) || (!!pendingCommand && !pendingMessage) || projection.connection !== 'live'} lockDraft={!!pendingMessage}
      isRunning={active} canCancel={canStop}
      cancelLabel={pending?.kind === 'cancel_work' ? '重试停止请求' : selectedWork?.cancelRequested ? '停止请求中' : '停止任务'}
      cancelDisabled={busy || projection.connection !== 'live' || (!!pending && pending.kind !== 'cancel_work') || (selectedWork?.cancelRequested === true && pending?.kind !== 'cancel_work')}
      activity={projectAssistantActivity(conversation.events)}
      runtimeStatus={nativeChat?undefined:<span>目标与资料保存在当前任务中。保存不会自动启动执行。</span>}
      emptyState={<div className="capstone-chat-empty"><strong>{snapshot?.sessionType==='enterprise-research'?'从资料或研究问题开始':snapshot?.sessionType==='general-chat'?'有什么想聊的？':'有什么工作需要完成？'}</strong><p>{snapshot?.sessionType==='enterprise-research'?'上传资料，提出你关心的问题；可以边分析边明确需要的报告、图表或其他成果。':snapshot?.sessionType==='general-chat'?'直接提问、讨论想法，或接着追问。':'描述目标、已有资料与期望交付。'}</p></div>}
      onSend={(_, text,submission) => send(text,submission)} onCancel={cancel} canRerunCompleted={false}
      hasOlderHistory={false /* Temporarily disabled while conversation history navigation is repaired. */}
      resultProjections={professional?.resultProjections}
      caseExecution={professional?.applicationState?.caseExecution}
      onReadAttemptRecords={client.supportsAttemptRecords ? (attemptId, after) => client.attemptRecords(currentId, attemptId, after) : undefined} />}
  </ThreadWorkspace>
}
