export type RunState = 'created' | 'open' | 'closing' | 'closed' | 'failed'
export type AttemptPhase = 'created' | 'accepted' | 'running' | 'waiting' | 'committing' |
  'cancelled' | 'interrupted' | 'completed' | 'failed'

export type RunSnapshot = { runId: string; state: RunState }
export type ModelContextSnapshot = {
  id: string; modelId: string; modelRevision: string; implementationFamily: string; selectionRevision: string
  enabledProfiles: Array<{ profileId: string; profileVersion: string }>
}
export type ProfileReference = { profileId: string; profileVersion: string }
export type PendingSelectionSnapshot = { commandId: string; enabledProfiles: ProfileReference[] }
export type PendingModelSwitchSnapshot = {
  commandId: string; modelId: string; modelRevision: string; implementationFamily: string
  enabledProfiles: ProfileReference[]
}
export type AttemptSnapshot = {
  turnId: string; attemptId: string; phase: AttemptPhase; targetModelContextId: string
}
export type CaseStepSnapshot = {
  ordinal: number; title: string; status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled' | 'interrupted'
  durationMs: number | null
  details: Record<string, unknown>
}
export type CaseActionSnapshot = { actionId: 'start_case' | 'retry_case_step' | 'cancel_case' | 'view_case_details'; label: string; enabled: boolean }
export type CaseExecutionSnapshot = {
  displayName: string
  status: 'idle' | 'created' | 'running' | 'waiting_step' | 'blocked' | 'cancelled' | 'completed'
  completedSteps: number; totalSteps: number; currentStep: number | null
  steps: CaseStepSnapshot[]; actions: CaseActionSnapshot[]; disabledReasons: string[]
}
export type ResultMetric = { metricId: string; label: string; value: string | number | boolean | null; unit?: string; severity?: 'info' | 'warning' | 'error' }
export type ResultElementRef = { elementKind: string; elementId: string }
export type ResultColumn = { columnId: string; label: string; unit?: string }
export type ResultRow = { rowId: string; cells: Record<string, string | number | boolean | null>; elementRef?: ResultElementRef }
export type ResultTable = { tableId: string; title: string; columns: ResultColumn[]; rows: ResultRow[] }
export type ResultOverlay = { metric: string; unit: string; sourceRef: string; values: Array<{ elementId: string; value: number }> }
export type ResultProjection = {
  resultId: string; resultRef?: string; evidenceRefs: string[]
  threadId: string; runId: string; turnId: string; attemptId: string
  modelContextId: string; modelId: string; modelRevision: string
  source: { capabilityId: string; domainPackId: string; implementationFamily: string }
  status: 'completed' | 'partial' | 'unavailable'
  summary: ResultMetric[]; tables: ResultTable[]; elementRefs: ResultElementRef[]
  overlay?: ResultOverlay; unavailableReason?: string
}
export type ThreadSnapshot = {
  threadId: string
  run: RunSnapshot
  activeModelContext: ModelContextSnapshot
  activeGridPageId: string
  currentAttempt: AttemptSnapshot | null
  lastEventSeq: number
  baseEventSeq: number
  pendingSelection?: PendingSelectionSnapshot
  pendingModelSwitch?: PendingModelSwitchSnapshot
  resultProjections?: ResultProjection[]
  applicationState?: { caseExecution?: CaseExecutionSnapshot; [key: string]: unknown }
  toDocument: () => Record<string, unknown>
}

export type EventEnvelope = {
  eventId: string
  eventSeq: number
  eventType: string
  eventVersion: number
  threadId: string
  runId: string
  turnId?: string
  attemptId?: string
  modelContextId?: string
  selectionRevision?: string
  occurredAt: string
  visibility: 'public' | 'diagnostic'
  payload: Record<string, unknown>
}
export type EventPage = {
  threadId: string
  afterEventSeq: number
  nextEventSeq: number
  hasMore: boolean
  events: EventEnvelope[]
  toDocument: () => Record<string, unknown>
}

export type CommandReceipt = {
  commandId: string
  idempotencyKey: string
  threadId: string
  runId?: string
  status: 'accepted' | 'rejected' | 'pending'
  acceptedEventSeq?: number
  rejection?: string
  target?: Record<string, unknown>
  toDocument: () => Record<string, unknown>
}

export class ThreadProtocolError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'ThreadProtocolError'
  }
}

const identifierPattern = /^[a-z][a-z0-9_-]{0,63}$/
const runStates = new Set<RunState>(['created', 'open', 'closing', 'closed', 'failed'])
const attemptPhases = new Set<AttemptPhase>([
  'created', 'accepted', 'running', 'waiting', 'committing',
  'cancelled', 'interrupted', 'completed', 'failed',
])
const caseStatuses = new Set<CaseExecutionSnapshot['status']>(['idle', 'created', 'running', 'waiting_step', 'blocked', 'cancelled', 'completed'])
const caseStepStatuses = new Set<CaseStepSnapshot['status']>(['pending', 'running', 'completed', 'failed', 'cancelled', 'interrupted'])
const caseActionIds = new Set<CaseActionSnapshot['actionId']>(['start_case', 'retry_case_step', 'cancel_case', 'view_case_details'])
const maxApplicationStateBytes = 64 * 1024
const maxCaseTextChars = 256
const maxCaseDetailsBytes = 16 * 1024
const maxCaseActions = 4
const maxCaseReasons = 16
const maxCaseDurationMs = 86_400_000
const caseActionMatrix: Record<CaseExecutionSnapshot['status'], readonly CaseActionSnapshot['actionId'][]> = {
  idle: ['start_case'], created: [], running: ['cancel_case'], waiting_step: ['cancel_case'],
  blocked: ['retry_case_step', 'cancel_case'], cancelled: [], completed: ['view_case_details'],
}
const resultProjectionStatuses = new Set<ResultProjection['status']>(['completed', 'partial', 'unavailable'])
const resultProjectionSeverities = new Set<ResultMetric['severity']>(['info', 'warning', 'error'])
const resultRefPattern = /^(result|evidence|revision):sha256:[0-9a-f]{64}$/
const maxResultSummary = 32
const maxResultTables = 12
const maxResultColumns = 32
const maxResultRows = 128
const maxResultElements = 128
const maxResultOverlayValues = 256
const maxResultText = 256

