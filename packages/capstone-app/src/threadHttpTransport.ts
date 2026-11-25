import {checkResourceReadCursor,parseResourceRead,parseResourceReadPage} from './resourceReads'
import {parseRowPage,parseRowSelection} from './resultRowSelection'
import {sha256Hex} from './browserDigest'
import {sha256 as incrementalSha256} from 'js-sha256'
import {parseThinkingPreview,type ThinkingPreview} from './thinkingPreview'
import {applicationCapacity,assertCapacity,exceedsCapacity,CapacityError,type CapacityKey} from './applicationCapacity'
import { parseEventEnvelope, type EventEnvelope } from './threadProtocol'
import { parseGridSourcePage, parseGridSourceScopes, type GridSourceQuery } from './gridSource'
import type { ThreadCommand, ThreadTransport, ThreadTransportState } from './threadClient'
import { parseThreadDescriptor, parseThreadListPage, type ThreadListPage, type ThreadDescriptor } from './threadManagement'
import { fetchWithReadRetry } from './httpRetry'
import { parseAttemptRecords } from './attemptRecords'
import { parseProcessProducts } from './processProducts'
import {parseInstructionTakeover,type WorkCommand} from './threadWorkProtocol'
import {parseNativeArtifact,parseNativeArtifacts,type NativeArtifact} from './nativeArtifacts'
import {recordAnswerArrival} from './answerRenderTiming'
import {compareRowIds,parseProductIndex,parseProductRef,parseProductResolution,parseContextProductRefs,type ProductQuery,type ProductRef} from './threadProducts'
import {object,parseSeries,parseComparison,type SeriesCommand} from './productSeries'
import {parseBlockJob,parseBlockPage} from './productBlocks'
import {transferResource,parseStoredResources} from './resourceUploads'
import {parseCapacityFailure} from './capacityFailure'
import {parseGatewayConnectionStatus} from './threadInput'
import type {WorkspaceConnections} from './workspaceConnections'
import type {GatewayConnectionInput} from './gatewayConnectionTypes'
import {parseGatewayConnections,parseGatewayProbe} from './gatewayConnectionProtocol'
import {currentWorkspaceName,normalizeWorkspaceName} from './workspaceName'
import {parseControlGoal,parseControlGoals,type ControlCommand,type ControlGoalCreate} from './controlGoals'
import {parseMission,type MissionCreate} from './missions'
import {parseControlEvents} from './controlEvents'

const THREAD_VERSION_HEADER = 'Capstone-Thread-Version'
const THREAD_VERSION = '1'
const VERSION_ERRORS = new Set(['unsupported_thread_version', 'protocol_upgrade_required', 'thread_version_mismatch'])
// Opaque scopes let retained session transports share workspace metadata without
// placing connection credentials or session IDs in public UI storage.
const workspaceScopes:{origin:string;token:string;scope:object}[]=[]
function workspaceScope(origin:string,token:string){
  const existing=workspaceScopes.find(entry=>entry.origin===origin&&entry.token===token)
  if(existing)return existing.scope
  const scope={}
  workspaceScopes.push({origin,token,scope})
  if(workspaceScopes.length>16)workspaceScopes.shift()
  return scope
}

function versionError(body: unknown): boolean {
  return !!body && typeof body === 'object' && 'error' in body
    && typeof body.error === 'string' && VERSION_ERRORS.has(body.error)
}

export class ThreadTransportError extends Error {
  constructor(public readonly status: number, message: string, public readonly body?: unknown) {
    super(message)
    this.name = 'ThreadTransportError'
  }
}

export function isThreadVersionError(error: unknown): error is ThreadTransportError {
  return error instanceof ThreadTransportError && versionError(error.body)
}

function responseError(status: number, body?: unknown): ThreadTransportError|CapacityError {
  const capacity=parseCapacityFailure(body&&typeof body==='object'&&'detail' in body?body.detail:undefined)
  if(capacity)return new CapacityError('服务端容量限制已触发。',capacity.dimension as CapacityKey,capacity.limit,capacity.actual,capacity.location||capacity.phase||'transport.response',{mode:capacity.mode||'normal',source:capacity.source||'application_capacity'})
  return new ThreadTransportError(status, versionError(body)
    ? '应用与会话协议版本不兼容，请更新应用后重新打开会话。'
    : `Thread 服务请求失败（${status}）。`, body)
}

async function checkResponseVersion(response: Response, requestedVersion = THREAD_VERSION): Promise<void> {
  const version = response.headers.get(THREAD_VERSION_HEADER)
  // Older v1 servers do not echo a version. Their strict body parsers still apply.
  if (response.ok && ((version !== null && version !== requestedVersion) || (requestedVersion === '2' && version === null))) {
    await response.body?.cancel().catch(() => undefined)
    throw responseError(409, { error: 'thread_version_mismatch' })
  }
}

async function boundedResponseText(response:Response,key:CapacityKey,maximumBytes=applicationCapacity(key)):Promise<string>{
  if(!response.body)return ''
  const reader=response.body.getReader(),decoder=new TextDecoder()
  let text='',total=0
  try{
    while(true){const {value,done}=await reader.read();if(done)break
      total+=value.byteLength
      if(total>maximumBytes){await reader.cancel();throw new CapacityError(`超过应用容量 ${key}：当前 ${total}，上限 ${maximumBytes} 字节。`,key,maximumBytes,total)}
      text+=decoder.decode(value,{stream:true})
    }
    return text+decoder.decode()
  }finally{reader.releaseLock()}
}

async function verifiedFileBytes(response:Response,size:number,digest:string,key:CapacityKey='artifact_file_bytes'):Promise<Uint8Array> {
  if(!response.ok)throw new Error('文件暂时无法读取')
  if(!Number.isSafeInteger(size)||size<0||exceedsCapacity(size,key)||!/^[a-f0-9]{64}$/.test(digest))throw new Error('文件信息无效')
  const reader=response.body?.getReader()
  if(!reader)throw new Error('文件内容缺失')
  const chunks:Uint8Array[]=[];let total=0
  try {
    while(true){const {value,done}=await reader.read();if(done)break;total+=value.byteLength
      if(total>size){await reader.cancel();throw new Error('文件大小不符')}
      chunks.push(value)
    }
  }finally{reader.releaseLock()}
  if(total!==size)throw new Error('文件不完整')
  const bytes=new Uint8Array(total);let offset=0
  for(const chunk of chunks){bytes.set(chunk,offset);offset+=chunk.length}
  const actual=await sha256Hex(bytes)
  if(actual!==digest)throw new Error('文件校验失败')
  return bytes
}

