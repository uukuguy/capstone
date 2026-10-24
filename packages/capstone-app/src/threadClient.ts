import {assertCapacity} from './applicationCapacity'
import {
  parseCommandReceipt, parseContext, parseEventPage, parseThreadSnapshot,
  type CommandReceipt, type EventEnvelope, type EventPage, type ThreadSnapshot,
} from './threadProtocol'
import { parseThreadCatalog, type ThreadCatalog } from './threadCatalog'
import { parseNetworkContextEvents, parseThreadHistoryPage } from './threadHistory'
import { parseModelWorkspace } from './threadModelWorkspace'
import type { AttemptRecords } from './attemptRecords'
import type { ProcessProductPage } from './processProducts'
import type { NativeArtifact, NativeArtifactPage } from './nativeArtifacts'
import { parseWorkSnapshot, type WorkCommand } from './threadWorkProtocol'

export type AnyThreadCommand = ThreadCommand | WorkCommand

export type ThreadCommand = {
  schema: 'capstone-command/1'
  command_id: string
  idempotency_key: string
  thread_id: string
  run_id?: string
  kind: string
  expected_event_seq: number
  payload: Record<string, unknown>
}

export type ThreadTransportState = 'live' | 'reconnecting' | 'resync_required' | 'offline'

import type {ProductIndex,ProductQuery,ProductRef,ProductResolution} from './threadProducts'

export interface ThreadTransport {
  readProductIndex?(threadId:string,query?:ProductQuery,signal?:AbortSignal):Promise<ProductIndex>
  resolveProduct?(ref:ProductRef,signal?:AbortSignal):Promise<ProductResolution>
  uploadThreadMaterial?(threadId:string,file:File,signal?:AbortSignal):Promise<unknown>
  removeThreadMaterial?(threadId:string,materialId:string,signal?:AbortSignal):Promise<unknown>
  readNativeArtifacts?(threadId:string,attemptId:string,after?:number,signal?:AbortSignal):Promise<NativeArtifactPage>
  readNativeArtifact?(artifact:NativeArtifact,signal?:AbortSignal):Promise<Uint8Array>
  readProcessProducts?(threadId: string, before?: number, signal?: AbortSignal): Promise<ProcessProductPage>
  readAttemptRecords?(threadId: string, attemptId: string, after?: number, signal?: AbortSignal): Promise<AttemptRecords>
  createThread?(modelId?: string, signal?: AbortSignal): Promise<unknown>
  renameSession?(threadId:string,runId:string,revision:number,text:string,commandId:string,idempotencyKey:string):Promise<unknown>
  readDeliveries?(threadId:string,before?:number,signal?:AbortSignal):Promise<unknown>
  publishDelivery?(threadId:string,request:Record<string,unknown>):Promise<unknown>
  readDeliveryContent?(threadId:string,artifactId:string,revision:number,signal?:AbortSignal):Promise<string>
  readDeliveryFile?(threadId:string,artifactId:string,revision:number,size:number,digest:string,signal?:AbortSignal):Promise<Uint8Array>
  getSnapshot(threadId: string, signal?: AbortSignal): Promise<unknown>
  getCatalog?(threadId: string, signal?: AbortSignal): Promise<unknown>
  getInputCatalog?(threadId: string, signal?: AbortSignal): Promise<unknown>
  getModels?(threadId: string, signal?: AbortSignal): Promise<unknown>
  readHistory?(threadId: string, beforeEventSeq?: number, signal?: AbortSignal): Promise<unknown>
  readNetworkEvents?(threadId: string, signal?: AbortSignal, contextId?: string, attemptId?: string): Promise<unknown>
  readEvents(threadId: string, afterEventSeq: number, signal?: AbortSignal): Promise<unknown>
  sendCommand(command: ThreadCommand, signal?: AbortSignal): Promise<unknown>
  sendWorkCommand?(command: WorkCommand, signal?: AbortSignal): Promise<unknown>
  streamEvents?(threadId: string, afterEventSeq: number, signal?: AbortSignal): AsyncGenerator<EventEnvelope>
  readonly connectionState?: ThreadTransportState
}

const commandIdentifierPattern = /^[a-z][a-z0-9_-]{0,63}$/

export function buildThreadCommand(input: {
  threadId: string
  runId?: string
  kind: string
  expectedEventSeq: number
  commandId: string
  idempotencyKey: string
  payload: Record<string, unknown>
}): ThreadCommand {
  for (const [name, value] of [
    ['threadId', input.threadId], ['commandId', input.commandId], ['idempotencyKey', input.idempotencyKey], ['kind', input.kind],
  ] as const) {
    if (!commandIdentifierPattern.test(value)) throw new Error(`${name} is invalid`)
  }
  if (input.runId !== undefined && !commandIdentifierPattern.test(input.runId)) throw new Error('runId is invalid')
  if (!Number.isSafeInteger(input.expectedEventSeq) || input.expectedEventSeq < 0) throw new Error('expectedEventSeq is invalid')
  if(typeof input.payload.text==='string')assertCapacity(input.payload.text.length,'input_text_chars')
  assertCapacity(new TextEncoder().encode(JSON.stringify(input)).byteLength,'command_bytes')
  return {
    schema: 'capstone-command/1', command_id: input.commandId,
    idempotency_key: input.idempotencyKey, thread_id: input.threadId,
    ...(input.runId === undefined ? {} : { run_id: input.runId }),
    kind: input.kind, expected_event_seq: input.expectedEventSeq,
    payload: { ...input.payload },
  }
}