function object(value: unknown, name: string): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new ThreadProtocolError(`${name} must be an object`)
  }
  return value as Record<string, unknown>
}

function fields(value: Record<string, unknown>, allowed: ReadonlySet<string>, name: string): void {
  const unknown = Object.keys(value).filter((key) => !allowed.has(key))
  if (unknown.length) throw new ThreadProtocolError(`${name} has unknown field: ${unknown.sort().join(', ')}`)
}

function required(value: Record<string, unknown>, keys: readonly string[], name: string): void {
  const missing = keys.filter((key) => !(key in value))
  if (missing.length) throw new ThreadProtocolError(`${name} is missing field: ${missing.join(', ')}`)
}

function identifier(value: unknown, name: string): string {
  if (typeof value !== 'string' || !identifierPattern.test(value)) throw new ThreadProtocolError(`${name} is invalid`)
  return value
}

function text(value: unknown, name: string): string {
  if (typeof value !== 'string' || !value) throw new ThreadProtocolError(`${name} is invalid`)
  return value
}

function caseText(value: unknown, name: string): string {
  const result = text(value, name)
  if (result.length > maxCaseTextChars) throw new ThreadProtocolError(`${name} is too long`)
  return result
}

function sequence(value: unknown, name: string): number {
  if (!Number.isSafeInteger(value) || (value as number) < 0) throw new ThreadProtocolError(`${name} is invalid`)
  return value as number
}

function jsonValue(value: unknown, name: string): void {
  try { JSON.stringify(value) } catch { throw new ThreadProtocolError(`${name} is not JSON`) }
}

function jsonBytes(value: unknown, name: string): number {
  try {
    const encoded = JSON.stringify(value)
    if (encoded === undefined) throw new Error('undefined')
    return new TextEncoder().encode(encoded).length
  } catch {
    throw new ThreadProtocolError(`${name} is not JSON`)
  }
}

function timestamp(value: unknown, name: string): string {
  const result = text(value, name)
  if (Number.isNaN(Date.parse(result))) throw new ThreadProtocolError(`${name} is invalid`)
  return result
}

function resultText(value: unknown, name: string): string {
  const result = text(value, name)
  if (result.length > maxResultText) throw new ThreadProtocolError(`${name} is too long`)
  return result
}

function resultIdentifier(value: unknown, name: string): string {
  const result = resultText(value, name)
  if (!/^[a-z][a-z0-9_.:-]{0,127}$/.test(result)) throw new ThreadProtocolError(`${name} is invalid`)
  return result
}

function resultRef(value: unknown, name: string, kind?: string): string {
  const result = resultText(value, name)
  const match = result.match(resultRefPattern)
  if (!match || (kind && match[1] !== kind)) throw new ThreadProtocolError(`${name} is invalid`)
  return result
}

function resultScalar(value: unknown, name: string): string | number | boolean | null {
  if (value === null || typeof value === 'string' || typeof value === 'boolean') {
    if (typeof value === 'string' && value.length > maxResultText) throw new ThreadProtocolError(`${name} is too long`)
    return value
  }
  if (typeof value === 'number' && Number.isFinite(value)) return value
  throw new ThreadProtocolError(`${name} must be scalar`)
}

function parseResultElementRef(value: unknown, name: string): ResultElementRef {
  const document = object(value, name)
  fields(document, new Set(['element_kind', 'element_id']), name)
  required(document, ['element_kind', 'element_id'], name)
  return { elementKind: resultIdentifier(document.element_kind, `${name}.element_kind`), elementId: resultIdentifier(document.element_id, `${name}.element_id`) }
}