async function writeVerifiedStream(response:Response,size:number,digest:string,write:(chunk:Uint8Array)=>Promise<void>){
  if(!Number.isSafeInteger(size)||size<1||!/^[a-f0-9]{64}$/.test(digest))throw new Error('文件信息无效')
  const reader=response.body?.getReader()
  if(!reader)throw new Error('文件内容缺失')
  const hasher=incrementalSha256.create()
  let total=0
  try{
    while(true){
      const {value,done}=await reader.read()
      if(done)break
      total+=value.byteLength
      if(total>size){await reader.cancel();throw new Error('文件大小不符')}
      hasher.update(value)
      await write(value)
    }
  }finally{reader.releaseLock()}
  if(total!==size)throw new Error('文件不完整')
  if(hasher.hex()!==digest)throw new Error('文件校验失败')
}

/** HTTP adapter for the negotiated Thread API; payload parsing remains in the client. */
export class HttpThreadTransport implements ThreadTransport {
  async createMission(body:MissionCreate){return parseMission(await this.request('/api/v1/control/missions',{method:'POST',headers:{'Idempotency-Key':body.operation_id},body:JSON.stringify(body),signal:AbortSignal.timeout(applicationCapacity('ui_network_status_timeout_ms'))}),this.workspaceName,body.origin.thread_id)}
  async mission(missionId:string,threadId:string){const mission=parseMission(await this.request('/api/v1/control/missions/'+encodeURIComponent(missionId),{signal:AbortSignal.timeout(applicationCapacity('ui_network_status_timeout_ms'))}),this.workspaceName,threadId);if(mission.missionId!==missionId)throw new Error('Mission 身份不匹配。');return mission}
  async resumeMission(missionId:string,threadId:string,revision:number,operationId:string) {
    const receipt=await this.request('/api/v1/control/missions/'+encodeURIComponent(missionId)+'/commands',{
      method:'POST',headers:{'Idempotency-Key':operationId},
      body:JSON.stringify({schema:'capstone-control-mission-command/1',operation_id:operationId,
        mission_id:missionId,expected_revision:revision,kind:'resume',payload:{}}),
      signal:AbortSignal.timeout(applicationCapacity('ui_network_status_timeout_ms')),
    }) as {schema?:unknown;operation_id?:unknown;mission?:unknown}
    if(receipt?.schema!=='capstone-control-mission-receipt/1'||receipt.operation_id!==operationId)
      throw new Error('Mission 恢复回执无效。')
    const mission=parseMission(receipt.mission,this.workspaceName,threadId)
    if(mission.missionId!==missionId)throw new Error('Mission 身份不匹配。')
    return mission
  }
  private controlDocument(value:unknown){const goal=parseControlGoal(value);if(goal.workspace!==this.workspaceName)throw new Error('长期目标不属于当前工作空间。');return goal}
  private controlRequest(path:string,init:RequestInit={}){return this.request('/api/v1/control/goals'+path,{...init,signal:AbortSignal.timeout(applicationCapacity('ui_network_status_timeout_ms'))})}
  async controlGoals(after?:string){
    const query=new URLSearchParams({include_missions:'true'})
    if(after)query.set('after',after)
    const page=parseControlGoals(await this.controlRequest('?'+query))
    if(page.goals.some(g=>g.workspace!==this.workspaceName))throw new Error('目标列表不属于当前工作空间。')
    return page
  }
  async controlGoal(id:string){const goal=this.controlDocument(await this.controlRequest('/'+encodeURIComponent(id)+'?include_missions=true'));if(goal.goal_id!==id)throw new Error('目标身份不匹配。');return goal}
  async controlEvents(id:string,after=0,through?:number){
    if(!Number.isSafeInteger(after)||after<0||(through!==undefined&&(!Number.isSafeInteger(through)||through<after)))throw new Error('控制事件读取边界无效')
    const query=new URLSearchParams({after:String(after),limit:'50'})
    if(through!==undefined)query.set('through',String(through))
    return parseControlEvents(await this.controlRequest('/'+encodeURIComponent(id)+'/events?'+query),this.workspaceName,id,after,through)
  }
  async createControlGoal(body:ControlGoalCreate){return this.controlDocument(await this.controlRequest('',{method:'POST',body:JSON.stringify(body)}))}
  async controlGoalCommand(body:ControlCommand){
    const result=await this.controlRequest('/'+encodeURIComponent(body.goal_id)+'/commands',{method:'POST',body:JSON.stringify(body)})
    if(!result||typeof result!=='object'||!('schema' in result)||result.schema!=='capstone-control-receipt/1'||!('goal' in result)||!('operation_id' in result)||result.operation_id!==body.operation_id)throw new Error('目标控制回执无效')
    const goal=this.controlDocument(result.goal)
    if(goal.goal_id!==body.goal_id)throw new Error('目标控制回执身份不匹配。')
    return {goal}
  }
  readonly workspaceName:string
  private get workspaceHeaders():Record<string,string>{return this.workspaceName==='enterprise'?{}:{'Capstone-Workspace':encodeURIComponent(this.workspaceName)}}
  readonly workspaceConnectionsScope:object
  readonly connectionState: ThreadTransportState = 'live'
  private readonly base: string
  private readonly resourcePath: string
  private gridThreadId?:string
  forThread(threadId:string){
    const scoped=new HttpThreadTransport(this.base,this.token,this.fetcher,this.resourcePath,this.protocolVersion,this.workspaceName)
    scoped.gridThreadId=threadId
    return scoped
  }
  private get gridSourcePath(){return this.gridThreadId?`${this.resourcePath}/${encodeURIComponent(this.gridThreadId)}/grid-sources`:'/api/v1/grid-sources'}
  // Missing request headers mean v1. Wait for a visible server advertisement
  // before adding a custom header that older cross-origin servers cannot allow.
  // Never retry a write to discover protocol support.
  private versionAdvertised = false
  private async checkWorkspace(response:Response){
    if(this.workspaceName==='enterprise'||!response.ok)return
    let matches=false
    try{const echoed=response.headers.get('Capstone-Workspace');matches=echoed!==null&&normalizeWorkspaceName(decodeURIComponent(echoed))===this.workspaceName}catch{/* Reject an absent or malformed response scope. */}
    if(!matches){await response.body?.cancel().catch(()=>undefined);throw new ThreadTransportError(409,'服务端尚未确认当前工作空间，请更新后端后重试。')}
  }

