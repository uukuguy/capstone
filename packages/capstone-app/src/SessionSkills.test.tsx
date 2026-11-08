import {fireEvent,render,screen,waitFor} from '@testing-library/react'
import {expect,it,vi} from 'vitest'
import SessionSkills from './SessionSkillSettings'

it('saves a session choice without sending an instruction and retains errors',async()=>{
  const save=vi.fn().mockRejectedValueOnce(new Error('配置已变化，请刷新后重选。')).mockResolvedValue(undefined)
  render(<SessionSkills value={{revision:0,skills:[]}} mode="capstone" catalog={{resource_profiles:{delegated_pi:{revision:'r',resources:[{id:'method',native_name:'调查方法',version:'v1',kind:'skill',ready:true,source:'local',reason:null}]}}} as never} onSave={save}/> )
  fireEvent.click(screen.getByText('会话技能'))
  fireEvent.click(screen.getByLabelText('调查方法'))
  fireEvent.click(screen.getByText('保存'))
  await waitFor(()=>expect(screen.getByRole('alert').textContent).toContain('配置已变化'))
  expect(save).toHaveBeenCalledWith([{id:'method',version:'v1',role:'delegated_pi'}],0)
  expect((screen.getByRole('checkbox') as HTMLInputElement).checked).toBe(true)
})