function parseResultProjection(value: unknown): ResultProjection {
  const document = object(value, 'result projection')
  const keys = ['schema', 'result_id', 'result_ref', 'evidence_refs', 'thread_id', 'run_id', 'turn_id', 'attempt_id', 'model_context_id', 'model_id', 'model_revision', 'source', 'status', 'summary', 'tables', 'element_refs', 'overlay', 'unavailable_reason']
  fields(document, new Set(keys), 'result projection')
  required(document, keys.slice(0, 17), 'result projection')
  if (document.schema !== 'capstone-result-projection/1.0') throw new ThreadProtocolError('result projection.schema is invalid')
  const status = resultText(document.status, 'result projection.status') as ResultProjection['status']
  if (!resultProjectionStatuses.has(status)) throw new ThreadProtocolError('result projection.status is invalid')
  const source = object(document.source, 'result projection.source')
  fields(source, new Set(['capability_id', 'domain_pack_id', 'implementation_family']), 'result projection.source')
  required(source, ['capability_id', 'domain_pack_id', 'implementation_family'], 'result projection.source')
  if (!Array.isArray(document.evidence_refs) || document.evidence_refs.length > maxResultElements) throw new ThreadProtocolError('result projection.evidence_refs is invalid')
  const evidenceRefs = document.evidence_refs.map((item, index) => resultRef(item, `result projection.evidence_refs[${index}]`, 'evidence'))
  const resultReference = document.result_ref == null ? undefined : resultRef(document.result_ref, 'result projection.result_ref', 'result')
  if (!Array.isArray(document.summary) || document.summary.length > maxResultSummary) throw new ThreadProtocolError('result projection.summary is invalid')
  const summary = document.summary.map((entry, index) => {
    const item = object(entry, `result projection.summary[${index}]`)
    fields(item, new Set(['metric_id', 'label', 'value', 'unit', 'severity']), `result projection.summary[${index}]`)
    required(item, ['metric_id', 'label', 'value'], `result projection.summary[${index}]`)
    const severity = item.severity == null ? undefined : resultText(item.severity, `result projection.summary[${index}].severity`) as ResultMetric['severity']
    if (severity && !resultProjectionSeverities.has(severity)) throw new ThreadProtocolError('result projection metric severity is invalid')
    return { metricId: resultIdentifier(item.metric_id, `result projection.summary[${index}].metric_id`), label: resultText(item.label, `result projection.summary[${index}].label`), value: resultScalar(item.value, `result projection.summary[${index}].value`), ...(item.unit == null ? {} : { unit: resultText(item.unit, `result projection.summary[${index}].unit`) }), ...(severity ? { severity } : {}) }
  })
  if (new Set(summary.map((item) => item.metricId)).size !== summary.length) throw new ThreadProtocolError('result projection summary contains duplicates')
  if (!Array.isArray(document.tables) || document.tables.length > maxResultTables) throw new ThreadProtocolError('result projection.tables is invalid')
  const tables = document.tables.map((entry, tableIndex) => {
    const item = object(entry, `result projection.tables[${tableIndex}]`)
    fields(item, new Set(['table_id', 'title', 'columns', 'rows']), `result projection.tables[${tableIndex}]`)
    required(item, ['table_id', 'title', 'columns', 'rows'], `result projection.tables[${tableIndex}]`)
    if (!Array.isArray(item.columns) || !item.columns.length || item.columns.length > maxResultColumns || !Array.isArray(item.rows) || item.rows.length > maxResultRows) throw new ThreadProtocolError('result projection table arrays are invalid')
    const columns = item.columns.map((entry, columnIndex) => {
      const column = object(entry, `result projection.tables[${tableIndex}].columns[${columnIndex}]`)
      fields(column, new Set(['column_id', 'label', 'unit']), `result projection.tables[${tableIndex}].columns[${columnIndex}]`)
      required(column, ['column_id', 'label'], `result projection.tables[${tableIndex}].columns[${columnIndex}]`)
      return { columnId: resultIdentifier(column.column_id, 'result column.column_id'), label: resultText(column.label, 'result column.label'), ...(column.unit == null ? {} : { unit: resultText(column.unit, 'result column.unit') }) }
    })
    const columnIds = new Set(columns.map((column) => column.columnId))
    if (columnIds.size !== columns.length) throw new ThreadProtocolError('result projection table columns contain duplicates')
    const rows = item.rows.map((entry, rowIndex) => {
      const row = object(entry, `result projection.tables[${tableIndex}].rows[${rowIndex}]`)
      fields(row, new Set(['row_id', 'cells', 'element_ref']), `result projection.tables[${tableIndex}].rows[${rowIndex}]`)
      required(row, ['row_id', 'cells'], `result projection.tables[${tableIndex}].rows[${rowIndex}]`)
      const cells = object(row.cells, 'result row.cells')
      if (Object.keys(cells).some((key) => !columnIds.has(key))) throw new ThreadProtocolError('result row contains an unknown column')
      const normalizedCells = Object.fromEntries(Object.entries(cells).map(([key, cell]) => [key, resultScalar(cell, `result row.cells.${key}`)]))
      return { rowId: resultIdentifier(row.row_id, 'result row.row_id'), cells: normalizedCells, ...(row.element_ref == null ? {} : { elementRef: parseResultElementRef(row.element_ref, 'result row.element_ref') }) }
    })
    if (new Set(rows.map((row) => row.rowId)).size !== rows.length) throw new ThreadProtocolError('result projection table rows contain duplicates')
    return { tableId: resultIdentifier(item.table_id, 'result table.table_id'), title: resultText(item.title, 'result table.title'), columns, rows }
  })
  if (new Set(tables.map((table) => table.tableId)).size !== tables.length) throw new ThreadProtocolError('result projection tables contain duplicates')
  if (!Array.isArray(document.element_refs) || document.element_refs.length > maxResultElements) throw new ThreadProtocolError('result projection.element_refs is invalid')
  const elementRefs = document.element_refs.map((entry, index) => parseResultElementRef(entry, `result projection.element_refs[${index}]`))
  if (new Set(elementRefs.map((entry) => `${entry.elementKind}:${entry.elementId}`)).size !== elementRefs.length) throw new ThreadProtocolError('result projection element_refs contain duplicates')
  let overlay: ResultOverlay | undefined
  if (document.overlay != null) {
    const raw = object(document.overlay, 'result projection.overlay')
    fields(raw, new Set(['metric', 'unit', 'source_ref', 'values']), 'result projection.overlay')
    required(raw, ['metric', 'unit', 'source_ref', 'values'], 'result projection.overlay')
    if (!Array.isArray(raw.values) || raw.values.length > maxResultOverlayValues) throw new ThreadProtocolError('result projection.overlay.values is invalid')
    const values = raw.values.map((entry, index) => {
      const item = object(entry, `result projection.overlay.values[${index}]`)
      fields(item, new Set(['element_id', 'value']), `result projection.overlay.values[${index}]`)
      required(item, ['element_id', 'value'], `result projection.overlay.values[${index}]`)
      if (typeof item.value !== 'number' || !Number.isFinite(item.value)) throw new ThreadProtocolError('result projection.overlay value is invalid')
      return { elementId: resultIdentifier(item.element_id, 'result overlay element_id'), value: item.value }
    })
    if (new Set(values.map((entry) => entry.elementId)).size !== values.length) throw new ThreadProtocolError('result projection.overlay values contain duplicates')
    overlay = { metric: resultIdentifier(raw.metric, 'result overlay.metric'), unit: resultText(raw.unit, 'result overlay.unit'), sourceRef: resultRef(raw.source_ref, 'result overlay.source_ref', 'result'), values }
  }
  const reason = document.unavailable_reason == null ? undefined : resultText(document.unavailable_reason, 'result projection.unavailable_reason')
  if (status === 'unavailable' && (!reason || summary.length || tables.length || elementRefs.length || overlay)) throw new ThreadProtocolError('unavailable result projection is inconsistent')
  if (status !== 'unavailable' && reason) throw new ThreadProtocolError('available result projection cannot have an unavailable reason')
  return {
    resultId: resultIdentifier(document.result_id, 'result projection.result_id'), resultRef: resultReference, evidenceRefs,
    threadId: identifier(document.thread_id, 'result projection.thread_id'), runId: identifier(document.run_id, 'result projection.run_id'),
    turnId: identifier(document.turn_id, 'result projection.turn_id'), attemptId: identifier(document.attempt_id, 'result projection.attempt_id'),
    modelContextId: identifier(document.model_context_id, 'result projection.model_context_id'), modelId: identifier(document.model_id, 'result projection.model_id'),
    modelRevision: resultRef(document.model_revision, 'result projection.model_revision', 'revision'),
    source: { capabilityId: resultIdentifier(source.capability_id, 'result source.capability_id'), domainPackId: resultIdentifier(source.domain_pack_id, 'result source.domain_pack_id'), implementationFamily: resultIdentifier(source.implementation_family, 'result source.implementation_family') },
    status, summary, tables, elementRefs, ...(overlay ? { overlay } : {}), ...(reason ? { unavailableReason: reason } : {}),
  }
}