  async listResourceReads(threadId:string,attemptId:string,cursor?:string,signal?:AbortSignal){
    if(cursor!==undefined)checkResourceReadCursor(cursor,threadId,attemptId)
    const query=new URLSearchParams({attempt_id:attemptId,limit:'20'})
    if(cursor)query.set('cursor',cursor)
    return parseResourceReadPage(await this.request(`${this.resourcePath}/${encodeURIComponent(threadId)}/resource-reads?${query}`,{signal}),threadId,attemptId)
  }
  async readResourceRead(threadId:string,readId:string,attemptId:string,signal?:AbortSignal){
    const item=parseResourceRead(await this.request(`${this.resourcePath}/${encodeURIComponent(threadId)}/resource-reads/${encodeURIComponent(readId)}`,{signal}),threadId,attemptId)
    if(item.read_id!==readId)throw new Error('资源读取回执身份不一致')
    return item
  }
  async workspaceConnections():Promise<WorkspaceConnections> {
    const value=await this.request('/api/v1/workspace/connections') as WorkspaceConnections
    if(!value||value.schema!=='capstone-workspace-connections/1')throw new Error('工作台连接信息无效')
    return {schema:value.schema,...(value.data_gateway===undefined?{}:{data_gateway:parseGatewayConnectionStatus(value.data_gateway)})}
  }

  private async gatewayRequest(action?:string,body?:unknown){
    const signal=AbortSignal.timeout(applicationCapacity('ui_network_status_timeout_ms')*(action?2:1))
    return this.gatewayOperation('/api/v1/workspace/gateways'+(action?'/'+action:''),action?{method:'POST',body:JSON.stringify(body??{}),signal}:{signal})
  }
  private async gatewayOperation(path:string,init:RequestInit={}){
    try{return await this.request(path,init)}
    catch(error){
      if(error instanceof ThreadTransportError&&error.body&&typeof error.body==='object'&&'detail' in error.body){
        const detail=error.body.detail
        if(detail&&typeof detail==='object'&&'message' in detail&&typeof detail.message==='string'&&detail.message.length<=256)throw new Error(detail.message)
      }
      throw error
    }
  }
  async gatewayConnections(){return parseGatewayConnections(await this.gatewayRequest())}
  async refreshGatewayConnections(){return parseGatewayConnections(await this.gatewayRequest('refresh'))}
  async refreshGatewayContract(){return parseGatewayConnections(await this.gatewayRequest('reload'))}
  async selectGatewayConnection(id:string){return parseGatewayConnections(await this.gatewayRequest('select',{id}))}
  async threadGatewayConnections(threadId:string){return parseGatewayConnections(await this.gatewayOperation(`${this.resourcePath}/${encodeURIComponent(threadId)}/gateways`))}
  async selectThreadGatewayConnection(threadId:string,id:string){return parseGatewayConnections(await this.gatewayOperation(`${this.resourcePath}/${encodeURIComponent(threadId)}/gateways/select`,{method:'POST',body:JSON.stringify({id})}))}
  async refreshThreadGatewayConnections(threadId:string){return parseGatewayConnections(await this.gatewayOperation(`${this.resourcePath}/${encodeURIComponent(threadId)}/gateways/refresh`,{method:'POST',body:'{}'}))}
  async refreshThreadGatewayContract(threadId:string){return parseGatewayConnections(await this.gatewayOperation(`${this.resourcePath}/${encodeURIComponent(threadId)}/gateways/reload`,{method:'POST',body:'{}'}))}
  async probeGatewayConnection(input:GatewayConnectionInput){return parseGatewayProbe(await this.gatewayRequest('probe',input))}
  async addGatewayConnection(input:GatewayConnectionInput){return parseGatewayConnections(await this.gatewayRequest('add',input))}

  constructor(
    baseUrl: string,
    private readonly token: string,
    private readonly fetcher: typeof fetch = fetch,
    resourcePath = '/api/v1/threads',
    private readonly protocolVersion: '1' | '2' = '1',
    workspaceName = currentWorkspaceName(),
  ) {
    // Browser fetch requires its Window receiver, including direct file reads.
    this.fetcher = fetcher.bind(globalThis)
    this.base = baseUrl.trim().replace(/\/$/, '')
    if (this.base && !/^https?:\/\/[^/]+$/.test(this.base)) throw new Error('API 地址无效')
    if (!/^\/[^?]+$/.test(resourcePath)) throw new Error('Thread 资源路径无效')
    this.resourcePath = resourcePath.replace(/\/$/, '')
    this.workspaceName=normalizeWorkspaceName(workspaceName)
    this.workspaceConnectionsScope=workspaceScope(this.base,this.token)
  }

  private async managedResourceRequest(path:string,init:RequestInit={}){
    try{return await this.request(path,init)}catch(error){
      if(error instanceof ThreadTransportError&&error.body&&typeof error.body==='object'&&'detail' in error.body){
        const detail=error.body.detail
        if(detail&&typeof detail==='object'&&'code' in detail&&typeof detail.code==='string'&&/^[a-z][a-z0-9_]{0,95}$/.test(detail.code)){
          const effect='executed' in detail?(detail.executed===false?'；未执行':detail.executed===null?'；执行结果未知，请勿直接重试':''):''
          throw new Error(`资源操作失败：${detail.code}${effect}`)
        }
      }
      throw error
    }
  }
  async debugStatus(threadId:string){
    const value=await this.request(`${this.resourcePath}/${encodeURIComponent(threadId)}/debug/status`) as Record<string,unknown>
    if(value?.thread_id!==threadId||value.enabled!==true)throw new Error('调试入口不可用。')
    const investigation=value.investigation as {investigation_id?:unknown;objective?:unknown;observation?:{
      attempt_id:string;through:number;first_failure:{seq:number;type:string}|null}}|null
    const observation=investigation?.observation
    const finding=observation?(observation.first_failure?
      `执行轮次 ${observation.attempt_id} 的首条公开异常为 #${observation.first_failure.seq}（${observation.first_failure.type}）。`:
      `执行轮次 ${observation.attempt_id} 截至事件 #${observation.through} 未记录公开失败事件。`):''
    return {timelineExport:value.timeline_export===true,
      investigationId:typeof investigation?.investigation_id==='string'?investigation.investigation_id:null,
      objective:typeof investigation?.objective==='string'?investigation.objective:null,finding}
  }
  async debugSourceVersion(threadId:string){
    const result=await this.request(`${this.resourcePath}/${encodeURIComponent(threadId)}/debug/sources`) as Record<string,unknown>
    if(result.status==='matched'&&typeof result.gateway_revision==='string')return '当前网关源码 '+result.gateway_revision
    if(result.status==='source_missing')return '当前网关的源码尚未入库。摘要 '+result.gateway_revision+'。导入对应发布包后可重新核对。'
    if(result.status==='unreported')return '当前网关尚未声明源码摘要。'
    return '当前网关连接不可用。'
  }
  async startDebugInvestigation(threadId:string,objective:string,key:string,attemptId?:string){
    const path=`${this.resourcePath}/${encodeURIComponent(threadId)}/debug/investigations`
    return this.request(path,{method:'POST',headers:{'Idempotency-Key':key},body:JSON.stringify({objective,attempt_id:attemptId})})
  }
  async debugTimeline(threadId:string,attemptId:string,after:number,through?:number){
    const path=`${this.resourcePath}/${encodeURIComponent(threadId)}/debug/attempts/${encodeURIComponent(attemptId)}/timeline?after=${after}`+(through===undefined?'':`&through=${through}`)
    const page=await this.request(path) as Record<string,unknown>
    if(page?.thread_id!==threadId||page.attempt_id!==attemptId||!Array.isArray(page.events)||
        typeof page.next_after!=='number'||!Number.isSafeInteger(page.next_after)||page.next_after<after||
        typeof page.has_more!=='boolean'||(page.has_more&&page.next_after===after))throw new Error('调试记录分页无效。')
    const events=page.events.map(event=>{
      if(!Number.isSafeInteger(event?.seq)||typeof event?.type!=='string'||typeof event?.occurred_at!=='string')throw new Error('调试事件格式无效。')
      return {seq:event.seq as number,type:event.type as string,occurred_at:event.occurred_at as string}
    })
    if(typeof page.through!=='number'||!Number.isSafeInteger(page.through)||page.through<page.next_after||
        (through!==undefined&&through!==page.through))throw new Error('调试记录快照无效。')
    return {events,nextAfter:page.next_after,hasMore:page.has_more,through:page.through}
  }
  async listManagedResources(){return this.managedResourceRequest('/api/v1/managed-resources')}
  async readManagedResourceOperation(requestId:string){return this.managedResourceRequest(`/api/v1/managed-resources/operations/${encodeURIComponent(requestId)}`)}
  async manageResource(operation:string,document:Record<string,unknown>){return this.managedResourceRequest(`/api/v1/managed-resources/operations/${encodeURIComponent(operation)}`,{method:'POST',body:JSON.stringify(document)})}

