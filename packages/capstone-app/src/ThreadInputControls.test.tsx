import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import CapstoneAssistantThread from './CapstoneAssistantThread'
import type { InputCatalog } from './threadInput'
import { MessageNotSentError } from '@assistant-ui/react'

afterEach(() => { cleanup(); sessionStorage.clear() })
function invokeSkill(){const composer=screen.getByRole('textbox',{name:'Thread 指令'});fireEvent.change(composer,{target:{value:'/skill:skill-a'}});fireEvent.keyDown(composer,{key:'Enter'});}
function openSkills(){const composer=screen.getByRole('textbox',{name:'Thread 指令'});fireEvent.change(composer,{target:{value:'/skills'}});fireEvent.keyDown(composer,{key:'Enter'});}

it('binds a unique native skill name and keeps same-name collisions in the picker', async () => {
  const skill = { id: 'powerskills-pandapower', native_name: 'pandapower', kind: 'skill', installed:true, version: 'version-A', source: 'managed', ready: true, reason: null }
  const direct = { ...catalog, resource_profiles: { direct_pi: { revision: 'accepted-A', resources: [skill] } } }
  const onSend = vi.fn(async () => {})
  const props = { events: [], disabled: false, isRunning: false, activity: [], onSend, onCancel: async () => {}, runtimeMode: 'pi_reference' as const }
  const view = render(<CapstoneAssistantThread {...props} inputCatalog={direct} />)
  const input = screen.getByRole('textbox', { name: 'Thread 指令' })
  fireEvent.change(input, { target: { value: '/skill:pandapower inspect model' } })
  fireEvent.keyDown(input, { key: 'Enter' })
  expect(screen.queryByRole('button', { name: '选择技能' })).toBeNull()
  expect(onSend).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: '发送指令' }))
  await waitFor(() => expect(onSend).toHaveBeenCalledWith('automatic', 'inspect model', expect.objectContaining({
    input: { kind: 'skill_invocation', text: 'inspect model', skill_id: skill.id, skill_version: 'version-A' },
    resource_profile: { profile_id: 'direct_pi', revision: 'accepted-A' } })))
  view.rerender(<CapstoneAssistantThread {...props} inputCatalog={{ ...direct, resource_profiles: { direct_pi: {
    revision: 'accepted-A', resources: [skill, { ...skill, id: 'other-pandapower', source: 'other' }] } } }} />)
  fireEvent.change(input, { target: { value: '/skill:pandapower second task' } })
  fireEvent.keyDown(input, { key: 'Enter' })
  expect(screen.getByRole('dialog', { name: '已安装技能' })).toBeTruthy()
  expect(screen.getAllByText(/version-A/)).toHaveLength(2)
  expect(onSend).toHaveBeenCalledTimes(1)
})
const catalog: InputCatalog = { schema: 'capstone-thread-input-catalog/1', revision: 'cat1', context_id: 'ctx', selection_revision: 'sel',
  objects: [{ object_id: 'ctx', model_id: 'ieee39', model_revision: '7', implementation_family: 'pandapower' }], materials: [], operations: [],
  resource_profiles: { delegated_pi: { revision: 'exact', resources: [{ id: 'skill-a', kind: 'skill', installed:true, version: '1', source: 'managed', ready: true, reason: null }] } } }

it('opens UI commands without sending and completion Enter never submits', async () => {
  const onSend = vi.fn(async () => {})
  render(<CapstoneAssistantThread events={[]} disabled={false} isRunning={false} activity={[]} onSend={onSend} onCancel={async () => {}} inputCatalog={catalog} />)
  const input = screen.getByRole('textbox', { name: 'Thread 指令' })
  fireEvent.change(input, { target: { value: '/context' } })
  fireEvent.keyDown(input, { key: 'Enter' })
  expect(screen.getByRole('dialog', { name: '本轮上下文' })).toBeTruthy()
  expect(screen.getByText('暂无可用资料。当前仅提供模型身份、版本与相关历史，不含完整网络表。')).toBeTruthy()
  expect(onSend).not.toHaveBeenCalled()
  fireEvent.keyDown(input, { key: 'Escape' })
  expect(screen.queryByRole('dialog')).toBeNull()
  fireEvent.change(input, { target: { value: '/skills' } })
  fireEvent.keyDown(input, { key: 'Enter', isComposing: true })
  expect(screen.queryByRole('dialog')).toBeNull()
  fireEvent.keyDown(input, { key: 'Enter' })
  expect(screen.getByRole('dialog',{name:'已安装技能'})).toBeTruthy()
  expect(screen.queryByRole('checkbox')).toBeNull()
  fireEvent.click(screen.getByRole('button',{name:'关闭'}))
  fireEvent.change(input, { target: { value: 'use method' } })
  fireEvent.click(screen.getByRole('button', { name: '发送指令' }))
  await waitFor(() => expect(onSend).toHaveBeenCalledTimes(1))
  expect((onSend.mock.calls as unknown[][])[0][1]).toBe('use method')
  expect((onSend.mock.calls as unknown[][])[0][2]).not.toHaveProperty('resource_profile')
})

