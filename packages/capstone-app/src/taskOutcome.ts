export type TaskOutcome = {
  schema: 'capstone-task-outcome/1'
  status: 'complete' | 'partial' | 'unavailable'
  work: { id: string; status: 'confirmed' | 'blocked'; summary: string; result_refs: string[]; evidence_refs: string[] }[]
  diagnostics: { code: string; category: string; stage: string; confirmation: 'confirmed' | 'unknown'; summary: string; work_id: string; recovery: string }[]
}

const record = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null && !Array.isArray(value)
const keys = (value: Record<string, unknown>, expected: string[]) => Object.keys(value).length === expected.length && expected.every(key => key in value)
const text = (value: unknown, max = 512): value is string => typeof value === 'string' && value.length > 0 && value.length <= max
const refs = (value: unknown): value is string[] => Array.isArray(value) && value.length <= 128 && value.every(item => text(item)) && new Set(value).size === value.length

export function parseTaskOutcome(value: unknown): TaskOutcome | undefined {
  if (!record(value) || !keys(value, ['schema', 'status', 'work', 'diagnostics']) || value.schema !== 'capstone-task-outcome/1'
    || !['complete', 'partial', 'unavailable'].includes(String(value.status)) || !Array.isArray(value.work) || value.work.length > 32
    || !Array.isArray(value.diagnostics) || value.diagnostics.length > 32) return undefined
  const identities = new Set<string>()
  for (const item of value.work) {
    if (!record(item) || !keys(item, ['id', 'status', 'summary', 'result_refs', 'evidence_refs']) || !text(item.id, 256)
      || identities.has(item.id) || !['confirmed', 'blocked'].includes(String(item.status)) || !text(item.summary)
      || !refs(item.result_refs) || !refs(item.evidence_refs) || (item.status === 'blocked' && (item.result_refs.length || item.evidence_refs.length))) return undefined
    identities.add(item.id)
  }
  for (const item of value.diagnostics) {
    if (!record(item) || !keys(item, ['code', 'category', 'stage', 'confirmation', 'summary', 'work_id', 'recovery'])
      || !text(item.code, 64) || !/^[a-z][a-z0-9_]{0,63}$/.test(item.code) || !text(item.summary)
      || !text(item.work_id, 256) || !identities.has(item.work_id)
      || !['input', 'calculation', 'capability', 'invocation', 'service', 'admission', 'storage', 'unknown'].includes(String(item.category))
      || !['parse', 'validate', 'execute', 'admit', 'persist'].includes(String(item.stage))
      || !['confirmed', 'unknown'].includes(String(item.confirmation))
      || !['retry', 'provide_input', 'change_scope', 'wait_for_service', 'report_issue', 'none'].includes(String(item.recovery))) return undefined
  }
  const confirmed = value.work.some(item => item.status === 'confirmed')
  const blocked = value.work.some(item => item.status === 'blocked')
  if ((value.status === 'partial' && !(confirmed && blocked)) || (value.status === 'unavailable' && confirmed) || (value.status === 'complete' && blocked)) return undefined
  return value as TaskOutcome
}