  private async request(path: string, init: RequestInit = {}, maximumBytes=applicationCapacity('event_page_bytes'),capacityKey:CapacityKey='event_page_bytes',threadVersion=true): Promise<unknown> {
    if(typeof init.body==='string')assertCapacity(new TextEncoder().encode(init.body).byteLength,'command_bytes')
    const response = await fetchWithReadRetry(this.base + path, {
      ...init,
      credentials: 'omit', cache: 'no-store',
      headers: {
        ...this.workspaceHeaders,
        ...(this.token ? { Authorization: `Bearer ${this.token}` } : {}),
        ...(init.body ? { 'Content-Type': 'application/json' } : {}),
        ...init.headers,
        ...(threadVersion && (this.versionAdvertised || this.protocolVersion === '2') ? { [THREAD_VERSION_HEADER]: this.protocolVersion } : {}),
      },
    }, this.fetcher)
    if(path===this.resourcePath||path.startsWith(this.resourcePath+'/')||path.startsWith('/api/v1/control/'))await this.checkWorkspace(response)
    if(threadVersion)await checkResponseVersion(response, this.protocolVersion)
    if(response.status===204)return undefined
    if(threadVersion)this.versionAdvertised = response.ok && response.headers.get(THREAD_VERSION_HEADER) === this.protocolVersion
    const text = await boundedResponseText(response,capacityKey,maximumBytes)
    let body: unknown = undefined
    try {
      body = JSON.parse(text) as unknown
    } catch {
      if (!response.ok) throw new ThreadTransportError(response.status, `Thread 服务请求失败（${response.status}）。`)
      throw new ThreadTransportError(response.status, 'Thread 响应不是有效 JSON。')
    }
    if (!response.ok) throw responseError(response.status, body)
    return body
  }

  private async streamRequest(path: string, signal?: AbortSignal): Promise<Response> {
    const response = await fetchWithReadRetry(this.base + path, {
      signal, credentials: 'omit', cache: 'no-store',
      headers: { ...this.workspaceHeaders, ...(this.token ? { Authorization: `Bearer ${this.token}` } : {}),
        ...(this.versionAdvertised || this.protocolVersion === '2' ? { [THREAD_VERSION_HEADER]: this.protocolVersion } : {}) },
    }, this.fetcher)
    await this.checkWorkspace(response)
    await checkResponseVersion(response, this.protocolVersion)
    this.versionAdvertised = response.ok && response.headers.get(THREAD_VERSION_HEADER) === this.protocolVersion
    if (!response.ok) {
      const text = await response.text()
      let body: unknown
      try { body = JSON.parse(text) as unknown } catch { body = undefined }
      throw responseError(response.status, body)
    }
    return response
  }

  getSnapshot(threadId: string, signal?: AbortSignal): Promise<unknown> {
    return this.request(`${this.resourcePath}/${encodeURIComponent(threadId)}`, { signal })
  }

  async getInstructionTakeover(threadId:string,signal?:AbortSignal) {
    return parseInstructionTakeover(await this.request(
      `${this.resourcePath}/${encodeURIComponent(threadId)}/instruction-takeover`, {signal},
    ))
  }

  getInputCatalog(threadId: string, signal?: AbortSignal): Promise<unknown> {
    return this.request(`${this.resourcePath}/${encodeURIComponent(threadId)}/input-catalog`, { signal })
  }

  readHistory(threadId: string, beforeEventSeq?: number, signal?: AbortSignal): Promise<unknown> {
    const query = new URLSearchParams({ limit: String(applicationCapacity('history_page_items')) })
    if (beforeEventSeq !== undefined) query.set('before', String(beforeEventSeq))
    return this.request(`${this.resourcePath}/${encodeURIComponent(threadId)}/history?${query}`, { signal })
  }

  async readProcessProducts(threadId: string, before?: number, signal?: AbortSignal) {
    const query = new URLSearchParams({limit:String(applicationCapacity('history_page_items')), ...(before === undefined ? {} : {before:String(before)})})
    return parseProcessProducts(await this.request(`${this.resourcePath}/${encodeURIComponent(threadId)}/products?${query}`, {signal}), threadId, before)
  }

  readTaskDiagram(threadId: string, attemptId: string, signal?: AbortSignal) {
    return this.request(`${this.resourcePath}/${encodeURIComponent(threadId)}/attempts/${encodeURIComponent(attemptId)}/task-diagram?focused=true`,
      {signal}, applicationCapacity('control_document_bytes'), 'control_document_bytes')
  }

  readModelContextSnapshot(threadId:string,attemptId:string,ref:string,index?:number,signal?:AbortSignal):Promise<unknown> {
    const query=index===undefined?'':`?index=${index}`
    return this.request(`${this.resourcePath}/${encodeURIComponent(threadId)}/attempts/${encodeURIComponent(attemptId)}/context-snapshots/${encodeURIComponent(ref)}${query}`,{signal})
  }