export { parseResultProjection }

function optionalIdentifier(value: unknown, name: string): string | undefined {
  return value === undefined || value === null ? undefined : identifier(value, name)
}

function parseCaseExecution(value: unknown): CaseExecutionSnapshot {
  const document = object(value, 'application_state.case_execution')
  const keys = ['display_name', 'status', 'completed_steps', 'total_steps', 'current_step', 'steps', 'actions', 'disabled_reasons']
  fields(document, new Set(keys), 'application_state.case_execution')
  required(document, keys, 'application_state.case_execution')
  const status = text(document.status, 'application_state.case_execution.status') as CaseExecutionSnapshot['status']
  if (!caseStatuses.has(status)) throw new ThreadProtocolError('application_state.case_execution.status is invalid')
  const total = document.total_steps; const completed = document.completed_steps
  if (!Number.isSafeInteger(total) || (total as number) < 1 || (total as number) > 32 || !Number.isSafeInteger(completed) || (completed as number) < 0 || (completed as number) > (total as number)) throw new ThreadProtocolError('application_state.case_execution step counts are invalid')
  const current = document.current_step
  if (current !== null && (!Number.isSafeInteger(current) || (current as number) < 1 || (current as number) > (total as number))) throw new ThreadProtocolError('application_state.case_execution.current_step is invalid')
  if (!Array.isArray(document.steps) || document.steps.length !== total || !Array.isArray(document.actions) || document.actions.length > maxCaseActions || !Array.isArray(document.disabled_reasons) || document.disabled_reasons.length > maxCaseReasons) throw new ThreadProtocolError('application_state.case_execution arrays are invalid')
  const steps = document.steps.map((entry, index) => {
    const item = object(entry, `application_state.case_execution.steps[${index}]`)
    fields(item, new Set(['ordinal', 'title', 'status', 'duration_ms', 'details']), `application_state.case_execution.steps[${index}]`)
    required(item, ['ordinal', 'title', 'status', 'duration_ms', 'details'], `application_state.case_execution.steps[${index}]`)
    if (item.ordinal !== index + 1 || !Number.isSafeInteger(item.ordinal)) throw new ThreadProtocolError('application_state.case_execution step ordinal is invalid')
    const stepStatus = text(item.status, 'case step.status') as CaseStepSnapshot['status']
    if (!caseStepStatuses.has(stepStatus)) throw new ThreadProtocolError('case step.status is invalid')
    if (item.duration_ms !== null && (!Number.isSafeInteger(item.duration_ms) || (item.duration_ms as number) < 0 || (item.duration_ms as number) > maxCaseDurationMs)) throw new ThreadProtocolError('case step.duration_ms is invalid')
    const details = object(item.details, 'case step.details'); jsonValue(details, 'case step.details')
    if (jsonBytes(details, 'case step.details') > maxCaseDetailsBytes) throw new ThreadProtocolError('case step.details is too large')
    return { ordinal: item.ordinal as number, title: caseText(item.title, 'case step.title'), status: stepStatus, durationMs: item.duration_ms as number | null, details }
  })
  const actions = document.actions.map((entry, index) => {
    const item = object(entry, `application_state.case_execution.actions[${index}]`)
    fields(item, new Set(['action_id', 'label', 'enabled']), `application_state.case_execution.actions[${index}]`)
    required(item, ['action_id', 'label', 'enabled'], `application_state.case_execution.actions[${index}]`)
    const actionId = identifier(item.action_id, 'case action.action_id') as CaseActionSnapshot['actionId']
    if (!caseActionIds.has(actionId) || typeof item.enabled !== 'boolean') throw new ThreadProtocolError('case action is invalid')
    return { actionId, label: caseText(item.label, 'case action.label'), enabled: item.enabled }
  })
  if (new Set(actions.map((action) => action.actionId)).size !== actions.length) throw new ThreadProtocolError('case actions contain duplicates')
  const expectedActions = caseActionMatrix[status]
  if (actions.map((action) => action.actionId).join('|') !== expectedActions.join('|') || actions.some((action) => !action.enabled)) throw new ThreadProtocolError('application_state.case_execution.actions do not match status')
  const disabledReasons = document.disabled_reasons.map((reason, index) => caseText(reason, `case disabled_reasons[${index}]`))
  if (['idle', 'created', 'running', 'waiting_step', 'completed'].includes(status) && disabledReasons.length) throw new ThreadProtocolError('application_state.case_execution.disabled_reasons do not match status')
  if (status === 'cancelled' && disabledReasons.length && (disabledReasons.length !== 1 || disabledReasons[0] !== '案例已停止')) throw new ThreadProtocolError('application_state.case_execution.disabled_reasons do not match status')
  if (status === 'blocked' && !disabledReasons.length) throw new ThreadProtocolError('application_state.case_execution.disabled_reasons do not match status')
  return { displayName: caseText(document.display_name, 'application_state.case_execution.display_name'), status, completedSteps: completed as number, totalSteps: total as number, currentStep: current as number | null, steps, actions, disabledReasons }
}

