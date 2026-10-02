export type ThreadCatalogModel = {
  modelId: string
  authorityModelRef: string
  displayName: string
  diagramProviderId: string
  implementationFamily: string
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
  const keys = ['model_id', 'authority_model_ref', 'display_name', 'diagram_provider_id', 'implementation_family']
  fields(item, keys, `catalog.models[${index}]`); required(item, keys, `catalog.models[${index}]`)
  return {
    modelId: string(item.model_id, `catalog.models[${index}].model_id`, modelIdentifierPattern),
    authorityModelRef: string(item.authority_model_ref, `catalog.models[${index}].authority_model_ref`),
    displayName: string(item.display_name, `catalog.models[${index}].display_name`),
    diagramProviderId: string(item.diagram_provider_id, `catalog.models[${index}].diagram_provider_id`, identifierPattern),
    implementationFamily: string(item.implementation_family, `catalog.models[${index}].implementation_family`, identifierPattern),
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
