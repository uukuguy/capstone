export type ThreadCatalogModel = {
  modelId: string
  authorityModelRef: string
  displayName: string
  diagramProviderId: string
  implementationFamily: string
  available?: boolean
  unavailableReason?: string
}

export type ThreadCatalogProfile = {
  profileId: string
  profileVersion: string
  displayName: string
  implementationFamilies: string[]
}

export type ThreadCatalogCase = {
  caseId: string
  caseVersion: string
  displayName: string
  summary: string
  modelIds: string[]
  stepCount: number
}

export type ThreadCatalog = {
  models: ThreadCatalogModel[]
  profiles: ThreadCatalogProfile[]
  cases?: ThreadCatalogCase[]
}

export type ThreadModelReferenceResolution =
  | { kind: 'resolved'; model: ThreadCatalogModel; matchedBy: 'exact' | 'suffix' | 'display_name' }
  | { kind: 'ambiguous'; reference: string; candidates: ThreadCatalogModel[] }
  | { kind: 'unknown'; reference: string }

export type ThreadModelCommandIntent = {
  action: 'switch_model' | 'reopen_model_context'
  reference: string
}

/** Keep longer analytical requests on the normal agent route. */
export function isLikelyNaturalLanguageModelRequest(reference: string): boolean {
  const value = reference.trim()
  const words = value.split(/\s+/u).filter(Boolean)
  return value.length > 48 || words.length > 5 || /(?:并|然后|执行|分析|解析|线路|潮流|母线|端点|结果|网络|network|analy[sz]|execute|perform|flow|line|bus)/iu.test(value)
}

export class ThreadCatalogProtocolError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'ThreadCatalogProtocolError'
  }
}

const identifierPattern = /^[a-z][a-z0-9_-]{0,63}$/
const modelIdentifierPattern = /^[a-z][a-z0-9_-]{0,63}(?:\/[a-z0-9][a-z0-9._-]{0,63})?$/

function record(value: unknown, name: string): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new ThreadCatalogProtocolError(`${name} must be an object`)
  return value as Record<string, unknown>
}

function fields(value: Record<string, unknown>, allowed: readonly string[], name: string): void {
  const unknown = Object.keys(value).filter((key) => !allowed.includes(key))
  if (unknown.length) throw new ThreadCatalogProtocolError(`${name} has unknown field: ${unknown.sort().join(', ')}`)
}

function required(value: Record<string, unknown>, keys: readonly string[], name: string): void {
  const missing = keys.filter((key) => !(key in value))
  if (missing.length) throw new ThreadCatalogProtocolError(`${name} is missing field: ${missing.join(', ')}`)
}

function string(value: unknown, name: string, pattern = /^.{1,256}$/): string {
  if (typeof value !== 'string' || !pattern.test(value)) throw new ThreadCatalogProtocolError(`${name} is invalid`)
  return value
}

function parseModel(value: unknown, index: number): ThreadCatalogModel {
  const item = record(value, `catalog.models[${index}]`)
  const keys = ['model_id', 'authority_model_ref', 'display_name', 'diagram_provider_id', 'implementation_family', 'available', 'unavailable_reason']
  fields(item, keys, `catalog.models[${index}]`); required(item, keys.slice(0, 5), `catalog.models[${index}]`)
  if (item.available !== undefined && typeof item.available !== 'boolean') throw new ThreadCatalogProtocolError(`catalog.models[${index}].available is invalid`)
  if (item.unavailable_reason !== undefined) string(item.unavailable_reason, `catalog.models[${index}].unavailable_reason`, identifierPattern)
  return {
    modelId: string(item.model_id, `catalog.models[${index}].model_id`, modelIdentifierPattern),
    authorityModelRef: string(item.authority_model_ref, `catalog.models[${index}].authority_model_ref`),
    displayName: string(item.display_name, `catalog.models[${index}].display_name`),
    diagramProviderId: string(item.diagram_provider_id, `catalog.models[${index}].diagram_provider_id`, identifierPattern),
    implementationFamily: string(item.implementation_family, `catalog.models[${index}].implementation_family`, identifierPattern),
    available: item.available === undefined ? true : item.available as boolean,
    ...(item.unavailable_reason === undefined ? {} : { unavailableReason: item.unavailable_reason as string }),
  }
}

function parseProfile(value: unknown, index: number): ThreadCatalogProfile {
  const item = record(value, `catalog.profiles[${index}]`)
  const keys = ['profile_id', 'profile_version', 'display_name', 'implementation_families']
  fields(item, keys, `catalog.profiles[${index}]`); required(item, keys, `catalog.profiles[${index}]`)
  if (!Array.isArray(item.implementation_families) || item.implementation_families.length > 32) throw new ThreadCatalogProtocolError(`catalog.profiles[${index}].implementation_families is invalid`)
  return {
    profileId: string(item.profile_id, `catalog.profiles[${index}].profile_id`, identifierPattern),
    profileVersion: string(item.profile_version, `catalog.profiles[${index}].profile_version`, /^[0-9]+(?:\.[0-9]+){1,3}(?:[-+][a-z0-9.-]+)?$/),
    displayName: string(item.display_name, `catalog.profiles[${index}].display_name`),
    implementationFamilies: item.implementation_families.map((family, familyIndex) => string(family, `catalog.profiles[${index}].implementation_families[${familyIndex}]`, identifierPattern)),
  }
}