export function parseCaseExecutionSnapshot(value: unknown): CaseExecutionSnapshot {
  return parseCaseExecution(value)
}

function parseEnabledProfiles(value: unknown): Array<{ profileId: string; profileVersion: string }> {
  if (value === undefined) return []
  const document = object(value, 'active_model_context.enabled_profiles')
  fields(document, new Set(['schema', 'enabled_profiles']), 'active_model_context.enabled_profiles')
  required(document, ['schema', 'enabled_profiles'], 'active_model_context.enabled_profiles')
  if (document.schema !== 'capstone-model-capability-selection/1' || !Array.isArray(document.enabled_profiles)) {
    throw new ThreadProtocolError('active_model_context.enabled_profiles is invalid')
  }
  return document.enabled_profiles.map((entry, index) => {
    const item = object(entry, `active_model_context.enabled_profiles[${index}]`)
    fields(item, new Set(['profile_id', 'profile_version']), `active_model_context.enabled_profiles[${index}]`)
    required(item, ['profile_id', 'profile_version'], `active_model_context.enabled_profiles[${index}]`)
    return {
      profileId: identifier(item.profile_id, `active_model_context.enabled_profiles[${index}].profile_id`),
      profileVersion: text(item.profile_version, `active_model_context.enabled_profiles[${index}].profile_version`),
    }
  })
}

function parseRun(value: unknown): RunSnapshot {
  const document = object(value, 'run')
  fields(document, new Set(['run_id', 'state']), 'run')
  required(document, ['run_id', 'state'], 'run')
  const state = text(document.state, 'run.state') as RunState
  if (!runStates.has(state)) throw new ThreadProtocolError('run.state is invalid')
  return { runId: identifier(document.run_id, 'run.run_id'), state }
}

function parseContext(value: unknown, name = 'active_model_context'): ModelContextSnapshot {
  const document = object(value, name)
  const keys = ['id', 'model_id', 'model_revision', 'implementation_family', 'selection_revision', 'enabled_profiles']
  fields(document, new Set(keys), name)
  required(document, keys.filter((key) => key !== 'enabled_profiles'), name)
  return {
    id: identifier(document.id, `${name}.id`),
    modelId: identifier(document.model_id, `${name}.model_id`),
    modelRevision: text(document.model_revision, `${name}.model_revision`),
    implementationFamily: identifier(document.implementation_family, `${name}.implementation_family`),
    selectionRevision: text(document.selection_revision, `${name}.selection_revision`),
    enabledProfiles: parseEnabledProfiles(document.enabled_profiles),
  }
}

function parsePendingSelection(value: unknown): PendingSelectionSnapshot {
  const document = object(value, 'pending_selection')
  fields(document, new Set(['command_id', 'selection']), 'pending_selection')
  required(document, ['command_id', 'selection'], 'pending_selection')
  return { commandId: identifier(document.command_id, 'pending_selection.command_id'), enabledProfiles: parseEnabledProfiles(document.selection) }
}

