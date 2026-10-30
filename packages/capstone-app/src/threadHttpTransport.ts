import {applicationCapacity,assertCapacity,exceedsCapacity,CapacityError,type CapacityKey} from './applicationCapacity'
import { parseEventEnvelope, type EventEnvelope } from './threadProtocol'
import { parseGridSourcePage, parseGridSourceScopes, type GridSourceQuery } from './gridSource'
import type { ThreadCommand, ThreadTransport, ThreadTransportState } from './threadClient'
import { parseThreadDescriptor, parseThreadListPage, type ThreadListPage, type ThreadDescriptor } from './threadManagement'
import { fetchWithReadRetry } from './httpRetry'
import { parseAttemptRecords } from './attemptRecords'
import { parseProcessProducts } from './processProducts'
import type { WorkCommand } from './threadWorkProtocol'
import {parseNativeArtifact,parseNativeArtifacts,type NativeArtifact} from './nativeArtifacts'
import {parseProductIndex,parseProductRef,parseProductResolution,type ProductQuery,type ProductRef} from './threadProducts'
import {transferResource,parseStoredResources} from './resourceUploads'
import {parseCapacityFailure} from './capacityFailure'
import {parseGatewayConnectionStatus} from './threadInput'
import type {WorkspaceConnections} from './workspaceConnections'
import type {GatewayConnectionInput} from './gatewayConnectionTypes'
import {parseGatewayConnections,parseGatewayProbe} from './gatewayConnectionProtocol'
import {currentWorkspaceName,normalizeWorkspaceName} from './workspaceName'

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
  const actual=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),value=>value.toString(16).padStart(2,'0')).join('')
  if(actual!==digest)throw new Error('文件校验失败')
  return bytes
}

/** HTTP adapter for the negotiated Thread API; payload parsing remains in the client. */
export class HttpThreadTransport implements ThreadTransport {
  readonly workspaceName:string
  private get workspaceHeaders():Record<string,string>{return this.workspaceName==='enterprise'?{}:{'Capstone-Workspace':encodeURIComponent(this.workspaceName)}}
  readonly workspaceConnectionsScope:object
  readonly connectionState: ThreadTransportState = 'live'
  private readonly base: string
  private readonly resourcePath: string
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

  async workspaceConnections():Promise<WorkspaceConnections> {
    const value=await this.request('/api/v1/workspace/connections') as WorkspaceConnections
    if(!value||value.schema!=='capstone-workspace-connections/1')throw new Error('工作台连接信息无效')
    return {schema:value.schema,...(value.data_gateway===undefined?{}:{data_gateway:parseGatewayConnectionStatus(value.data_gateway)})}
  }

  private async gatewayRequest(action?:string,body?:unknown){
    const signal=AbortSignal.timeout(applicationCapacity('ui_network_status_timeout_ms')*(action?2:1))
    try{return await this.request('/api/v1/workspace/gateways'+(action?'/'+action:''),action?{method:'POST',body:JSON.stringify(body??{}),signal}:{signal})}
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
  async selectGatewayConnection(id:string){return parseGatewayConnections(await this.gatewayRequest('select',{id}))}
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
    if(path===this.resourcePath||path.startsWith(this.resourcePath+'/'))await this.checkWorkspace(response)
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
    return parseStoredResources(await this.request(`${this.resourcePath}/${encodeURIComponent(threadId)}/resources${draft?'?draft=true':''}`,{signal}),threadId)
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
    return this.request('/api/v1/grid-sources/data-gateway/scopes',{signal},4*1024*1024,'event_page_bytes',false)
      .then(parseGridSourceScopes).catch(cause=>{
        if(cause instanceof ThreadTransportError)throw new Error('电网范围目录暂时无法读取。')
        throw cause
      })
  }

  electricalModels(signal?:AbortSignal):Promise<unknown> {
    return this.request('/api/v1/grid-sources/data-gateway/electrical/models',{signal},4*1024*1024,'event_page_bytes',false)
  }
  electricalOpen(query:Record<string,unknown>,signal?:AbortSignal):Promise<unknown> {
    return this.request('/api/v1/grid-sources/data-gateway/electrical/open',{method:'POST',signal,body:JSON.stringify(query)},4*1024*1024,'event_page_bytes',false)
  }
  electricalRead(query:{view_ref:string;stream:string;cursor?:string;limit?:number},signal?:AbortSignal):Promise<unknown> {
    return this.request('/api/v1/grid-sources/data-gateway/electrical/read',{method:'POST',signal,body:JSON.stringify(query)},4*1024*1024,'event_page_bytes',false)
  }
  electricalJob(job_ref:string,signal?:AbortSignal):Promise<unknown> {
    return this.request('/api/v1/grid-sources/data-gateway/electrical/job',{method:'POST',signal,body:JSON.stringify({job_ref})},4*1024*1024,'event_page_bytes',false)
  }

  gridSourceTopology(query: GridSourceQuery, signal?: AbortSignal) {
    return this.request('/api/v1/grid-sources/data-gateway/topology', {
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
    threadId: string, afterEventSeq: number, signal?: AbortSignal,
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
          if (eventName === 'protocol_upgrade_required') throw responseError(409, payload)
          if (eventName === 'resync_required') {
            throw new ThreadTransportError(409, 'Thread SSE requires resync.', payload)
          }
          const event = parseEventEnvelope(payload)
          if (event.threadId !== threadId) throw new Error('Thread 事件身份无效')
          if (event.eventSeq <= cursor) continue
          cursor = event.eventSeq
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
