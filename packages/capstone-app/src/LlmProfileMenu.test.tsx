import {afterEach,expect,it,vi} from 'vitest'
import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import LlmProfileMenu from './LlmProfileMenu'

afterEach(cleanup)
const catalog={default_profile_id:'commercial-deepseek-flash',profiles:[
  {id:'commercial-deepseek-flash',label:'deepseek-flash',model:'deepseek-flash',available:true,icon:'deepseek'},
  {id:'internal',label:'192.168.72.69:18804',model:'dsv4',available:true,icon:'server'},
  {id:'custom',label:'自定义模型',model:'',available:false,icon:'server'},
]}
it('focuses the selected model, skips unavailable choices and returns focus on escape',()=>{
  render(<LlmProfileMenu catalog={catalog} value="internal" onChange={vi.fn()}/> )
  const trigger=screen.getByRole('button',{name:'后端 LLM'})
  fireEvent.click(trigger)
  expect(document.activeElement).toBe(screen.getByRole('menuitemradio',{name:/18804/}))
  fireEvent.keyDown(document.activeElement!,{key:'ArrowDown'})
  expect(document.activeElement).toBe(screen.getByRole('menuitemradio',{name:'deepseek-flash'}))
  fireEvent.keyDown(document.activeElement!,{key:'Escape'})
  expect(screen.queryByRole('menu')).toBeNull()
  expect(document.activeElement).toBe(trigger)
})
it('uses the DeepSeek brand in the trigger and option, including a cached catalog',()=>{
  render(<LlmProfileMenu catalog={{...catalog,profiles:catalog.profiles.map(p=>({...p,icon:undefined}))}} onChange={vi.fn()}/> )
  expect(screen.getByRole('button',{name:'后端 LLM'}).querySelector('img')?.getAttribute('src')).toBe('/icons/deepseek.svg')
  fireEvent.click(screen.getByRole('button',{name:'后端 LLM'}))
  expect(screen.getByRole('menuitemradio',{name:'deepseek-flash'}).querySelector('img')).not.toBeNull()
  expect(screen.getByRole('menuitemradio',{name:/18804/}).querySelector('img')).toBeNull()
})
