import {afterEach,expect,it,vi} from 'vitest'
import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import LlmProfileMenu from './LlmProfileMenu'
import WelcomeConnections from './WelcomeConnections'

afterEach(cleanup)
const catalog={default_profile_id:'commercial-deepseek-flash',profiles:[
  {id:'commercial-deepseek-flash',label:'deepseek-flash',model:'deepseek-flash',available:true,icon:'deepseek'},
  {id:'internal',label:'192.168.72.69:18804',model:'dsv4',available:true,icon:'server'},
  {id:'custom',label:'自定义模型',model:'',available:false,icon:'server'},
]}
it('focuses the selected model, includes unconfigured presets and returns focus on escape',()=>{
  render(<LlmProfileMenu catalog={catalog} value="internal" onChange={vi.fn()}/> )
  const trigger=screen.getByRole('button',{name:'后端 LLM'})
  fireEvent.click(trigger)
  expect(document.activeElement).toBe(screen.getByRole('menuitemradio',{name:/18804/}))
  fireEvent.keyDown(document.activeElement!,{key:'ArrowDown'})
  const unconfigured=screen.getByRole('menuitemradio',{name:/自定义模型.*未配置/})
  expect(document.activeElement).toBe(unconfigured)
  fireEvent.keyDown(document.activeElement!,{key:'Escape'})
  expect(screen.queryByRole('menu')).toBeNull()
  expect(document.activeElement).toBe(trigger)
})
it('allows selecting an unconfigured preset',()=>{
  const onChange=vi.fn()
  render(<LlmProfileMenu catalog={catalog} onChange={onChange}/>)
  fireEvent.click(screen.getByRole('button',{name:'后端 LLM'}))
  fireEvent.click(screen.getByRole('menuitemradio',{name:/自定义模型.*未配置/}))
  expect(onChange).toHaveBeenCalledWith('custom')
  expect(screen.queryByRole('menu')).toBeNull()
})
it('uses the DeepSeek brand in the trigger and option, including a cached catalog',()=>{
  render(<LlmProfileMenu catalog={{...catalog,profiles:catalog.profiles.map(p=>({...p,icon:undefined}))}} onChange={vi.fn()}/> )
  expect(screen.getByRole('button',{name:'后端 LLM'}).querySelector('img')?.getAttribute('src')).toBe('/icons/deepseek.svg')
  fireEvent.click(screen.getByRole('button',{name:'后端 LLM'}))
  expect(screen.getByRole('menuitemradio',{name:'deepseek-flash'}).querySelector('img')).not.toBeNull()
  expect(screen.getByRole('menuitemradio',{name:/18804/}).querySelector('img')).toBeNull()
})

it.each([
  {id:'local-qwen-35b',label:'Qwen3.6-35B-A3B（本机）',model:'weights/Qwen3.6-35B-A3B.gguf',available:true,icon:'server'},
  {id:'local-qwen-27b',label:'Qwen3.8-27B（本机）',model:'weights/Qwen3.8-27B.gguf',available:true,icon:'qwen'},
])('shows the short $label label and brand in the menu and welcome card',qwen=>{
  const models={...catalog,profiles:[...catalog.profiles,qwen]}
  render(<><LlmProfileMenu catalog={models} value={qwen.id} onChange={vi.fn()}/>
    <WelcomeConnections catalog={{llm_profiles:models} as Parameters<typeof WelcomeConnections>[0]['catalog']} profileId={qwen.id}/></>)
  const trigger=screen.getByRole('button',{name:'后端 LLM'})
  expect(trigger.textContent).toBe(qwen.label)
  expect(trigger.querySelector('img')?.getAttribute('src')).toBe('/icons/qwen.svg')
  fireEvent.click(trigger)
  expect(screen.getByRole('menuitemradio',{name:qwen.label}).querySelector('img')?.getAttribute('src')).toBe('/icons/qwen.svg')
  const connection=screen.getByRole('region',{name:'当前会话连接'})
  expect(connection.textContent).toContain(qwen.label)
  expect(connection.textContent).not.toContain(qwen.model)
  expect(connection.querySelector('img')?.getAttribute('src')).toBe('/icons/qwen.svg')
})