  async readAttemptRecords(threadId: string, attemptId: string, after = 0, signal?: AbortSignal) {
    if (!Number.isSafeInteger(after) || after < 0) throw new Error('任务记录游标无效')
    const query = new URLSearchParams({ after: String(after), limit: String(applicationCapacity('native_record_count')) })
    const body = await this.request(`${this.resourcePath}/${encodeURIComponent(threadId)}/attempts/${encodeURIComponent(attemptId)}/records?${query}`, { signal })
    return parseAttemptRecords(body, threadId, attemptId, after)
  }

  readNetworkEvents(threadId: string, signal?: AbortSignal, contextId?: string, attemptId?: string): Promise<unknown> {
    const query = new URLSearchParams()
    if (contextId) query.set('context_id', contextId)
    if (attemptId) query.set('attempt_id', attemptId)
    return this.request(`${this.resourcePath}/${encodeURIComponent(threadId)}/network-events${query.size ? `?${query}` : ''}`, { signal })
  }

  async getModels(threadId: string, signal?: AbortSignal): Promise<unknown> {
    try { return await this.request(`${this.resourcePath}/${encodeURIComponent(threadId)}/models`, { signal }) }
    catch (cause) { if (cause instanceof ThreadTransportError && cause.status === 404) return null; throw cause }
  }

  async listThreads(archived = false, before?: string, signal?: AbortSignal): Promise<ThreadListPage> {
    const query = new URLSearchParams({ archived: String(archived), limit: String(applicationCapacity('ui_session_page_items')) })
    if (before) query.set('before', before)
    try { return parseThreadListPage(await this.request(`${this.resourcePath}?${query}`, { signal })) }
    catch (cause) {
      if (this.protocolVersion !== '1' || !isThreadVersionError(cause)) throw cause
      // A mixed list needs v2, but the selected v1 conversation must keep its own protocol.
      return new HttpThreadTransport(this.base, this.token, this.fetcher, this.resourcePath, '2',this.workspaceName)
        .listThreads(archived, before, signal)
    }
  }

  async archiveThread(threadId: string, archived: boolean, signal?: AbortSignal):Promise<ThreadDescriptor> {
    try{return parseThreadDescriptor(await this.request(`${this.resourcePath}/${encodeURIComponent(threadId)}/archive`, {
      method: 'POST', signal, body: JSON.stringify({ archived }),
    }))}catch(error){if(this.protocolVersion==='2'||!isThreadVersionError(error))throw error;return new HttpThreadTransport(this.base,this.token,this.fetcher,this.resourcePath,'2',this.workspaceName).archiveThread(threadId,archived,signal)}
  }

  async readSessionPins(){return this.request('/api/v1/workspace/session-pins')}
  async writeSessionPins(operation:{thread_id:string;pinned:boolean}|{import:string[]}){return this.request('/api/v1/workspace/session-pins',{method:'PUT',body:JSON.stringify(operation)})}
  async cleanupThread(threadId:string){await this.request(`/api/v1/workspace/session-pins/cleanup/${encodeURIComponent(threadId)}`,{method:'DELETE'})}

  async deleteThread(threadId:string,signal?:AbortSignal):Promise<void> {
    try{await this.request(`${this.resourcePath}/${encodeURIComponent(threadId)}`,{method:'DELETE',signal})}
    catch(error){if(this.protocolVersion==='2'||!isThreadVersionError(error))throw error;await new HttpThreadTransport(this.base,this.token,this.fetcher,this.resourcePath,'2',this.workspaceName).deleteThread(threadId,signal)}
  }

  async getSessionManagementSnapshot(threadId:string):Promise<{run:{run_id:string};session_title?:{revision:number}}> {
    let value:unknown
    try{value=await this.getSnapshot(threadId)}catch(error){
      if(!isThreadVersionError(error))throw error
      value=await new HttpThreadTransport(this.base,this.token,this.fetcher,this.resourcePath,'2',this.workspaceName).getSnapshot(threadId)
    }
    const row=value as {run?:{run_id?:unknown};session_title?:{revision:number}}
    if(typeof row?.run?.run_id!=='string')throw new Error('会话信息暂不可用')
    return {run:{run_id:row.run.run_id},session_title:row.session_title}
  }

  async getThreadMetadata(threadId: string, signal?: AbortSignal): Promise<{ archived: boolean }> {
    const body = await this.request(`${this.resourcePath}/${encodeURIComponent(threadId)}/metadata`, { signal })
    if (!body || typeof body !== 'object' || !('archived' in body) || typeof body.archived !== 'boolean') throw new Error('会话状态无效')
    return { archived: body.archived }
  }

  getCatalog(threadId: string, signal?: AbortSignal): Promise<unknown> {
    return this.request(`${this.resourcePath}/${encodeURIComponent(threadId)}/catalog`, { signal })
  }

  createThread(modelId?: string, signal?: AbortSignal): Promise<unknown> {
    return this.request(this.resourcePath, {
      method: 'POST', signal, body: JSON.stringify(modelId ? { model_id: modelId } : {}),
    })
  }

  getSessionCatalog(signal?: AbortSignal): Promise<unknown> {
    return this.request('/api/v1/thread-catalog', {signal})
  }