function parsePendingModelSwitch(value: unknown): PendingModelSwitchSnapshot {
  const document = object(value, 'pending_model_switch')
  fields(document, new Set(['command_id', 'model_id', 'model_revision', 'implementation_family', 'selection']), 'pending_model_switch')
  required(document, ['command_id', 'model_id', 'model_revision', 'implementation_family', 'selection'], 'pending_model_switch')
  return {
    commandId: identifier(document.command_id, 'pending_model_switch.command_id'),
    modelId: identifier(document.model_id, 'pending_model_switch.model_id'),
    modelRevision: text(document.model_revision, 'pending_model_switch.model_revision'),
    implementationFamily: identifier(document.implementation_family, 'pending_model_switch.implementation_family'),
    enabledProfiles: parseEnabledProfiles(document.selection),
  }
}

function parseAttempt(value: unknown): AttemptSnapshot {
  const document = object(value, 'current_attempt')
  const keys = ['turn_id', 'attempt_id', 'phase', 'target_model_context_id']
  fields(document, new Set(keys), 'current_attempt')
  required(document, keys, 'current_attempt')
  const phase = text(document.phase, 'current_attempt.phase') as AttemptPhase
  if (!attemptPhases.has(phase)) throw new ThreadProtocolError('current_attempt.phase is invalid')
  return {
    turnId: identifier(document.turn_id, 'current_attempt.turn_id'),
    attemptId: identifier(document.attempt_id, 'current_attempt.attempt_id'),
    phase,
    targetModelContextId: identifier(document.target_model_context_id, 'current_attempt.target_model_context_id'),
  }
}

function snapshotDocument(snapshot: Omit<ThreadSnapshot, 'toDocument'>): Record<string, unknown> {
  return {
    schema: 'capstone-thread-snapshot/1',
    thread_id: snapshot.threadId,
    run: { run_id: snapshot.run.runId, state: snapshot.run.state },
    active_model_context: {
      id: snapshot.activeModelContext.id,
      model_id: snapshot.activeModelContext.modelId,
      model_revision: snapshot.activeModelContext.modelRevision,
      implementation_family: snapshot.activeModelContext.implementationFamily,
      selection_revision: snapshot.activeModelContext.selectionRevision,
      ...(snapshot.activeModelContext.enabledProfiles.length ? {
        enabled_profiles: {
          schema: 'capstone-model-capability-selection/1',
          enabled_profiles: snapshot.activeModelContext.enabledProfiles.map((profile) => ({
            profile_id: profile.profileId, profile_version: profile.profileVersion,
          })),
        },
      } : {}),
    },
    active_grid_page_id: snapshot.activeGridPageId,
    current_attempt: snapshot.currentAttempt ? {
      turn_id: snapshot.currentAttempt.turnId,
      attempt_id: snapshot.currentAttempt.attemptId,
      phase: snapshot.currentAttempt.phase,
      target_model_context_id: snapshot.currentAttempt.targetModelContextId,
    } : null,
    last_event_seq: snapshot.lastEventSeq,
    base_event_seq: snapshot.baseEventSeq,
    ...(snapshot.resultProjections ? { result_projections: snapshot.resultProjections.map(resultProjectionDocument) } : {}),
    ...(snapshot.applicationState ? { application_state: {
      ...(snapshot.applicationState.caseExecution ? { case_execution: {
        display_name: snapshot.applicationState.caseExecution.displayName,
        status: snapshot.applicationState.caseExecution.status,
        completed_steps: snapshot.applicationState.caseExecution.completedSteps,
        total_steps: snapshot.applicationState.caseExecution.totalSteps,
        current_step: snapshot.applicationState.caseExecution.currentStep,
        steps: snapshot.applicationState.caseExecution.steps.map((step) => ({ ordinal: step.ordinal, title: step.title, status: step.status, duration_ms: step.durationMs, details: step.details })),
        actions: snapshot.applicationState.caseExecution.actions.map((action) => ({ action_id: action.actionId, label: action.label, enabled: action.enabled })),
        disabled_reasons: snapshot.applicationState.caseExecution.disabledReasons,
      } } : {}),
    } } : {}),
    ...(snapshot.pendingSelection ? { pending_selection: {
      command_id: snapshot.pendingSelection.commandId,
      selection: { schema: 'capstone-model-capability-selection/1', enabled_profiles: snapshot.pendingSelection.enabledProfiles.map((profile) => ({ profile_id: profile.profileId, profile_version: profile.profileVersion })) },
    } } : {}),
    ...(snapshot.pendingModelSwitch ? { pending_model_switch: {
      command_id: snapshot.pendingModelSwitch.commandId,
      model_id: snapshot.pendingModelSwitch.modelId,
      model_revision: snapshot.pendingModelSwitch.modelRevision,
      implementation_family: snapshot.pendingModelSwitch.implementationFamily,
      selection: { schema: 'capstone-model-capability-selection/1', enabled_profiles: snapshot.pendingModelSwitch.enabledProfiles.map((profile) => ({ profile_id: profile.profileId, profile_version: profile.profileVersion })) },
    } } : {}),
  }
}

