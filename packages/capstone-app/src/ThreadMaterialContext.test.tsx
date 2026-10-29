import {afterEach,expect,it,vi} from 'vitest'
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import CapstoneAssistantThread from './CapstoneAssistantThread'
import type {InputCatalog} from './threadInput'

afterEach(()=>{cleanup();sessionStorage.clear();localStorage.clear()})
function openContext(){const input=screen.getByRole('textbox',{name:'Thread 指令'});fireEvent.change(input,{target:{value:'/context'}});fireEvent.keyDown(input,{key:'Enter'})}
const one=`material_${'a'.repeat(32)}`,two=`material_${'b'.repeat(32)}`
const catalog:InputCatalog={schema:'capstone-thread-input-catalog/1',revision:'input_one',context_id:'ctx_none',selection_revision:'sel_one',objects:[],materials:[{material_id:one,display_name:'需求.md',size_bytes:12},{material_id:two,display_name:'记录.txt',size_bytes:12}],resource_profiles:{},operations:[]}
it('uses all associated materials by default and retains an explicit subset after sending',async()=>{
  const send=vi.fn().mockResolvedValue(undefined)
  render(<CapstoneAssistantThread inputCatalog={catalog} storageKey="material-selection" events={[]} disabled={false} isRunning={false} activity={[]} onSend={send} onCancel={async()=>{}}/>)
  openContext()
  expect((screen.getByRole('checkbox',{name:'读取资料 需求.md'}) as HTMLInputElement).checked).toBe(true)
  fireEvent.click(screen.getByRole('checkbox',{name:'读取资料 需求.md'}))
  fireEvent.click(screen.getByRole('button',{name:'关闭上下文'}))
  fireEvent.change(screen.getByRole('textbox',{name:'Thread 指令'}),{target:{value:'按所选资料回答'}})
  fireEvent.click(screen.getByRole('button',{name:'发送指令'}))
  await waitFor(()=>expect(send).toHaveBeenCalledWith('automatic','按所选资料回答',expect.objectContaining({material_refs:[two]})))
  openContext()
  expect((screen.getByRole('checkbox',{name:'读取资料 需求.md'}) as HTMLInputElement).checked).toBe(false)
  expect((screen.getByRole('checkbox',{name:'读取资料 记录.txt'}) as HTMLInputElement).checked).toBe(true)
})
it('sends an explicit empty selection instead of silently reverting to all materials',async()=>{
  const send=vi.fn().mockResolvedValue(undefined)
  render(<CapstoneAssistantThread inputCatalog={catalog} events={[]} disabled={false} isRunning={false} activity={[]} onSend={send} onCancel={async()=>{}}/>)
  openContext()
  fireEvent.click(screen.getByRole('checkbox',{name:'读取资料 需求.md'}))
  fireEvent.click(screen.getByRole('checkbox',{name:'读取资料 记录.txt'}))
  fireEvent.click(screen.getByRole('button',{name:'关闭上下文'}))
  fireEvent.change(screen.getByRole('textbox',{name:'Thread 指令'}),{target:{value:'本轮只讨论一般问题'}})
  fireEvent.click(screen.getByRole('button',{name:'发送指令'}))
  await waitFor(()=>expect(send).toHaveBeenCalledWith('automatic','本轮只讨论一般问题',expect.objectContaining({material_refs:[]})))
})
it('adds an uploaded material to an explicit subset through the existing input controller',async()=>{
  const three=`material_${'c'.repeat(32)}`
  const props={events:[],disabled:false,isRunning:false,activity:[],onSend:async()=>{},onCancel:async()=>{}}
  const controls:NonNullable<React.ComponentProps<typeof CapstoneAssistantThread>['composerControls']>=(_,actions)=><button onClick={()=>actions.addMaterial(three)}>上传完成</button>
  const view=render(<CapstoneAssistantThread {...props} inputCatalog={catalog} composerControls={controls}/>)
  openContext()
  fireEvent.click(screen.getByRole('checkbox',{name:'读取资料 需求.md'}))
  fireEvent.click(screen.getByRole('button',{name:'关闭上下文'}))
  fireEvent.click(screen.getByRole('button',{name:'上传完成'}))
  view.rerender(<CapstoneAssistantThread {...props} inputCatalog={{...catalog,materials:[...catalog.materials,{material_id:three,display_name:'补充.csv',size_bytes:12}]}} composerControls={controls}/>)
  openContext()
  expect((screen.getByRole('checkbox',{name:'读取资料 需求.md'}) as HTMLInputElement).checked).toBe(false)
  expect((screen.getByRole('checkbox',{name:'读取资料 记录.txt'}) as HTMLInputElement).checked).toBe(true)
  expect((screen.getByRole('checkbox',{name:'读取资料 补充.csv'}) as HTMLInputElement).checked).toBe(true)
})