  async readProductIndex(threadId:string,query:ProductQuery={},signal?:AbortSignal) {
    const params=new URLSearchParams({limit:String(applicationCapacity('product_page_items'))})
    if(query.cursor)params.set('cursor',query.cursor)
    if(query.workId!==undefined)params.set('work_id',query.workId===null?'legacy':query.workId)
    return parseProductIndex(await this.request(`${this.resourcePath}/${encodeURIComponent(threadId)}/product-index?${params}`,{signal}),threadId)
  }
  async discoverProductSeries(ref:ProductRef,signal?:AbortSignal){
    ref=parseProductRef(ref)
    const body=object(await this.request(`${this.resourcePath}/${encodeURIComponent(ref.thread_id)}/product-series/discover`,{method:'POST',body:JSON.stringify({product:ref}),signal}),['series'])
    return body.series===null?null:parseSeries(body.series,ref.thread_id)
  }
  async commandProductSeries(thread:string,command:SeriesCommand){
    const state=parseSeries(await this.request(`${this.resourcePath}/${encodeURIComponent(thread)}/product-series/commands`,{method:'POST',body:JSON.stringify(command),headers:{'Idempotency-Key':command.idempotency_key}}),thread)
    if(state.series_id!==command.series_id)throw new Error('系列身份不匹配。')
    return state
  }
  async productSources(ref:ProductRef,signal?:AbortSignal){
    ref=parseProductRef(ref)
    const body=object(await this.request(`${this.resourcePath}/${encodeURIComponent(ref.thread_id)}/product-series/sources`,{method:'POST',body:JSON.stringify({product:ref}),signal}),['sources'])
    return parseContextProductRefs(body.sources,ref.thread_id)
  }
  async compareProducts(original:ProductRef,revised:ProductRef,signal?:AbortSignal){
    original=parseProductRef(original);revised=parseProductRef(revised,original.thread_id)
    return parseComparison(await this.request(`${this.resourcePath}/${encodeURIComponent(original.thread_id)}/product-comparisons`,{method:'POST',body:JSON.stringify({original_ref:original,revised_ref:revised}),signal}),original,revised)
  }
  async seriesMembers(thread:string,series:string,after?:string,signal?:AbortSignal){
    const query=new URLSearchParams({limit:String(Math.min(20,applicationCapacity('product_page_items')))})
    if(after)query.set('after',after)
    const body=object(await this.request(`${this.resourcePath}/${encodeURIComponent(thread)}/product-series/${encodeURIComponent(series)}/members?${query}`,{signal}),['members','next_cursor'])
    if(!Array.isArray(body.members)||body.members.length>20||body.next_cursor!==null&&typeof body.next_cursor!=='string'||body.next_cursor===after)throw new Error('系列分页响应无效。')
    return {members:body.members.map(ref=>parseProductRef(ref,thread)),next_cursor:body.next_cursor as string|null}
  }
  async readResultRows(ref:ProductRef,table:string,offset=0,signal?:AbortSignal,limit=32){
    ref=parseProductRef(ref)
    return parseRowPage(await this.request(`${this.resourcePath}/${encodeURIComponent(ref.thread_id)}/product-index/table-page`,{method:'POST',body:JSON.stringify({ref,table_id:table,offset,limit}),signal}),ref,table,offset,limit)
  }
  async prepareResultRows(ref:ProductRef,table:string,rows:string[],columns:string[],signal?:AbortSignal){
    ref=parseProductRef(ref)
    const selection=parseRowSelection(await this.request(`${this.resourcePath}/${encodeURIComponent(ref.thread_id)}/product-index/row-selection`,{method:'POST',body:JSON.stringify({ref,table_id:table,row_ids:rows,column_ids:columns}),signal}),ref)
    if(selection.table_id!==table||JSON.stringify(selection.row_ids)!==JSON.stringify([...rows].sort(compareRowIds))||selection.column_ids.length!==columns.length||selection.column_ids.some(id=>!columns.includes(id)))throw new Error('表格选择响应不符')
    return selection
  }
  async readProductBlocks(ref:ProductRef,jobId?:string,offset=0,signal?:AbortSignal) {
    ref=parseProductRef(ref)
    if(!Number.isSafeInteger(offset)||offset<0)throw new Error('段落分页无效')
    const path=`${this.resourcePath}/${encodeURIComponent(ref.thread_id)}/product-block-indexes`
    const job=parseBlockJob(await this.request(jobId?`${path}/${encodeURIComponent(jobId)}`:path,
      jobId?{signal}:{method:'POST',body:JSON.stringify({ref}),signal}),ref,jobId)
    if(job.state!=='ready')return {job}
    const limit=Math.min(20,applicationCapacity('product_page_items'))
    const page=parseBlockPage(await this.request(`${path}/${encodeURIComponent(job.job_id)}/blocks?offset=${offset}&limit=${limit}`,{signal}),ref,job.job_id,offset)
    return {job,page}
  }
  async resolveProduct(reference:ProductRef,signal?:AbortSignal) {
    const ref=parseProductRef(reference)
    const body=await this.request(`${this.resourcePath}/${encodeURIComponent(ref.thread_id)}/product-index/resolve`,{method:'POST',body:JSON.stringify({ref}),signal},applicationCapacity('ui_product_resolution_bytes'),'ui_product_resolution_bytes')
    return parseProductResolution(body,ref)
  }