export function parseThreadSnapshot(value: unknown): ThreadSnapshot {
  const document = object(value, 'snapshot')
  const keys = ['schema', 'thread_id', 'run', 'active_model_context', 'active_grid_page_id', 'current_attempt', 'last_event_seq', 'base_event_seq', 'pending_selection', 'pending_model_switch', 'result_projections', 'application_state']
  fields(document, new Set(keys), 'snapshot')
  required(document, keys.filter((key) => !['pending_selection', 'pending_model_switch', 'result_projections', 'application_state'].includes(key)), 'snapshot')
  if (document.schema !== 'capstone-thread-snapshot/1') throw new ThreadProtocolError('snapshot.schema is invalid')
  const lastEventSeq = sequence(document.last_event_seq, 'snapshot.last_event_seq')
  const baseEventSeq = sequence(document.base_event_seq, 'snapshot.base_event_seq')
  if (baseEventSeq > lastEventSeq) throw new ThreadProtocolError('snapshot base_event_seq exceeds last_event_seq')
  const activeModelContext = parseContext(document.active_model_context)
  const currentAttempt = document.current_attempt === null ? null : parseAttempt(document.current_attempt)
  if (currentAttempt && currentAttempt.targetModelContextId !== activeModelContext.id) {
    throw new ThreadProtocolError('current_attempt target context does not match active context')
  }
  let applicationState: ThreadSnapshot['applicationState'] | undefined
  if (document.application_state !== undefined && document.application_state !== null) {
    const app = object(document.application_state, 'snapshot.application_state')
    if (jsonBytes(app, 'snapshot.application_state') > maxApplicationStateBytes) throw new ThreadProtocolError('snapshot.application_state is too large')
    fields(app, new Set(['case_execution']), 'snapshot.application_state')
    required(app, ['case_execution'], 'snapshot.application_state')
    applicationState = { caseExecution: parseCaseExecution(app.case_execution) }
  }
  const resultProjections = document.result_projections === undefined ? undefined : (() => {
    if (!Array.isArray(document.result_projections) || document.result_projections.length > maxResultTables) throw new ThreadProtocolError('snapshot.result_projections is invalid')
    return document.result_projections.map(parseResultProjection)
  })()
  const snapshot = {
    threadId: identifier(document.thread_id, 'snapshot.thread_id'),
    run: parseRun(document.run),
    activeModelContext,
    activeGridPageId: identifier(document.active_grid_page_id, 'snapshot.active_grid_page_id'),
    currentAttempt,
    lastEventSeq,
    baseEventSeq,
    ...(resultProjections ? { resultProjections } : {}),
    ...(applicationState ? { applicationState } : {}),
    ...(document.pending_selection == null ? {} : { pendingSelection: parsePendingSelection(document.pending_selection) }),
    ...(document.pending_model_switch == null ? {} : { pendingModelSwitch: parsePendingModelSwitch(document.pending_model_switch) }),
  }
  return { ...snapshot, toDocument: () => snapshotDocument(snapshot) }
}

function resultProjectionDocument(projection: ResultProjection): Record<string, unknown> {
  return {
    schema: 'capstone-result-projection/1.0', result_id: projection.resultId,
    ...(projection.resultRef ? { result_ref: projection.resultRef } : { result_ref: null }),
    evidence_refs: projection.evidenceRefs, thread_id: projection.threadId, run_id: projection.runId,
    turn_id: projection.turnId, attempt_id: projection.attemptId, model_context_id: projection.modelContextId,
    model_id: projection.modelId, model_revision: projection.modelRevision,
    source: { capability_id: projection.source.capabilityId, domain_pack_id: projection.source.domainPackId, implementation_family: projection.source.implementationFamily },
    status: projection.status,
    summary: projection.summary.map((item) => ({ metric_id: item.metricId, label: item.label, value: item.value, ...(item.unit ? { unit: item.unit } : {}), ...(item.severity ? { severity: item.severity } : {}) })),
    tables: projection.tables.map((table) => ({
      table_id: table.tableId, title: table.title,
      columns: table.columns.map((column) => ({ column_id: column.columnId, label: column.label, ...(column.unit ? { unit: column.unit } : {}) })),
      rows: table.rows.map((row) => ({ row_id: row.rowId, cells: row.cells, ...(row.elementRef ? { element_ref: { element_kind: row.elementRef.elementKind, element_id: row.elementRef.elementId } } : {}) })),
    })),
    element_refs: projection.elementRefs.map((entry) => ({ element_kind: entry.elementKind, element_id: entry.elementId })),
    overlay: projection.overlay ? { metric: projection.overlay.metric, unit: projection.overlay.unit, source_ref: projection.overlay.sourceRef, values: projection.overlay.values.map((entry) => ({ element_id: entry.elementId, value: entry.value })) } : null,
    ...(projection.unavailableReason ? { unavailable_reason: projection.unavailableReason } : {}),
  }
}

export function parseEventEnvelope(value: unknown): EventEnvelope {
  const document = object(value, 'event')
  const keys = ['event_id', 'event_seq', 'event_type', 'event_version', 'thread_id', 'run_id', 'turn_id', 'attempt_id', 'model_context_id', 'selection_revision', 'occurred_at', 'visibility', 'payload']
  fields(document, new Set(keys), 'event')
  required(document, ['event_id', 'event_seq', 'event_type', 'event_version', 'thread_id', 'run_id', 'occurred_at', 'visibility', 'payload'], 'event')
  if (!Number.isSafeInteger(document.event_version) || (document.event_version as number) < 1) throw new ThreadProtocolError('event.event_version is invalid')
  if (document.visibility !== 'public' && document.visibility !== 'diagnostic') throw new ThreadProtocolError('event.visibility is invalid')
  const payload = object(document.payload, 'event.payload')
  jsonValue(payload, 'event.payload')
  return {
    eventId: identifier(document.event_id, 'event.event_id'), eventSeq: sequence(document.event_seq, 'event.event_seq'),
    eventType: text(document.event_type, 'event.event_type'), eventVersion: document.event_version as number,
    threadId: identifier(document.thread_id, 'event.thread_id'), runId: identifier(document.run_id, 'event.run_id'),
    turnId: optionalIdentifier(document.turn_id, 'event.turn_id'), attemptId: optionalIdentifier(document.attempt_id, 'event.attempt_id'),
    modelContextId: optionalIdentifier(document.model_context_id, 'event.model_context_id'),
    selectionRevision: document.selection_revision == null ? undefined : text(document.selection_revision, 'event.selection_revision'),
    occurredAt: timestamp(document.occurred_at, 'event.occurred_at'), visibility: document.visibility,
    payload,
  }
}