export class CapstoneThreadClient {
  constructor(private readonly transport: ThreadTransport) {}
  get supportsProductIndex():boolean{return Boolean(this.transport.readProductIndex&&this.transport.resolveProduct)}
  async productIndex(threadId:string,query:ProductQuery={},signal?:AbortSignal):Promise<ProductIndex>{
    if(!this.transport.readProductIndex)throw new Error('当前服务未提供统一成果目录')
    return this.transport.readProductIndex(threadId,query,signal)
  }
  async resolveProduct(ref:ProductRef,signal?:AbortSignal):Promise<ProductResolution>{
    if(!this.transport.resolveProduct)throw new Error('当前服务未提供成果读取')
    return this.transport.resolveProduct(ref,signal)
  }

  async uploadThreadMaterial(threadId:string,file:File,signal?:AbortSignal) {
    if(!this.transport.uploadThreadMaterial)throw new Error('当前服务不支持资料上传')
    return this.transport.uploadThreadMaterial(threadId,file,signal)
  }
  async removeThreadMaterial(threadId:string,materialId:string,signal?:AbortSignal) {
    if(!this.transport.removeThreadMaterial)throw new Error('当前服务不支持资料移除')
    return this.transport.removeThreadMaterial(threadId,materialId,signal)
  }

  async nativeArtifacts(threadId:string,attemptId:string,after=0,signal?:AbortSignal):Promise<NativeArtifactPage> {
    if(!this.transport.readNativeArtifacts)throw new Error('指令文件目录不可用')
    return this.transport.readNativeArtifacts(threadId,attemptId,after,signal)
  }
  async nativeArtifact(artifact:NativeArtifact,signal?:AbortSignal):Promise<Uint8Array> {
    if(!this.transport.readNativeArtifact)throw new Error('指令文件读取不可用')
    return this.transport.readNativeArtifact(artifact,signal)
  }

  get connectionState(): ThreadTransportState {
    return this.transport.connectionState ?? 'live'
  }

  get supportsEventStream(): boolean {
    return this.transport.streamEvents !== undefined
  }

  get supportsHistory(): boolean { return this.transport.readHistory !== undefined }

  get supportsAttemptRecords(): boolean { return this.transport.readAttemptRecords !== undefined }
  get supportsProcessProducts(): boolean { return this.transport.readProcessProducts !== undefined }

  async processProducts(threadId: string, before?: number, signal?: AbortSignal): Promise<ProcessProductPage> {
    if (!this.transport.readProcessProducts) throw new Error('过程制品目录暂不可用')
    return this.transport.readProcessProducts(threadId, before, signal)
  }

  async attemptRecords(threadId: string, attemptId: string, after = 0, signal?: AbortSignal): Promise<AttemptRecords> {
    if (!this.transport.readAttemptRecords) throw new Error('任务记录读取不可用')
    if (!Number.isSafeInteger(after) || after < 0) throw new Error('任务记录游标无效')
    const page = await this.transport.readAttemptRecords(threadId, attemptId, after, signal)
    if (page.threadId !== threadId || page.attemptId !== attemptId) throw new Error('任务记录身份不一致')
    return page
  }

  async history(threadId: string, beforeEventSeq?: number, signal?: AbortSignal) {
    if (!this.transport.readHistory) throw new Error('History paging unavailable')
    return parseThreadHistoryPage(await this.transport.readHistory(threadId, beforeEventSeq, signal), threadId, beforeEventSeq)
  }

  async networkContextEvents(threadId: string, contextId: string, signal?: AbortSignal): Promise<EventEnvelope[]> {
    if (!this.transport.readNetworkEvents) return []
    return parseNetworkContextEvents(await this.transport.readNetworkEvents(threadId, signal), threadId, contextId)
  }

  async models(threadId: string, signal?: AbortSignal) {
    if (!this.transport.getModels) return null
    const value = await this.transport.getModels(threadId, signal)
    return value === null ? null : parseModelWorkspace(value, threadId)
  }

  async historicalNetwork(threadId: string, contextId: string, attemptId?: string) {
    if (!this.transport.readNetworkEvents) throw new Error('历史电网投影不可用')
    const value = await this.transport.readNetworkEvents(threadId, undefined, contextId, attemptId)
    const body = value as Record<string, unknown>
    const context = parseContext(body.model_context, 'historical model context')
    if (context.id !== contextId) throw new Error('历史模型身份不一致')
    return { context, events: parseNetworkContextEvents(value, threadId, contextId) }
  }

