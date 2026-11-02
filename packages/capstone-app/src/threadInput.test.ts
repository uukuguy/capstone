import { describe, expect, it } from 'vitest'
import { parseInputCommand, buildInputSubmission, readInputDraft, writeInputDraft,parseInputCatalog,inputDraftError } from './threadInput'
import {parseProductRef} from './threadProducts'

describe('typed composer input', () => {
  it('uses deployment catalog defaults and rejects missing or disabled saved profiles',()=>{
    const base={schema:'capstone-thread-input-catalog/1',revision:'r',objects:[],materials:[],resource_profiles:{},operations:[]}
    const catalog=parseInputCatalog({...base,llm_profiles:{default_profile_id:'intranet',profiles:[{id:'intranet',label:'Server default',model:'dsv4',available:true},{id:'custom',label:'Custom',model:'',available:false}]}})
    expect(catalog.llm_profiles?.default_profile_id).toBe('intranet')
    const draft={mode:'capstone' as const,context:{include_refs:[],exclude_refs:[]},llm_profile_id:'intranet'}
    expect(inputDraftError(draft,catalog)).toBeUndefined()
    expect(inputDraftError({...draft,llm_profile_id:'custom'},catalog)).toContain('不可用')
    expect(inputDraftError({...draft,llm_profile_id:'removed'},catalog)).toContain('不可用')
    expect(()=>parseInputCatalog({...base,llm_profiles:{default_profile_id:'missing',profiles:[]}})).toThrow()
    expect(()=>buildInputSubmission('text',{...draft,llm_profile_id:'https://caller'})).toThrow()
  })
  it('retains a session LLM choice across refresh and freezes the submitted ID',()=>{
    const state={mode:'capstone' as const,llm_profile_id:'internal-choice',context:{include_refs:[],exclude_refs:[]}}
    writeInputDraft('session-llm-one',state)
    expect(readInputDraft('session-llm-one')?.llm_profile_id).toBe('internal-choice')
    expect(readInputDraft('session-llm-other')?.llm_profile_id).toBeUndefined()
    const submitted=buildInputSubmission('hello',state)
    state.llm_profile_id='other-choice'
    expect(submitted.llm_profile_id).toBe('internal-choice')
  })
  it('stores and submits exact historical product versions without turning them into current evidence',()=>{
    const ref=parseProductRef({schema:'capstone-product-ref/1',thread_id:'thr_one',product_id:'delivery_one',origin:'task_delivery',scope:'task',event_seq:12,revision:2,digest:'a'.repeat(64),work_id:'old_work',attempt_id:'old_attempt',producer_attempt_id:null})
    const state={mode:'capstone' as const,context:{include_refs:[],exclude_refs:[]},context_product_refs:[{ref,purpose:'historical-context' as const}]}
    expect(buildInputSubmission('继续分析',state).context_product_refs).toEqual(state.context_product_refs)
    writeInputDraft('product-test',state)
    expect(readInputDraft('product-test')?.context_product_refs).toEqual(state.context_product_refs)
    expect(()=>buildInputSubmission('继续分析',{...state,context_product_refs:[...state.context_product_refs,...state.context_product_refs]})).toThrow()
  })
  it('retains explicit material choices while absence keeps session defaults', () => {
    const state = {mode: 'capstone' as const, context: {include_refs: [], exclude_refs: []},
      material_refs: ['material_' + 'a'.repeat(32)]}
    expect(buildInputSubmission('Read', state).material_refs).toEqual(state.material_refs)
    writeInputDraft('material-test', state)
    expect(readInputDraft('material-test')?.material_refs).toEqual(state.material_refs)
    expect(buildInputSubmission('Read', {mode: 'capstone', context: state.context})).not.toHaveProperty('material_refs')
  })
  it('parses only a leading standalone command position', () => {
    expect(parseInputCommand('/skills')).toEqual({ kind: 'skills', rest: '' })
    expect(parseInputCommand('/context task')).toEqual({ kind: 'context', rest: 'task' })
    expect(parseInputCommand('/skill:power-a explain')).toEqual({ kind: 'skill', name: 'power-a', rest: 'explain' })
    for (const text of ['/tmp/path', 'read /skills', '```\n/skills\n```', 'https://host/skills', ' /skills']) expect(parseInputCommand(text)).toBeNull()
    expect(parseInputCommand('/unknown')).toEqual({ kind: 'unknown', name: 'unknown', rest: '' })
  })
  it('retains resource identity, context choices and role through storage', () => {
    const state = { mode: 'capstone' as const, skill: { id: 'a', version: 'v1', role: 'delegated_pi' as const, revision: 'exact' },
      context: { include_refs: ['current'], exclude_refs: ['old'] }, literal: true }
    writeInputDraft('input-test', state)
    expect(readInputDraft('input-test')).toEqual(state)
    expect(buildInputSubmission(' task ', state)).toEqual({
      input: { kind: 'skill_invocation', text: ' task ', skill_id: 'a', skill_version: 'v1' },
      resource_profile: { profile_id: 'delegated_pi', revision: 'exact' }, context_selection: state.context,
    })
    expect(() => buildInputSubmission('task', { ...state, mode: 'pi_reference' })).toThrow(/重新选择/)
  })
})