export function parseEventPage(value: unknown, expectedAfterSeq?: number): EventPage {
  const document = object(value, 'event_page')
  const keys = ['schema', 'thread_id', 'after_event_seq', 'next_event_seq', 'has_more', 'events']
  fields(document, new Set(keys), 'event_page')
  required(document, keys, 'event_page')
  if (document.schema !== 'capstone-thread-events/1') throw new ThreadProtocolError('event_page.schema is invalid')
  const afterEventSeq = sequence(document.after_event_seq, 'event_page.after_event_seq')
  if (expectedAfterSeq !== undefined && afterEventSeq !== expectedAfterSeq) throw new ThreadProtocolError('event page does not start at expected cursor')
  if (typeof document.has_more !== 'boolean' || !Array.isArray(document.events)) throw new ThreadProtocolError('event_page pagination is invalid')
  const threadId = identifier(document.thread_id, 'event_page.thread_id')
  const events = document.events.map(parseEventEnvelope)
  let expectedSeq = afterEventSeq + 1
  for (const event of events) {
    if (event.threadId !== threadId) throw new ThreadProtocolError('event thread_id does not match page')
    if (event.eventSeq !== expectedSeq) throw new ThreadProtocolError('event page is not contiguous')
    expectedSeq += 1
  }
  const nextEventSeq = sequence(document.next_event_seq, 'event_page.next_event_seq')
  if (nextEventSeq !== expectedSeq - 1) throw new ThreadProtocolError('event_page.next_event_seq is invalid')
  const page = { threadId, afterEventSeq, nextEventSeq, hasMore: document.has_more, events }
  return { ...page, toDocument: () => ({
    schema: 'capstone-thread-events/1', thread_id: page.threadId,
    after_event_seq: page.afterEventSeq, next_event_seq: page.nextEventSeq,
    has_more: page.hasMore, events: page.events.map((event) => ({
      event_id: event.eventId, event_seq: event.eventSeq, event_type: event.eventType,
      event_version: event.eventVersion, thread_id: event.threadId, run_id: event.runId,
      ...(event.turnId ? { turn_id: event.turnId } : {}), ...(event.attemptId ? { attempt_id: event.attemptId } : {}),
      ...(event.modelContextId ? { model_context_id: event.modelContextId } : {}),
      ...(event.selectionRevision ? { selection_revision: event.selectionRevision } : {}),
      occurred_at: event.occurredAt, visibility: event.visibility, payload: event.payload,
    })),
  }) }
}

export function parseCommandReceipt(value: unknown): CommandReceipt {
  const document = object(value, 'receipt')
  const keys = ['schema', 'command_id', 'idempotency_key', 'thread_id', 'run_id', 'status', 'accepted_event_seq', 'rejection', 'target']
  fields(document, new Set(keys), 'receipt')
  required(document, ['schema', 'command_id', 'idempotency_key', 'thread_id', 'status'], 'receipt')
  if (document.schema !== 'capstone-command-receipt/1') throw new ThreadProtocolError('receipt.schema is invalid')
  if (document.status !== 'accepted' && document.status !== 'rejected' && document.status !== 'pending') throw new ThreadProtocolError('receipt.status is invalid')
  if (document.target !== undefined && document.target !== null) jsonValue(object(document.target, 'receipt.target'), 'receipt.target')
  const receipt = {
    commandId: identifier(document.command_id, 'receipt.command_id'), idempotencyKey: identifier(document.idempotency_key, 'receipt.idempotency_key'),
    threadId: identifier(document.thread_id, 'receipt.thread_id'), runId: optionalIdentifier(document.run_id, 'receipt.run_id'),
    status: document.status, acceptedEventSeq: document.accepted_event_seq == null ? undefined : sequence(document.accepted_event_seq, 'receipt.accepted_event_seq'),
    rejection: document.rejection == null ? undefined : text(document.rejection, 'receipt.rejection'),
    target: document.target == null ? undefined : object(document.target, 'receipt.target'),
  } as CommandReceipt
  return { ...receipt, toDocument: () => ({
    schema: 'capstone-command-receipt/1', command_id: receipt.commandId,
    idempotency_key: receipt.idempotencyKey, thread_id: receipt.threadId,
    ...(receipt.runId ? { run_id: receipt.runId } : {}), status: receipt.status,
    ...(receipt.acceptedEventSeq !== undefined ? { accepted_event_seq: receipt.acceptedEventSeq } : {}),
    ...(receipt.rejection ? { rejection: receipt.rejection } : {}), ...(receipt.target ? { target: receipt.target } : {}),
  }) }
}