function parseCase(value: unknown, index: number): ThreadCatalogCase {
  const item = record(value, `catalog.cases[${index}]`)
  const keys = ['case_id', 'case_version', 'title', 'summary', 'model_ids', 'step_count']
  fields(item, keys, `catalog.cases[${index}]`); required(item, keys, `catalog.cases[${index}]`)
  if (!Array.isArray(item.model_ids) || item.model_ids.length > 32 || !item.model_ids.every((model) => typeof model === 'string' && modelIdentifierPattern.test(model))) {
    throw new ThreadCatalogProtocolError(`catalog.cases[${index}].model_ids is invalid`)
  }
  if (!Number.isSafeInteger(item.step_count) || (item.step_count as number) < 1 || (item.step_count as number) > 32) {
    throw new ThreadCatalogProtocolError(`catalog.cases[${index}].step_count is invalid`)
  }
  return {
    caseId: string(item.case_id, `catalog.cases[${index}].case_id`, identifierPattern),
    caseVersion: string(item.case_version, `catalog.cases[${index}].case_version`),
    displayName: string(item.title, `catalog.cases[${index}].title`),
    summary: string(item.summary, `catalog.cases[${index}].summary`),
    modelIds: item.model_ids as string[],
    stepCount: item.step_count as number,
  }
}

export function parseThreadCatalog(value: unknown): ThreadCatalog {
  const document = record(value, 'catalog')
  fields(document, ['schema', 'models', 'profiles', 'cases'], 'catalog')
  required(document, ['schema', 'models', 'profiles'], 'catalog')
  if (document.schema !== 'capstone-thread-catalog/1' || !Array.isArray(document.models) || !Array.isArray(document.profiles)) throw new ThreadCatalogProtocolError('catalog schema is invalid')
  if (document.models.length > 128 || document.profiles.length > 128) throw new ThreadCatalogProtocolError('catalog is too large')
  const cases = document.cases === undefined ? undefined : (() => {
    if (!Array.isArray(document.cases) || document.cases.length > 128) throw new ThreadCatalogProtocolError('catalog.cases is invalid')
    return document.cases.map(parseCase)
  })()
  return {
    models: document.models.map(parseModel),
    profiles: document.profiles.map(parseProfile),
    ...(cases === undefined ? {} : { cases }),
  }
}

function normalizedReference(value: string): string {
  return value.trim().replace(/\s+/gu, ' ').toLocaleLowerCase()
}

/** Resolve a user-facing model reference without crossing the Authority boundary.
 *
 * Exact canonical IDs win. A short namespaced suffix is accepted only when it
 * identifies one registered model; display names follow the same rule. This
 * keeps ``model_energy`` convenient while refusing to guess between duplicate
 * names such as ``two-bus``.
 */
export function resolveThreadModelReference(catalog: ThreadCatalog, reference: string): ThreadModelReferenceResolution {
  const trimmed = reference.trim()
  if (!trimmed) return { kind: 'unknown', reference: trimmed }
  const exact = catalog.models.find((model) => model.modelId === trimmed)
  if (exact) return { kind: 'resolved', model: exact, matchedBy: 'exact' }

  const normalized = normalizedReference(trimmed)
  const caseInsensitiveExact = catalog.models.filter((model) => normalizedReference(model.modelId) === normalized)
  if (caseInsensitiveExact.length === 1) return { kind: 'resolved', model: caseInsensitiveExact[0], matchedBy: 'exact' }

  const suffixMatches = catalog.models.filter((model) => normalizedReference(model.modelId.split('/').at(-1) || model.modelId) === normalized)
  if (suffixMatches.length === 1) return { kind: 'resolved', model: suffixMatches[0], matchedBy: 'suffix' }
  if (suffixMatches.length > 1) return { kind: 'ambiguous', reference: trimmed, candidates: [...suffixMatches].sort((left, right) => left.modelId.localeCompare(right.modelId)) }

  const displayMatches = catalog.models.filter((model) => normalizedReference(model.displayName) === normalized)
  if (displayMatches.length === 1) return { kind: 'resolved', model: displayMatches[0], matchedBy: 'display_name' }
  if (displayMatches.length > 1) return { kind: 'ambiguous', reference: trimmed, candidates: [...displayMatches].sort((left, right) => left.modelId.localeCompare(right.modelId)) }
  return { kind: 'unknown', reference: trimmed }
}

/** Parse only short, unambiguous model-control phrases. Longer requests such
 * as “打开 IEEE-39 网络并解析线路” deliberately return null and remain
 * ordinary agent instructions. */
export function parseThreadModelCommand(text: string): ThreadModelCommandIntent | null {
  const value = text.trim().replace(/[。.!！?？]+$/u, '').trim()
  const fresh = value.match(/^(?:重新打开|重新载入|重建|打开一个干净的模型)\s+(.+)$/u)
  if (fresh?.[1]) return { action: 'reopen_model_context', reference: fresh[1].trim() }
  const switchMatch = value.match(/^(?:打开|切换到|切换至|使用|选择)\s+(.+)$/u)
  if (switchMatch?.[1]) return { action: 'switch_model', reference: switchMatch[1].trim() }
  return null
}