  async uploadThreadMaterial(threadId:string,file:File,signal?:AbortSignal):Promise<unknown> {
    const page=await this.request(`${this.resourcePath}/${encodeURIComponent(threadId)}/materials`,{signal}) as {limits?:{max_file_bytes?:number;supported_extensions?:string[]}}
    const limit=page.limits?.max_file_bytes,extensions=page.limits?.supported_extensions
    if(!Number.isSafeInteger(limit)||!limit||limit<1||!Array.isArray(extensions))throw new Error('暂时无法读取资料上传范围，请重试')
    const extension=file.name.slice(file.name.lastIndexOf('.')).toLowerCase()
    if(!extensions.includes(extension))throw new Error(`支持的资料格式：${extensions.join('、')}`)
    if(file.size>limit)throw new Error(`单份资料不能超过 ${Math.ceil(limit/1024)} KiB`)
    return this.request(`${this.resourcePath}/${encodeURIComponent(threadId)}/materials?filename=${encodeURIComponent(file.name)}`,{method:'POST',body:file,signal,headers:{'Content-Type':'application/octet-stream'}})
  }
  uploadThreadResource(threadId:string,file:File,options:Parameters<typeof transferResource>[3]) {
    return transferResource((path,init)=>this.request(path,init),`${this.resourcePath}/${encodeURIComponent(threadId)}/resource-uploads`,file,options)
  }
  async readStoredResources(threadId:string,signal?:AbortSignal,draft=false) {
    const resources:ReturnType<typeof parseStoredResources>=[]
    const cursors=new Set<string>(),identities=new Set<string>()
    let cursor:string|undefined,revision:number|undefined,bytes=0
    do{
      signal?.throwIfAborted()
      const params=new URLSearchParams({limit:'100',...(draft?{draft:'true'}:{}),...(cursor?{cursor}:{})})
      const raw=await this.request(`${this.resourcePath}/${encodeURIComponent(threadId)}/resources?${params}`,{signal})
      const page=parseStoredResources(raw,threadId)
      const metadata=raw as {revision?:number;next_cursor?:unknown}
      if(metadata.revision!==undefined){
        if(!Number.isSafeInteger(metadata.revision)||metadata.revision<0||(revision!==undefined&&metadata.revision!==revision))throw new Error('资源目录已变化，请重新读取。')
        revision=metadata.revision
      }else if(cursor)throw new Error('资源分页版本无效。')
      bytes+=new TextEncoder().encode(JSON.stringify(raw)).byteLength
      assertCapacity(bytes,'control_document_bytes','resource.directory')
      for(const item of page){
        if(identities.has(item.resource_id))throw new Error('资源分页返回重复文件。')
        identities.add(item.resource_id);resources.push(item)
      }
      const next=metadata.next_cursor
      if(next===undefined||next===null)return resources // Older hosts return one complete page.
      if(typeof next!=='string'||!next||next.length>1024||cursors.has(next)||!page.length||revision===undefined)throw new Error('资源分页游标无效。')
      cursors.add(next);cursor=next
    }while(cursor)
    return resources
  }
  async readThreadResource(threadId:string,file:{resource_id:string;size_bytes:number;sha256:string;version?:number},signal?:AbortSignal):Promise<Uint8Array> {
    if(!/^resource_[a-f0-9]{32}$/.test(file.resource_id)||!Number.isSafeInteger(file.size_bytes)||file.size_bytes<1||!/^[a-f0-9]{64}$/.test(file.sha256))throw new Error('资源身份无效')
    assertCapacity(file.size_bytes,'artifact_file_bytes','resource.content')
    const response=await this.streamRequest(this.resourceContentPath(threadId,file),signal)
    return verifiedFileBytes(response,file.size_bytes,file.sha256,'artifact_file_bytes')
  }
  async saveThreadResource(threadId:string,file:{resource_id:string;file_name:string;size_bytes:number;sha256:string;version?:number},signal?:AbortSignal):Promise<void> {
    if(!/^resource_[a-f0-9]{32}$/.test(file.resource_id)||!file.file_name||!Number.isSafeInteger(file.size_bytes)||!/^[a-f0-9]{64}$/.test(file.sha256))throw new Error('资源身份无效')
    if(file.size_bytes<=applicationCapacity('artifact_file_bytes'))throw new Error('此文件可在读取后直接保存。')
    const picker=(globalThis as {showSaveFilePicker?:(options?:{suggestedName?:string})=>Promise<{createWritable:()=>Promise<{write:(data:Uint8Array)=>Promise<void>;close:()=>Promise<void>;abort:()=>Promise<void>}>}>}).showSaveFilePicker
    if(!picker)throw new Error(`此文件超过浏览器内可校验读取的容量（${applicationCapacity('artifact_file_bytes')} 字节）。请使用支持直接保存的浏览器下载。`)
    let handle:{createWritable:()=>Promise<{write:(data:Uint8Array)=>Promise<void>;close:()=>Promise<void>;abort:()=>Promise<void>}>}
    try{handle=await picker({suggestedName:file.file_name})}
    catch(cause){if(cause instanceof DOMException&&cause.name==='AbortError')throw new Error('已取消保存。');throw cause}
    const writable=await handle.createWritable()
    try{
      const response=await this.streamRequest(this.resourceContentPath(threadId,file),signal)
      await writeVerifiedStream(response,file.size_bytes,file.sha256,chunk=>writable.write(chunk))
      await writable.close()
    }catch(cause){await writable.abort().catch(()=>undefined);throw cause}
  }
  private resourceContentPath(threadId:string,file:{resource_id:string;version?:number}) {
    const version=file.version??1
    if(!Number.isSafeInteger(version)||version<1)throw new Error('资源版本无效')
    const path=`${this.resourcePath}/${encodeURIComponent(threadId)}/resources/${encodeURIComponent(file.resource_id)}/content`
    return version===1?path:`${path}?version=${version}`
  }
  cancelResourceUpload(threadId:string,uploadId:string,signal?:AbortSignal) {
    return this.request(`${this.resourcePath}/${encodeURIComponent(threadId)}/resource-uploads/${encodeURIComponent(uploadId)}`,{method:'DELETE',signal})
  }
  removeThreadMaterial(threadId:string,materialId:string,signal?:AbortSignal):Promise<unknown> {
    return this.request(`${this.resourcePath}/${encodeURIComponent(threadId)}/materials/${encodeURIComponent(materialId)}`,{method:'DELETE',signal})
  }

  async readNativeArtifacts(threadId:string,attemptId:string,after=0,signal?:AbortSignal) {
    if(!Number.isSafeInteger(after)||after<0)throw new Error('文件目录游标无效')
    return parseNativeArtifacts(await this.request(`${this.resourcePath}/${encodeURIComponent(threadId)}/attempts/${encodeURIComponent(attemptId)}/artifacts?after=${after}`,{signal}),threadId,attemptId,after)
  }
  async readNativeArtifact(artifact:NativeArtifact,signal?:AbortSignal):Promise<Uint8Array> {
    const item=parseNativeArtifact(artifact,artifact.thread_id,artifact.attempt_id)
    const response=await this.fetcher(this.base+item.download_url,{signal,credentials:'omit',cache:'no-store',headers:{...this.workspaceHeaders,...(this.token?{Authorization:`Bearer ${this.token}`} : {}),'Capstone-Thread-Version':this.protocolVersion}})
    await this.checkWorkspace(response)
    return verifiedFileBytes(response,item.size_bytes,item.sha256)
  }

  async readDeliveryFile(threadId:string,artifactId:string,revision:number,size:number,digest:string,signal?:AbortSignal):Promise<Uint8Array> {
    if(!/^delivery_[a-f0-9]{32}$/.test(artifactId)||!Number.isSafeInteger(revision)||revision<1)throw new Error('交付版本无效')
    const response=await this.fetcher(`${this.base}${this.resourcePath}/${encodeURIComponent(threadId)}/deliveries/${artifactId}/revisions/${revision}/content`,{signal,credentials:'omit',cache:'no-store',headers:{...this.workspaceHeaders,...(this.token?{Authorization:`Bearer ${this.token}`} : {}),'Capstone-Thread-Version':this.protocolVersion}})
    await this.checkWorkspace(response)
    return verifiedFileBytes(response,size,digest,'delivery_file_bytes')
  }

  readDeliveries(threadId:string,before?:number,signal?:AbortSignal):Promise<unknown> {
    const query=new URLSearchParams({limit:String(applicationCapacity('product_page_items'))});if(before!==undefined)query.set('before',String(before))
    return this.request(`${this.resourcePath}/${encodeURIComponent(threadId)}/deliveries?${query}`,{signal})
  }
  publishDelivery(threadId:string,request:Record<string,unknown>):Promise<unknown> {
    return this.request(`${this.resourcePath}/${encodeURIComponent(threadId)}/deliveries`,{method:'POST',body:JSON.stringify(request),headers:{'Idempotency-Key':String(request.idempotency_key)}})
  }
  async readDeliveryContent(threadId:string,artifactId:string,revision:number,signal?:AbortSignal):Promise<string> {
    const response=await this.fetcher(`${this.base}${this.resourcePath}/${encodeURIComponent(threadId)}/deliveries/${encodeURIComponent(artifactId)}/revisions/${revision}/content`,{signal,credentials:'omit',cache:'no-store',headers:{...this.workspaceHeaders,...(this.token?{Authorization:`Bearer ${this.token}`} : {}),'Capstone-Thread-Version':this.protocolVersion}})
    if(!response.ok)throw new Error('交付文件暂时无法读取')
    await this.checkWorkspace(response)
    const content=await boundedResponseText(response,'delivery_file_bytes')
    return content
  }

