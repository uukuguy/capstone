import {afterEach,expect,it,vi} from 'vitest'
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import SessionEntry from './SessionEntry'

afterEach(cleanup)
const models=[{modelId:'ieee39',displayName:'IEEE-39',authorityModelRef:'gridctl:ieee39',diagramProviderId:'pandapower',implementationFamily:'pandapower'}]
it('creates native choices directly in a compact picker and expands only the grid model selection',async()=>{
  const create=vi.fn().mockResolvedValue(undefined)
  render(<SessionEntry compact models={models} onCreate={create} />)
  expect(screen.queryByRole('button',{name:'创建会话'})).toBeNull()
  fireEvent.click(screen.getByRole('button',{name:'通用聊天'}))
  await waitFor(()=>expect(create).toHaveBeenCalledWith({session_type:'general-chat'}))
  fireEvent.click(screen.getByRole('button',{name:'企业研究与分析'}))
  await waitFor(()=>expect(create).toHaveBeenLastCalledWith({session_type:'enterprise-research'}))
  fireEvent.click(screen.getByRole('button',{name:'电网分析与决策'}))
  expect(create).toHaveBeenCalledTimes(2)
  expect(screen.getByRole('combobox',{name:'主要模型'})).toBeTruthy()
  fireEvent.change(screen.getByRole('combobox',{name:'主要模型'}),{target:{value:'ieee39'}})
  fireEvent.click(screen.getByRole('button',{name:'创建会话'}))
  await waitFor(()=>expect(create).toHaveBeenLastCalledWith({session_type:'grid-analysis',model_id:'ieee39'}))
})
it('requires a registered grid object but no concrete goal',async()=>{
  const create=vi.fn().mockResolvedValue(undefined)
  render(<SessionEntry models={models} onCreate={create} />)
  fireEvent.click(screen.getByRole('radio',{name:'电网分析与决策'}))
  expect((screen.getByRole('button',{name:'创建会话'}) as HTMLButtonElement).disabled).toBe(true)
  fireEvent.change(screen.getByRole('combobox',{name:'主要模型'}),{target:{value:'ieee39'}})
  fireEvent.click(screen.getByRole('button',{name:'创建会话'}))
  await waitFor(()=>expect(create).toHaveBeenCalledWith({session_type:'grid-analysis',model_id:'ieee39'}))
  expect(screen.queryByRole('textbox',{name:'任务目标'})).toBeNull()
})
it('creates native types without a model and retains the choice after failure',async()=>{
  const create=vi.fn().mockRejectedValue(new Error('连接中断，请重试。'))
  render(<SessionEntry models={models} onCreate={create} />)
  fireEvent.click(screen.getByRole('radio',{name:'企业研究与分析'}))
  fireEvent.click(screen.getByRole('button',{name:'创建会话'}))
  await screen.findByRole('alert')
  expect(create).toHaveBeenCalledWith({session_type:'enterprise-research'})
  expect((screen.getByRole('radio',{name:'企业研究与分析'}) as HTMLInputElement).checked).toBe(true)
  fireEvent.click(screen.getByRole('radio',{name:'通用聊天'}))
  fireEvent.click(screen.getByRole('button',{name:'创建会话'}))
  await waitFor(()=>expect(create).toHaveBeenLastCalledWith({session_type:'general-chat'}))
})
