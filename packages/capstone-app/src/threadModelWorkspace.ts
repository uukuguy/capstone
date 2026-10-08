import { ThreadProtocolError } from './threadProtocol'

export type OpenedModel = {
  entryId: string; modelId: string; modelRevision: string; implementationFamily: string;
  authorityModelRef: string | null; displayName: string; diagramProviderId: string | null; lastActiveSeq: number
}
export type ModelWorkspace = {
  threadId: string; runId: string; eventSeq: number; currentEntryId: string;
  models: OpenedModel[]; blockedReason: string | null
}

export function parseModelControl(text: string): { kind: 'open_model' | 'activate_model' | 'close_model'; reference: string; openedOnly: boolean; task?: string } | null {
  const match = text.trim().replace(/[。.!！?？]+$/u, '').match(/^(打开|切换到|切换至|关闭)\s*(.+)$/u)
  if (!match) return null
  let reference = match[2].trim()
  const openedOnly = /^已打开的?\s*/u.test(reference)
  reference = reference.replace(/^已打开的?\s*/u, '')
  const boundary = reference.match(/[，,；;]\s*(?:然后|并)?\s*|(?:然后|并)(?=运行|执行|计算|分析|检查|查看)/u)
  let task: string | undefined
  if (boundary?.index !== undefined) {
    task = reference.slice(boundary.index + boundary[0].length).trim()
    reference = reference.slice(0, boundary.index).trim()
  }
  if (!reference) return null
  return { kind: match[1] === '关闭' ? 'close_model' : match[1] === '打开' ? 'open_model' : 'activate_model', reference, openedOnly, ...(task ? { task } : {}) }
}

export function parseModelWorkspace(value: unknown, threadId: string): ModelWorkspace {
  const fail = (): never => { throw new ThreadProtocolError('模型集合身份或内容无效') }
  const object = (item: unknown): Record<string, unknown> => item !== null && typeof item === 'object' && !Array.isArray(item) ? item as Record<string, unknown> : fail()
  const text = (item: unknown): string => typeof item === 'string' && item.trim().length > 0 && item.length <= 256 ? item : fail()
  const sequence = (item: unknown): number => typeof item === 'number' && Number.isSafeInteger(item) && item >= 0 ? item : fail()
  const fields = (item: Record<string, unknown>, allowed: string[]) => { if (Object.keys(item).length !== allowed.length || allowed.some((key) => !(key in item))) fail() }
  const body = object(value)
  fields(body, ['schema', 'thread_id', 'run_id', 'event_seq', 'current_entry_id', 'models', 'blocked_reason'])
  if (body.schema !== 'capstone-thread-model-workspace/1' || body.thread_id !== threadId ||
      new TextEncoder().encode(JSON.stringify(body)).length > 64 * 1024 ||
      !Array.isArray(body.models) || !body.models.length || body.models.length > 64) fail()
  const models = (body.models as unknown[]).map((item): OpenedModel => {
    const model = object(item)
    fields(model, ['entry_id', 'model_id', 'model_revision', 'implementation_family', 'authority_model_ref', 'display_name', 'diagram_provider_id', 'last_active_seq'])
    if (!/^[a-z][a-z0-9_-]{0,63}$/.test(text(model.entry_id)) || !/^[a-z][a-z0-9_-]{0,63}$/.test(text(model.implementation_family)) || sequence(model.last_active_seq) > sequence(body.event_seq)) fail()
    return { entryId: text(model.entry_id), modelId: text(model.model_id), modelRevision: text(model.model_revision),
      implementationFamily: text(model.implementation_family), displayName: text(model.display_name),
      authorityModelRef: model.authority_model_ref === null ? null : text(model.authority_model_ref),
      diagramProviderId: model.diagram_provider_id === null ? null : text(model.diagram_provider_id), lastActiveSeq: sequence(model.last_active_seq) }
  })
  const currentEntryId = text(body.current_entry_id)
  if (new Set(models.map((model) => model.entryId)).size !== models.length ||
      new Set(models.map((model) => `${model.implementationFamily}\0${model.modelId}\0${model.modelRevision}`)).size !== models.length || !models.some((model) => model.entryId === currentEntryId)) fail()
  return { threadId, runId: text(body.run_id), eventSeq: sequence(body.event_seq), currentEntryId, models,
    blockedReason: body.blocked_reason === null ? null : text(body.blocked_reason) }
}
