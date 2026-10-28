import {assertCapacity,exceedsCapacity,CapacityError,rethrowDebugCapacity} from './applicationCapacity'
import type { RuntimeMode } from './threadProtocol'
import {parseContextProductRefs,type ContextProductRef} from './threadProducts'
import type {StoredResource} from './resourceUploads'

export type SkillRole = 'harness_engine' | 'direct_pi' | 'delegated_pi'
export type SkillChoice = { id: string; version: string; role: SkillRole; revision: string }
export type ContextChoice = { include_refs: string[]; exclude_refs: string[] }
export type GatewayConnectionStatus={available:boolean;connection_name?:string;server_name?:string;server_version?:string;endpoint?:string;instance_id?:string;instance_name?:string;environment_label?:string;data_source_label?:string;offline?:boolean}
export type InputDraft = { mode: RuntimeMode; llm_profile_id?:string; deep_research?:boolean; skill?: SkillChoice; context: ContextChoice; literal?: boolean; material_refs?: string[];context_product_refs?:ContextProductRef[] }
export type InputSubmission = { llm_profile_id?:string; deep_research?:boolean; input: { kind: 'text' | 'skill_invocation'; text: string; skill_id?: string; skill_version?: string }; resource_profile?: { profile_id: SkillRole; revision: string }; context_selection: ContextChoice; material_refs?: string[];context_product_refs?:ContextProductRef[];attachment_refs?:string[] }
export type InputCatalog = {
  data_gateway?:GatewayConnectionStatus
  llm_profiles?:{default_profile_id:string;profiles:{id:string;label:string;model:string;available:boolean;icon?:string}[]}
  stored_resources?:StoredResource[]
  schema: 'capstone-thread-input-catalog/1'; revision: string; context_id: string; selection_revision: string
  objects: { object_id: string; model_id: string; model_revision: string; implementation_family: string }[]
  materials: { material_id: string; display_name: string; size_bytes?: number; media_type?: string; sha256?: string }[]
  resource_profiles: Partial<Record<SkillRole, { revision: string; resources: { id: string; native_name?: string | null; description?: string | null; kind: string; version: string; source: string; ready: boolean; reason: string | null }[] }>>
  operations: { operation_id: string; scope: string; role: string; available: boolean; reason: string | null; revision: string }[]
}
export const emptyInputDraft = (mode: RuntimeMode): InputDraft => ({ mode, context: { include_refs: [], exclude_refs: [] } })
export const validLlmProfileId=(value:unknown):value is string=>typeof value==='string'&&/^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}$/.test(value)
export function skillCompatible(skill: SkillChoice, mode: RuntimeMode) {
  return mode === 'pi_reference' ? skill.role === 'direct_pi' : skill.role === 'harness_engine' || skill.role === 'delegated_pi'
}
export function inputDraftError(draft: InputDraft, catalog?: InputCatalog): string | undefined {
  if(draft.llm_profile_id!==undefined){
    if(!validLlmProfileId(draft.llm_profile_id))return 'LLM 选择无效，请重新选择。'
    if(!catalog)return '正在读取 LLM 目录。'
    if(!catalog.llm_profiles?.profiles.some(profile=>profile.id===draft.llm_profile_id&&profile.available))return '所选 LLM 不可用或未配置，请重新选择。'
  }
  try{if(draft.context_product_refs!==undefined)parseContextProductRefs(draft.context_product_refs)}catch(error){rethrowDebugCapacity(error);return error instanceof CapacityError?error.message:'成果引用无效，请移除后重新选择。'}
  if (draft.material_refs !== undefined && (!validMaterialRefs(draft.material_refs) || catalog && draft.material_refs.some(ref => !catalog.materials.some(item => item.material_id === ref)))) return '所选资料已变化，请重新选择。'
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
  if(draft.llm_profile_id!==undefined&&!validLlmProfileId(draft.llm_profile_id))throw new Error('LLM 选择无效。')
  assertCapacity(text.length,'input_text_chars')
  if (draft.material_refs !== undefined && !validMaterialRefs(draft.material_refs)) throw new Error('所选资料无效。')
  if (draft.skill && !skillCompatible(draft.skill, draft.mode)) throw new Error('所选技能与当前模式不兼容，请重新选择。')
  return { input: draft.skill ? { kind: 'skill_invocation', text, skill_id: draft.skill.id, skill_version: draft.skill.version } : { kind: 'text', text },
    ...(draft.deep_research===undefined?{}:{deep_research:draft.deep_research}),
    ...(draft.llm_profile_id===undefined?{}:{llm_profile_id:draft.llm_profile_id}),
    ...(draft.skill ? { resource_profile: { profile_id: draft.skill.role, revision: draft.skill.revision } } : {}), context_selection: draft.context,
    ...(draft.material_refs === undefined ? {} : {material_refs: [...draft.material_refs]}),
    ...(draft.context_product_refs===undefined?{}:{context_product_refs:parseContextProductRefs(draft.context_product_refs)}) }
}
function validMaterialRefs(value: unknown): value is string[] {
  return Array.isArray(value) && !exceedsCapacity(value.length,'inline_material_count') && value.every(ref => typeof ref === 'string' && /^material_[a-f0-9]{32}$/.test(ref)) && new Set(value).size === value.length
}
export function readInputDraft(key?: string): InputDraft | undefined {
  if (!key) return
  try {
    const text = sessionStorage.getItem(`${key}.input`)
    if (!text) return
    assertCapacity(new TextEncoder().encode(text).byteLength,'ui_input_draft_bytes')
    const value = JSON.parse(text)
    if(value.llm_profile_id!==undefined&&!validLlmProfileId(value.llm_profile_id))return
    if(value.deep_research!==undefined&&typeof value.deep_research!=='boolean')return
    if (!['capstone', 'pi_reference'].includes(value.mode) || !Array.isArray(value.context?.include_refs) || !Array.isArray(value.context?.exclude_refs)) return
    if (value.skill && (!['harness_engine', 'direct_pi', 'delegated_pi'].includes(value.skill.role) || ['id', 'version', 'revision'].some(key => typeof value.skill[key] !== 'string'))) return
    if (value.material_refs !== undefined && !validMaterialRefs(value.material_refs)) return
    if(value.context_product_refs!==undefined)parseContextProductRefs(value.context_product_refs)
    return value
  } catch (error) { if(error instanceof CapacityError)throw error; return }
}
export function writeInputDraft(key: string | undefined, value: InputDraft): void {
  const text=JSON.stringify(value)
  assertCapacity(new TextEncoder().encode(text).byteLength,'ui_input_draft_bytes')
  if (key) try { sessionStorage.setItem(`${key}.input`, text) } catch { /* Live state remains available. */ }
}
export function parseInputCatalog(value: unknown): InputCatalog {
  const item = value as InputCatalog
  if (!item || item.schema !== 'capstone-thread-input-catalog/1' || typeof item.revision !== 'string'
      || !Array.isArray(item.objects) || exceedsCapacity(item.objects.length,'resource_profile_items') || !Array.isArray(item.materials) || exceedsCapacity(item.materials.length,'inline_material_count')
      || !item.resource_profiles || !Array.isArray(item.operations)) throw new Error('输入目录无效')
  for (const [role, profile] of Object.entries(item.resource_profiles)) {
    if (!['harness_engine', 'direct_pi', 'delegated_pi'].includes(role) || !profile || typeof profile.revision !== 'string'
        || !Array.isArray(profile.resources) || exceedsCapacity(profile.resources.length,'resource_profile_items')) throw new Error('资源目录无效')
  }
  if(item.llm_profiles!==undefined){
    const llm=item.llm_profiles
    if(!llm||!validLlmProfileId(llm.default_profile_id)||!Array.isArray(llm.profiles)||llm.profiles.length>100
      ||llm.profiles.some(profile=>!profile||!validLlmProfileId(profile.id)||typeof profile.available!=='boolean'||typeof profile.label!=='string'||!profile.label||profile.label.length>256||typeof profile.model!=='string'||profile.model.length>256)
      ||new Set(llm.profiles.map(profile=>profile.id)).size!==llm.profiles.length||!llm.profiles.some(profile=>profile.id===llm.default_profile_id))throw new Error('LLM 目录无效')
  }
  if(item.data_gateway!==undefined){
    const gateway=item.data_gateway
    if(!gateway||typeof gateway.available!=='boolean')throw new Error('数据网关连接信息无效')
    const projected:GatewayConnectionStatus={available:gateway.available}
    if(gateway.offline!==undefined){
      if(typeof gateway.offline!=='boolean')throw new Error('数据网关连接信息无效')
      projected.offline=gateway.offline
    }
    for(const field of ['connection_name','server_name','server_version','endpoint','instance_id','instance_name','environment_label','data_source_label'] as const){
      const text=gateway[field]
      if(text===undefined)continue
      if(typeof text!=='string'||text.length>2048||/[\u0000-\u001f\u007f]/.test(text))throw new Error('数据网关连接信息无效')
      if(text.trim())projected[field]=text
    }
    if(projected.endpoint){
      const address=projected.endpoint
      const bare=!address.includes('://')
      if(bare){
        const matched=/^(?:\[[0-9a-fA-F:.]+\]|[a-zA-Z0-9.-]+):([0-9]{1,5})$/.exec(address)
        if(!matched||Number(matched[1])<1||Number(matched[1])>65535)throw new Error('数据网关连接信息无效')
      }
      const url=new URL(bare?`http://${address}`:address)
      if(!['http:','https:'].includes(url.protocol)||url.username||url.password||url.search||url.hash)throw new Error('数据网关连接信息无效')
    }
    return {...item,data_gateway:projected}
  }
  return item
}