  createSession(selection: {session_type:'grid-analysis'|'enterprise-research'|'general-chat'; model_id?:string}, signal?:AbortSignal):Promise<unknown> {
    return this.request(this.resourcePath, {method:'POST',signal,body:JSON.stringify(selection)})
  }

  gridSourceScopes(signal?:AbortSignal) {
    return this.request(this.gridSourcePath+'/data-gateway/scopes',{signal},4*1024*1024,'event_page_bytes',false)
      .then(parseGridSourceScopes).catch(cause=>{
        if(cause instanceof ThreadTransportError)throw new Error('电网范围目录暂时无法读取。')
        throw cause
      })
  }

  electricalModels(signal?:AbortSignal):Promise<unknown> {
    return this.request(this.gridSourcePath+'/data-gateway/electrical/models',{signal},4*1024*1024,'event_page_bytes',false)
  }
  electricalOpen(query:Record<string,unknown>,signal?:AbortSignal):Promise<unknown> {
    return this.request(this.gridSourcePath+'/data-gateway/electrical/open',{method:'POST',signal,body:JSON.stringify(query)},4*1024*1024,'event_page_bytes',false)
  }
  electricalRead(query:{view_ref:string;stream:string;cursor?:string;limit?:number},signal?:AbortSignal):Promise<unknown> {
    return this.request(this.gridSourcePath+'/data-gateway/electrical/read',{method:'POST',signal,body:JSON.stringify(query)},4*1024*1024,'event_page_bytes',false)
  }
  electricalJob(job_ref:string,signal?:AbortSignal):Promise<unknown> {
    return this.request(this.gridSourcePath+'/data-gateway/electrical/job',{method:'POST',signal,body:JSON.stringify({job_ref})},4*1024*1024,'event_page_bytes',false)
  }

  gridSourceTopology(query: GridSourceQuery, signal?: AbortSignal) {
    return this.request(this.gridSourcePath+'/data-gateway/topology', {
      method:'POST', signal, body:JSON.stringify(query),
    },4*1024*1024,'event_page_bytes',false).then(parseGridSourcePage).catch(cause=>{
      if(cause instanceof ThreadTransportError)throw new Error(cause.status===409
        ?'源拓扑版本已变化，请重新加载。':cause.status===400?'源拓扑读取范围无效，请重新选择对象。':'源拓扑暂时无法读取，请稍后重新加载。')
      throw cause
    })
  }

  renameSession(threadId:string,runId:string,revision:number,text:string,commandId:string,idempotencyKey:string):Promise<unknown> {
    const transport=new HttpThreadTransport(this.base,this.token,this.fetcher,this.resourcePath,'2',this.workspaceName)
    return transport.request(`${this.resourcePath}/${encodeURIComponent(threadId)}/commands`,{method:'POST',headers:{'Idempotency-Key':idempotencyKey},body:JSON.stringify({schema:'capstone-command/2',thread_id:threadId,run_id:runId,command_id:commandId,idempotency_key:idempotencyKey,kind:'rename_session',target:{kind:'session_title',id:threadId,expected_revision:revision},payload:{text}})})
  }

  setSessionSkills(threadId:string,runId:string,revision:number,skills:import('./sessionSkills').SessionSkill[],commandId:string,idempotencyKey:string):Promise<unknown> {
    const transport=new HttpThreadTransport(this.base,this.token,this.fetcher,this.resourcePath,'2',this.workspaceName)
    return transport.request(`${this.resourcePath}/${encodeURIComponent(threadId)}/commands`,{method:'POST',headers:{'Idempotency-Key':idempotencyKey},body:JSON.stringify({schema:'capstone-command/2',thread_id:threadId,run_id:runId,command_id:commandId,idempotency_key:idempotencyKey,kind:'set_session_skills',target:{kind:'session_skills',id:threadId,expected_revision:revision},payload:{skills}})})
  }

  createWorkThread(signal?: AbortSignal): Promise<unknown> {
    if (this.protocolVersion !== '2') throw new Error('工作会话需要新版协议')
    return this.request(this.resourcePath, { method: 'POST', signal, body: JSON.stringify({}) })
  }

  readEvents(threadId: string, afterEventSeq: number, signal?: AbortSignal): Promise<unknown> {
    return this.request(`${this.resourcePath}/${encodeURIComponent(threadId)}/events?after=${afterEventSeq}`, { signal })
  }

  sendCommand(command: ThreadCommand | WorkCommand, signal?: AbortSignal): Promise<unknown> {
    return this.request(`${this.resourcePath}/${encodeURIComponent(command.thread_id)}/commands`, {
      method: 'POST', signal, body: JSON.stringify(command),
      headers: { 'Idempotency-Key': command.idempotency_key },
    })
  }

  sendWorkCommand(command: WorkCommand, signal?: AbortSignal): Promise<unknown> {
    return this.sendCommand(command, signal)
  }

  async *streamEvents(
    threadId: string, afterEventSeq: number, signal?: AbortSignal, onPreview?:(preview:ThinkingPreview)=>void,
  ): AsyncGenerator<EventEnvelope> {
    const response = await this.streamRequest(
      `${this.resourcePath}/${encodeURIComponent(threadId)}/events/stream?after=${afterEventSeq}&follow=1`,
      signal,
    )
    if (!response.body) throw new Error('Thread 事件流不可用')
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let cursor = afterEventSeq
    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, '\n')
        let boundary: number
        while ((boundary = buffer.indexOf('\n\n')) !== -1) {
          const frame = buffer.slice(0, boundary)
          buffer = buffer.slice(boundary + 2)
          assertCapacity(new TextEncoder().encode(frame).byteLength,'event_bytes','transport.sse.frame')
          const data = frame.split('\n').find((line) => line.startsWith('data: '))
          if (!data) continue
          const eventName = frame.split('\n').find((line) => line.startsWith('event: '))?.slice(7)
          const payload = JSON.parse(data.slice(6)) as unknown
          if(eventName==='thinking_preview') {onPreview?.(parseThinkingPreview(payload,threadId));continue}
          if (eventName === 'protocol_upgrade_required') throw responseError(409, payload)
          if (eventName === 'resync_required') {
            throw new ThreadTransportError(409, 'Thread SSE requires resync.', payload)
          }
          const event = parseEventEnvelope(payload)
          if (event.threadId !== threadId) throw new Error('Thread 事件身份无效')
          if (event.eventSeq <= cursor) continue
          cursor = event.eventSeq
          if (event.eventType === 'attempt_completed' && event.visibility === 'public' && event.attemptId)
            recordAnswerArrival(event.attemptId)
          yield event
        }
        assertCapacity(new TextEncoder().encode(buffer).byteLength,'event_bytes','transport.sse.buffer')
      }
    } finally {
      await reader.cancel().catch(() => undefined)
      reader.releaseLock()
    }
  }
}