it('preserves text and incompatible selection on mode change and requires re-selection', () => {
  const props = { events: [], disabled: false, isRunning: false, activity: [], onSend: vi.fn(async () => {}), onCancel: async () => {}, inputCatalog: catalog }
  const view = render(<CapstoneAssistantThread {...props} />)
  invokeSkill()
  const input = screen.getByRole('textbox', { name: 'Thread 指令' })
  fireEvent.change(input, { target: { value: 'keep draft' } })
  view.rerender(<CapstoneAssistantThread {...props} runtimeMode="pi_reference" />)
  expect((input as HTMLTextAreaElement).value).toBe('keep draft')
  expect(screen.getByText(/所选技能与当前模式不兼容/)).toBeTruthy()
  expect((screen.getByRole('button', { name: '发送指令' }) as HTMLButtonElement).disabled).toBe(true)
})

it('restores the exact draft and skill after an uncertain submission and remount', async () => {
  const onSend = vi.fn(async () => { throw new MessageNotSentError('receipt unknown') })
  const props = { events: [], disabled: false, isRunning: false, activity: [], onSend, onCancel: async () => {}, inputCatalog: catalog, storageKey: 'typed-recovery' }
  const view = render(<CapstoneAssistantThread {...props} />)
  invokeSkill()
  fireEvent.change(screen.getByRole('textbox', { name: 'Thread 指令' }), { target: { value: 'original draft' } })
  fireEvent.click(screen.getByRole('button', { name: '发送指令' }))
  await waitFor(() => expect(onSend).toHaveBeenCalledTimes(1))
  await waitFor(() => expect((screen.getByRole('textbox', { name: 'Thread 指令' }) as HTMLTextAreaElement).value).toBe('original draft'))
  view.unmount()
  render(<CapstoneAssistantThread {...props} />)
  expect((screen.getByRole('textbox', { name: 'Thread 指令' }) as HTMLTextAreaElement).value).toBe('original draft')
  openSkills()
  expect(screen.getByRole('dialog',{name:'已安装技能'})).toBeTruthy()
  expect(screen.queryByRole('button', { name: '移除技能 skill-a' })).toBeNull()
})

it('unknown commands require a literal choice and do not silently submit', async () => {
  const onSend = vi.fn(async () => {})
  render(<CapstoneAssistantThread events={[]} disabled={false} isRunning={false} activity={[]} onSend={onSend} onCancel={async () => {}} inputCatalog={catalog} />)
  const input = screen.getByRole('textbox', { name: 'Thread 指令' })
  fireEvent.change(input, { target: { value: '/unknown content' } })
  fireEvent.click(screen.getByRole('button', { name: '发送指令' }))
  expect(onSend).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: '按普通文本发送' }))
  fireEvent.click(screen.getByRole('button', { name: '发送指令' }))
  await waitFor(() => expect(onSend).toHaveBeenCalledWith('automatic', '/unknown content', expect.objectContaining({ input: { kind: 'text', text: '/unknown content' } })))
})

it('clears recovered accepted metadata but keeps a changed next draft', async () => {
  const props = { events: [], disabled: false, isRunning: false, activity: [], onSend: async () => {}, onCancel: async () => {}, inputCatalog: catalog }
  const view = render(<CapstoneAssistantThread {...props} />)
  invokeSkill()
  const input = screen.getByRole('textbox', { name: 'Thread 指令' })
  fireEvent.change(input, { target: { value: 'original draft' } })
  const accepted = { text: 'original draft', commandId: 'cmd_recovered', submission: {
    input: { kind: 'skill_invocation' as const, text: 'original draft', skill_id: 'skill-a', skill_version: '1' },
    resource_profile: { profile_id: 'delegated_pi' as const, revision: 'exact' }, context_selection: { include_refs: [], exclude_refs: [] } } }
  view.rerender(<CapstoneAssistantThread {...props} acceptedDraft={accepted} />)
  await waitFor(() => expect((input as HTMLTextAreaElement).value).toBe(''))
  expect(screen.queryByRole('button', { name: '移除技能 skill-a' })).toBeNull()
  fireEvent.change(input, { target: { value: 'next draft' } })
  view.rerender(<CapstoneAssistantThread {...props} acceptedDraft={{ ...accepted, commandId: 'cmd_other' }} />)
  expect((input as HTMLTextAreaElement).value).toBe('next draft')
})

it('shows installed methods read-only from the toolbar without changing the draft',()=>{
 const onSend=vi.fn(async()=>{})
 const resources=[{id:'installed',native_name:'调查',kind:'skill',version:'1',source:'local',installed:true,ready:true,reason:null},{id:'missing',kind:'skill',version:'1',source:'local',installed:false,ready:false,reason:'not installed'}]
 render(<CapstoneAssistantThread events={[]} disabled={false} isRunning={false} activity={[]} onSend={onSend} onCancel={async()=>{}} inputCatalog={{...catalog,resource_profiles:{delegated_pi:{revision:'r',resources}}}} />)
 const input=screen.getByRole('textbox',{name:'Thread 指令'})
 fireEvent.change(input,{target:{value:'保留这段问题'}})
 fireEvent.click(screen.getByRole('button',{name:'技能'}))
 expect(screen.getByRole('dialog',{name:'已安装技能'})).toBeTruthy()
 expect(screen.getByText('调查')).toBeTruthy()
 expect(screen.queryByText('missing')).toBeNull()
 expect(screen.queryByRole('checkbox')).toBeNull()
 expect(screen.queryByRole('button',{name:'保存'})).toBeNull()
 expect((input as HTMLTextAreaElement).value).toBe('保留这段问题')
 expect(onSend).not.toHaveBeenCalled()
})
