import {afterEach} from 'vitest'
afterEach(()=>initializeApplicationCapacity())
import {initializeApplicationCapacity} from './applicationCapacity'
import { describe, expect, it } from 'vitest'
import { parseWorkSnapshot, buildWorkCommand, buildStartWorkCommand, buildSendMessageCommand, parseStoredWorkCommand } from './threadWorkProtocol'
import {parseProductRef} from './threadProducts'
import {buildModelWorkspaceCommand, buildTaskDecisionCommand} from './threadWorkProtocol'

export function workSnapshot() {
  return { schema: 'capstone-thread-snapshot/2', thread_id: 'thr_work',
    run: { run_id: 'run_work', state: 'open' }, active_model_context: null,
    active_grid_page_id: null, current_attempt: null, last_event_seq: 0, base_event_seq: 0,
    minimum_protocol_version: 2, selected_model_context_id: null, task_context: null, works: [] }
}

describe('Work protocol', () => {
  it('preserves the exact task revision when a decision request is replayed', () => {
    const command = buildTaskDecisionCommand('thr_work', 'run_work', 'cmd_accept', 'idem_accept',
      'work_one', 4, 'attempt_one', 'accept')
    expect(parseStoredWorkCommand(command, 'thr_work')).toEqual(command)
    expect(() => parseStoredWorkCommand({...command, payload: {decision: 'accept'}}, 'thr_work')).toThrow()
  })
  it('recovers queued instruction and withdrawal commands with their original retry identity', () => {
    for (const [kind,payload] of [['queue_instruction',{text:'请先检查来源'}],['withdraw_instruction',{instruction_id:'ins_one'}]] as const) {
      const command={schema:'capstone-command/2',thread_id:'thr_work',run_id:'run_work',command_id:'cmd_queue',idempotency_key:'idem_queue',kind,target:{kind:'work',id:'work_one',expected_revision:2},payload}
      expect(parseStoredWorkCommand(command,'thr_work')).toEqual(command)
      expect(()=>parseStoredWorkCommand({...command,payload:{...payload,unexpected:true}},'thr_work')).toThrow()
    }
  })
  it('recovers the frozen LLM profile on a pending command',()=>{
    const submission={input:{kind:'text' as const,text:'分析'},context_selection:{include_refs:[],exclude_refs:[]},llm_profile_id:'selected-profile'}
    const command=buildSendMessageCommand('thr_work','run_work','cmd_send','idem_send','new',0,'分析',submission)
    expect(parseStoredWorkCommand(JSON.parse(JSON.stringify(command)),'thr_work')).toEqual(command)
    expect(()=>buildSendMessageCommand('thr_work','run_work','cmd_send','idem_send','new',0,'分析',{...submission,llm_profile_id:'https://caller'})).toThrow()
  })
  it.each([false,true])('retains the exact DR choice through pending command recovery: %s',deep_research=>{
    const submission={input:{kind:'text' as const,text:'分析'},context_selection:{include_refs:[],exclude_refs:[]},deep_research}
    const command=buildSendMessageCommand('thr_work','run_work','cmd_send','idem_send','new',0,'分析',submission)
    expect(parseStoredWorkCommand(JSON.parse(JSON.stringify(command)),'thr_work')).toEqual(command)
  })
  it('roundtrips version 2 model controls with workspace CAS and rejects a mismatched target', () => {
    for (const kind of ['open_model','activate_model','close_model'] as const) {
      const command=buildModelWorkspaceCommand('thr_work','run_work','cmd_model','idem_model',12,kind,
        kind==='open_model'?{model_id:'ieee39'}:{entry_id:'mdl_one'})
      expect(command.target).toEqual({kind:'model_workspace',id:'thr_work',expected_revision:12})
      expect(parseStoredWorkCommand(command,'thr_work')).toEqual(command)
      expect(()=>parseStoredWorkCommand({...command,target:{...command.target,id:'thr_other'}},'thr_work')).toThrow()
    }
  })
  it('roundtrips atomic typed native input without discarding selected resources', () => {
    const submission = { input: {kind: 'skill_invocation' as const, text: '继续', skill_id: 'summary', skill_version: '1'},
      resource_profile: {profile_id: 'delegated_pi' as const, revision: 'rev1'},
      context_selection: {include_refs: [], exclude_refs: []},context_product_refs:[{purpose:'historical-context' as const,ref:parseProductRef({schema:'capstone-product-ref/1',thread_id:'thr_work',product_id:'native_one',origin:'native_file',scope:'instruction',event_seq:12,revision:null,digest:'a'.repeat(64),work_id:'other_work',attempt_id:'prior_attempt',producer_attempt_id:null})}] }
    const command = buildSendMessageCommand('thr_work', 'run_work', 'cmd_send', 'idem_send', 'new', 0, '继续', submission, 'attempt_source')
    expect(command.kind).toBe('send_message')
    expect(command.payload).toEqual({text: '继续', ...submission, source_attempt_id: 'attempt_source'})
    expect(parseStoredWorkCommand(JSON.parse(JSON.stringify(command)), 'thr_work')).toEqual(command)
    expect(() => buildSendMessageCommand('thr_work', 'run_work', 'cmd_send', 'idem_send', 'new', 0, 'different', submission)).toThrow()
  })
  it('reads a native running Attempt and an empty successful conversation without a model', () => {
    const snapshot = parseWorkSnapshot({...workSnapshot(), session_type: 'general-chat', runtime_mode: 'capstone',
      native_execution: {available: true, unavailable_reason: null},
      current_attempt: {turn_id: 'turn_one', attempt_id: 'attempt_one', target_model_context_id: null, phase: 'running', runtime_mode: 'capstone', work_id: 'work_one'},
      works: [{work_id: 'work_one', goal: '你好', goal_revision: 1, revision: 2, status: 'running', blocked_reason: null,
        conversation_mode: true, messages: [], latest_attempt_id: 'attempt_one',
        task_context: {binding: {thread_id: 'thr_work', work_id: 'work_one'}, goal_revision: 1, model_contexts: [], resource_refs: []}}]})
    expect(snapshot.currentAttempt?.targetModelContextId).toBeNull()
    expect(snapshot.currentAttempt?.workId).toBe('work_one')
    expect(snapshot.works[0].conversationMode).toBe(true)
    expect(snapshot.sessionType).toBe('general-chat')
    expect(snapshot.nativeExecution?.available).toBe(true)
    expect(snapshot.professionalSnapshot).toBeUndefined()
  })
  it('starts an existing Work with object CAS and no fabricated instruction payload', () => {
    const command = buildStartWorkCommand('thr_work', 'run_work', 'cmd_start', 'idem_start', 'work_one', 3)
    expect(command.kind).toBe('start_work')
    expect(command.payload).toEqual({})
    expect(command.target.expected_revision).toBe(3)
    expect(command).not.toHaveProperty('expected_event_seq')
    expect(() => buildStartWorkCommand('thr_work', 'run_work', 'cmd_start', 'idem_start', 'new', 0)).toThrow()
  })
  it('reads a model-free Thread without inventing a model', () => {
    const snapshot = parseWorkSnapshot(workSnapshot())
    expect(snapshot.threadId).toBe('thr_work')
    expect(snapshot.works).toEqual([])
    expect(snapshot.selectedModelContextId).toBeNull()
  })
  it('rejects an unsupported schema and inconsistent event cursor', () => {
    expect(() => parseWorkSnapshot({ ...workSnapshot(), schema: 'capstone-thread-snapshot/3' })).toThrow()
    expect(() => parseWorkSnapshot({ ...workSnapshot(), base_event_seq: 2 })).toThrow()
  })
  it('uses object revision rather than event sequence for a new Work', () => {
    const command = buildWorkCommand('thr_work', 'run_work', 'cmd_save', 'key_save', 'new', 0, '整理所提供的资料')
    expect(command.target).toEqual({ kind: 'work', id: 'new', expected_revision: 0 })
    expect(command).not.toHaveProperty('expected_event_seq')
    expect(command.kind).toBe('work_message')
  })
  it('limits the encoded command, including multibyte task text', () => {
    initializeApplicationCapacity({command_bytes:65536})
    expect(() => buildWorkCommand('thr_work', 'run_work', 'cmd_save', 'key_save', 'new', 0, '中'.repeat(22000))).toThrow()
  })
})
it.each(['work_message','revise_goal'] as const)('preserves row refs in recoverable professional %s commands',kind=>{
 const ref=parseProductRef({schema:'capstone-product-ref/1',thread_id:'thr_work',product_id:'result_one',origin:'domain_result',scope:'instruction',event_seq:12,revision:null,digest:'a'.repeat(64),work_id:'work_one',attempt_id:'prior_attempt',producer_attempt_id:null})
 const selection={ref,purpose:'historical-context' as const,row_selection:{schema:'capstone-result-row-selection/1' as const,parent_ref:ref,table_id:'lines',table_version:'b'.repeat(64),row_ids:['r1'],column_ids:['mw'],digest:'c'.repeat(64)}}
 const command=buildWorkCommand('thr_work','run_work','cmd_row','idem_row','work_one',1,'分析所选行',kind,[selection])
 expect(parseStoredWorkCommand(JSON.parse(JSON.stringify(command)),'thr_work')).toEqual(command)
 expect(command.payload).toEqual({text:'分析所选行',context_product_refs:[selection]})
})