  async create(modelId?: string, signal?: AbortSignal): Promise<ThreadSnapshot> {
    if (!this.transport.createThread) throw new Error('Thread transport does not support creation')
    return parseThreadSnapshot(await this.transport.createThread(modelId, signal))
  }

  async load(threadId: string, signal?: AbortSignal): Promise<ThreadSnapshot> {
    return parseThreadSnapshot(await this.transport.getSnapshot(threadId, signal))
  }

  get supportsSessionTitle():boolean {return Boolean(this.transport.renameSession)}
  get supportsDeliveries():boolean {return Boolean(this.transport.readDeliveries&&this.transport.publishDelivery&&this.transport.readDeliveryContent)}
  get supportsDeliveryFiles():boolean {return Boolean(this.transport.readDeliveryFile)}
  async deliveryFile(threadId:string,artifactId:string,revision:number,size:number,digest:string,signal?:AbortSignal) {
    if(!this.transport.readDeliveryFile)throw new Error('交付文件不可用')
    return this.transport.readDeliveryFile(threadId,artifactId,revision,size,digest,signal)
  }
  async deliveries(threadId:string,before?:number,signal?:AbortSignal){
    if(!this.transport.readDeliveries)throw new Error('交付目录不可用')
    return this.transport.readDeliveries(threadId,before,signal)
  }
  async publishDelivery(threadId:string,request:Record<string,unknown>){
    if(!this.transport.publishDelivery)throw new Error('交付生成不可用')
    return this.transport.publishDelivery(threadId,request)
  }
  async deliveryContent(threadId:string,artifactId:string,revision:number,signal?:AbortSignal){
    if(!this.transport.readDeliveryContent)throw new Error('交付文件不可用')
    return this.transport.readDeliveryContent(threadId,artifactId,revision,signal)
  }
  async renameSession(threadId:string,runId:string,revision:number,text:string,commandId:string,idempotencyKey:string) {
    if(!this.transport.renameSession)throw new Error('当前服务不支持会话改名')
    return parseCommandReceipt(await this.transport.renameSession(threadId,runId,revision,text,commandId,idempotencyKey))
  }

  async loadWork(threadId: string, signal?: AbortSignal) {
    const raw = await this.transport.getSnapshot(threadId, signal)
    return raw && typeof raw === 'object' && 'schema' in raw && raw.schema === 'capstone-thread-snapshot/2'
      ? parseWorkSnapshot(raw) : parseThreadSnapshot(raw)
  }

  async caseExecution(threadId: string, signal?: AbortSignal) {
    const snapshot = await this.load(threadId, signal)
    return snapshot.applicationState?.caseExecution ?? null
  }

  async caseCommand(
    threadId: string, runId: string, kind: 'start_case_execution' | 'retry_case_step' | 'cancel_case_execution' | 'resume_case_execution',
    payload: Record<string, unknown>, expectedEventSeq: number,
    identity: { commandId: string; idempotencyKey: string }, signal?: AbortSignal,
  ): Promise<CommandReceipt> {
    return this.send(buildThreadCommand({ threadId, runId, kind, expectedEventSeq, payload, ...identity }), signal)
  }

  async catalog(threadId: string, signal?: AbortSignal): Promise<ThreadCatalog> {
    if (!this.transport.getCatalog) return { models: [], profiles: [] }
    return parseThreadCatalog(await this.transport.getCatalog(threadId, signal))
  }

  async inputCatalog(threadId: string, signal?: AbortSignal) {
    if (!this.transport.getInputCatalog) return undefined
    const { parseInputCatalog } = await import('./threadInput')
    return parseInputCatalog(await this.transport.getInputCatalog(threadId, signal))
  }

  async readAfter(threadId: string, afterEventSeq: number, signal?: AbortSignal): Promise<EventPage> {
    return parseEventPage(
      await this.transport.readEvents(threadId, afterEventSeq, signal),
      afterEventSeq,
    )
  }

  async send(command: AnyThreadCommand, signal?: AbortSignal): Promise<CommandReceipt> {
    if (command.schema === 'capstone-command/2') {
      if (!this.transport.sendWorkCommand) throw new Error('工作命令传输不可用')
      return parseCommandReceipt(await this.transport.sendWorkCommand(command, signal))
    }
    return parseCommandReceipt(await this.transport.sendCommand(command, signal))
  }

  async switchModel(
    threadId: string, runId: string, modelId: string, expectedEventSeq: number,
    identity: { commandId: string; idempotencyKey: string }, signal?: AbortSignal,
  ): Promise<CommandReceipt> {
    return this.send(buildThreadCommand({
      threadId, runId, kind: 'switch_model', expectedEventSeq,
      commandId: identity.commandId, idempotencyKey: identity.idempotencyKey,
      payload: { model_id: modelId },
    }), signal)
  }

  async *events(threadId: string, afterEventSeq: number, signal?: AbortSignal): AsyncGenerator<EventEnvelope> {
    if (!this.transport.streamEvents) throw new Error('Thread transport does not support SSE')
    for await (const event of this.transport.streamEvents(threadId, afterEventSeq, signal)) yield event
  }
}
