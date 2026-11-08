import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import {afterEach,expect,it,vi} from 'vitest'
import SessionSkills from './SessionSkillSettings'
afterEach(cleanup)

it('saves a session choice without sending an instruction and retains errors',async()=>{
  const save=vi.fn().mockRejectedValueOnce(new Error('配置已变化，请刷新后重选。')).mockResolvedValue(undefined)
  render(<SessionSkills value={{revision:0,skills:[]}} mode="capstone" catalog={{resource_profiles:{delegated_pi:{revision:'r',resources:[{id:'method',native_name:'调查方法',loaded_identity:'a'.repeat(64),version:'v1',kind:'skill',ready:true,source:'local',reason:null}]}}} as never} onSave={save}/> )
  fireEvent.click(screen.getByText('会话技能'))
  fireEvent.click(screen.getByLabelText('调查方法'))
  fireEvent.click(screen.getByText('保存'))
  await waitFor(()=>expect(screen.getByRole('alert').textContent).toContain('配置已变化'))
  expect(save).toHaveBeenCalledWith([{id:'method',version:'v1',role:'delegated_pi',loaded_identity:'a'.repeat(64),native_name:'调查方法',catalog_revision:'r'}],0)
  expect((screen.getByRole('checkbox') as HTMLInputElement).checked).toBe(true)
})

it('reloads a conflicting revision only after an explicit user action',async()=>{
 const save=vi.fn().mockRejectedValueOnce(new Error('配置已变化')).mockResolvedValue(undefined)
 const reload=vi.fn().mockResolvedValue({revision:2,skills:[]})
 render(<SessionSkills value={{revision:0,skills:[]}} mode="capstone" catalog={{resource_profiles:{delegated_pi:{revision:'r',resources:[{id:'method',native_name:'调查方法',loaded_identity:'a'.repeat(64),version:'v1',kind:'skill',ready:true,source:'local',reason:null}]}}} as never} onSave={save} onReload={reload}/> )
 fireEvent.click(screen.getByText('会话技能'));fireEvent.click(screen.getByLabelText('调查方法'));fireEvent.click(screen.getByText('保存'))
 await waitFor(()=>expect(screen.getByRole('alert').textContent).toContain('配置已变化'))
 expect(reload).not.toHaveBeenCalled()
 fireEvent.click(screen.getByText('读取最新配置'))
 await waitFor(()=>expect((screen.getByRole('checkbox') as HTMLInputElement).checked).toBe(false))
 fireEvent.click(screen.getByLabelText('调查方法'));fireEvent.click(screen.getByText('保存'))
 await waitFor(()=>expect(save).toHaveBeenLastCalledWith(expect.any(Array),2))
})
