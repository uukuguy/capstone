import type { RuntimeMode } from './threadProtocol'

export type SkillRole = 'harness_engine' | 'direct_pi' | 'delegated_pi'
export type SkillChoice = { id: string; version: string; role: SkillRole; revision: string }
export type ContextChoice = { include_refs: string[]; exclude_refs: string[] }
export type InputDraft = { mode: RuntimeMode; skill?: SkillChoice; context: ContextChoice; literal?: boolean }
export type InputSubmission = { input: { kind: 'text' | 'skill_invocation'; text: string; skill_id?: string; skill_version?: string }; resource_profile?: { profile_id: SkillRole; revision: string }; context_selection: ContextChoice }
export type InputCatalog = {
  schema: 'capstone-thread-input-catalog/1'; revision: string; context_id: string; selection_revision: string
  objects: { object_id: string; model_id: string; model_revision: string; implementation_family: string }[]
  materials: { material_id: string; display_name: string }[]
  resource_profiles: Partial<Record<SkillRole, { revision: string; resources: { id: string; kind: string; version: string; source: string; ready: boolean; reason: string | null }[] }>>
  operations: { operation_id: string; scope: string; role: string; available: boolean; reason: string | null; revision: string }[]
}
export const emptyInputDraft = (mode: RuntimeMode): InputDraft => ({ mode, context: { include_refs: [], exclude_refs: [] } })
export function skillCompatible(skill: SkillChoice, mode: RuntimeMode) {
  return mode === 'pi_reference' ? skill.role === 'direct_pi' : skill.role === 'harness_engine' || skill.role === 'delegated_pi'
}
export function inputDraftError(draft: InputDraft, catalog?: InputCatalog): string | undefined {
  if (draft.skill && !skillCompatible(draft.skill, draft.mode)) return '所选技能与当前模式不兼容，请重新选择。'
  if (draft.skill && catalog) {
    const profile = catalog.resource_profiles[draft.skill.role]
    if (profile?.revision !== draft.skill.revision || !profile.resources.some(skill => skill.id === draft.skill!.id && skill.version === draft.skill!.version && skill.ready)) return '所选技能目录已变化，请重新选择。'
  }
  if (catalog && [...draft.context.include_refs, ...draft.context.exclude_refs].some(ref => !catalog.objects.some(object => object.object_id === ref))) return '所选上下文已变化，请重新选择。'
}
export function parseInputCommand(text: string): { kind: 'skills' | 'context'; rest: string } | { kind: 'skill' | 'unknown'; name: string; rest: string } | null {
  const skill = /^\/skill:([\w.-]+)(?:\s+([\s\S]*))?$/.exec(text)
  if (skill) return { kind: 'skill', name: skill[1], rest: skill[2] || '' }
  const match = /^\/([a-z][\w-]*)(?:\s+([\s\S]*))?$/.exec(text)
  if (!match) return null
  if (match[1] === 'skills' || match[1] === 'context') return { kind: match[1], rest: match[2] || '' }
  return { kind: 'unknown', name: match[1], rest: match[2] || '' }
}
export function buildInputSubmission(text: string, draft: InputDraft): InputSubmission {
  if (draft.skill && !skillCompatible(draft.skill, draft.mode)) throw new Error('所选技能与当前模式不兼容，请重新选择。')
  return { input: draft.skill ? { kind: 'skill_invocation', text, skill_id: draft.skill.id, skill_version: draft.skill.version } : { kind: 'text', text },
    ...(draft.skill ? { resource_profile: { profile_id: draft.skill.role, revision: draft.skill.revision } } : {}), context_selection: draft.context }
}
export function readInputDraft(key?: string): InputDraft | undefined {
  if (!key) return
  try {
    const text = sessionStorage.getItem(`${key}.input`)
    if (!text || text.length > 16384) return
    const value = JSON.parse(text)
    if (!['capstone', 'pi_reference'].includes(value.mode) || !Array.isArray(value.context?.include_refs) || !Array.isArray(value.context?.exclude_refs)) return
    if (value.skill && (!['harness_engine', 'direct_pi', 'delegated_pi'].includes(value.skill.role) || ['id', 'version', 'revision'].some(key => typeof value.skill[key] !== 'string'))) return
    return value
  } catch { return }
}
export function writeInputDraft(key: string | undefined, value: InputDraft): void {
  if (key) try { sessionStorage.setItem(`${key}.input`, JSON.stringify(value)) } catch { /* Live state remains available. */ }
}
export function parseInputCatalog(value: unknown): InputCatalog {
  const item = value as InputCatalog
  if (!item || item.schema !== 'capstone-thread-input-catalog/1' || typeof item.revision !== 'string'
      || !Array.isArray(item.objects) || item.objects.length > 16 || !Array.isArray(item.materials) || item.materials.length > 8
      || !item.resource_profiles || !Array.isArray(item.operations)) throw new Error('输入目录无效')
  for (const [role, profile] of Object.entries(item.resource_profiles)) {
    if (!['harness_engine', 'direct_pi', 'delegated_pi'].includes(role) || !profile || typeof profile.revision !== 'string'
        || !Array.isArray(profile.resources) || profile.resources.length > 128) throw new Error('资源目录无效')
  }
  return item
}
