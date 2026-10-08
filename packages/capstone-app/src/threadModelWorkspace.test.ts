import { describe, expect, it } from 'vitest'
import { CapstoneThreadClient } from './threadClient'
import { parseModelWorkspace, parseModelControl } from './threadModelWorkspace'

const model = { entry_id: 'mdl_first', model_id: 'ieee39', model_revision: '7', implementation_family: 'pandapower',
  authority_model_ref: 'gridctl:ieee39', display_name: 'IEEE-39', diagram_provider_id: 'gridctl', last_active_seq: 0 }
export const workspace = { schema: 'capstone-thread-model-workspace/1', thread_id: 'thr_demo', run_id: 'run_demo',
  event_seq: 0, current_entry_id: 'mdl_first', models: [model], blocked_reason: null }

describe('opened model projection', () => {
  it('recognizes opened-model controls without a space and separates explicit follow-up tasks', () => {
    expect(parseModelControl('切换至已打开的 IEEE-39 电网模型')).toEqual({ kind: 'activate_model', reference: 'IEEE-39 电网模型', openedOnly: true })
    expect(parseModelControl('打开case57，然后运行潮流')).toEqual({ kind: 'open_model', reference: 'case57', openedOnly: false, task: '运行潮流' })
    expect(parseModelControl('关闭 case57 电网模型')).toMatchObject({ kind: 'close_model', reference: 'case57 电网模型' })
    expect(parseModelControl('为什么不能切换至 IEEE-39')).toBeNull()
  })
  it('parses membership separately from the execution snapshot', () => {
    const result = parseModelWorkspace(workspace, 'thr_demo')
    expect(result.currentEntryId).toBe('mdl_first')
    expect(result.models[0].displayName).toBe('IEEE-39')
  })
  it('rejects an empty collection, dangling current pointer and foreign Thread', () => {
    expect(() => parseModelWorkspace({ ...workspace, models: [] }, 'thr_demo')).toThrow()
    expect(() => parseModelWorkspace({ ...workspace, current_entry_id: 'mdl_missing' }, 'thr_demo')).toThrow()
    expect(() => parseModelWorkspace(workspace, 'thr_other')).toThrow()
  })
  it('rejects duplicate entries and unbounded membership', () => {
    expect(() => parseModelWorkspace({ ...workspace, models: [model, model] }, 'thr_demo')).toThrow()
    expect(() => parseModelWorkspace({ ...workspace, models: Array.from({ length: 65 }, (_, index) => ({ ...model, entry_id: `mdl_${index}` })) }, 'thr_demo')).toThrow()
  })
  it('loads server membership through its own resource', async () => {
    const client = new CapstoneThreadClient({ getSnapshot: async () => ({}), readEvents: async () => ({}), sendCommand: async () => ({}),
      getModels: async () => workspace })
    expect((await client.models('thr_demo'))?.currentEntryId).toBe('mdl_first')
  })
  it('rejects unknown fields, duplicate model versions and future activation cursors', () => {
    expect(() => parseModelWorkspace({ ...workspace, model: 'unbounded' }, 'thr_demo')).toThrow()
    expect(() => parseModelWorkspace({ ...workspace, models: [model, { ...model, entry_id: 'mdl_other' }] }, 'thr_demo')).toThrow()
    expect(() => parseModelWorkspace({ ...workspace, models: [{ ...model, last_active_seq: 10 }] }, 'thr_demo')).toThrow()
  })
})
