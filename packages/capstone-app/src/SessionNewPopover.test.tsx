import {afterEach,expect,it,vi} from 'vitest'
import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import SessionNewPopover from './SessionNewPopover'

afterEach(()=>{cleanup();vi.unstubAllGlobals();sessionStorage.clear()})
function host(){
  const writes:RequestInit[]=[]
  vi.stubGlobal('fetch',vi.fn(async(url:string,init?:RequestInit)=>{
    if(url.endsWith('/thread-access'))return Response.json({schema:'capstone-thread-access/1',mode:'open'})
    if(url.endsWith('/thread-catalog'))return Response.json({schema:'capstone-thread-catalog/1',models:[{model_id:'ieee39',display_name:'IEEE-39',authority_model_ref:'gridctl:ieee39',diagram_provider_id:'pandapower',implementation_family:'pandapower'}],profiles:[]})
    if(init?.method==='POST'){writes.push(init);return Response.json({schema:JSON.parse(String(init.body)).session_type==='grid-analysis'?'capstone-thread-snapshot/1':'capstone-thread-snapshot/2',thread_id:'thr_created'},{headers:{'Capstone-Thread-Version':JSON.parse(String(init.body)).session_type==='grid-analysis'?'1':'2'}})}
    return Response.json({schema:'capstone-thread-list/1',threads:[],has_more:false,next_before_thread_id:null})
  }))
  return writes
}
it('keeps the current conversation mounted while opening and dismissing a compact creation picker',async()=>{
  const writes=host()
  render(<><SessionNewPopover /><textarea aria-label="当前草稿" defaultValue="继续原问题"/><button>外部按钮</button></>)
  const trigger=screen.getByRole('button',{name:'新建会话'})
  fireEvent.click(trigger)
  await screen.findByRole('button',{name:'通用聊天'})
  expect(screen.getByRole('dialog',{name:'新建会话'})).toBeTruthy()
  expect((screen.getByRole('textbox',{name:'当前草稿'}) as HTMLTextAreaElement).value).toBe('继续原问题')
  expect(writes).toHaveLength(0)
  // Background composer restoration must not dismiss a resource choice.
  act(()=>screen.getByRole('textbox',{name:'当前草稿'}).focus())
  expect(screen.getByRole('dialog',{name:'新建会话'})).toBeTruthy()
  fireEvent.keyDown(document,{key:'Escape'})
  expect(screen.queryByRole('dialog')).toBeNull()
  expect(document.activeElement).toBe(trigger)
  fireEvent.click(trigger)
  await screen.findByRole('button',{name:'通用聊天'})
  fireEvent.pointerDown(screen.getByRole('button',{name:'外部按钮'}))
  expect(screen.queryByRole('dialog')).toBeNull()
  expect(document.activeElement).toBe(trigger)
})
it.each(['general-chat','enterprise-research','grid-analysis'])('creates %s through the existing host contract',async(type)=>{
  const writes=host(),created=vi.fn()
  render(<SessionNewPopover onCreated={created}/>)
  fireEvent.click(screen.getByRole('button',{name:'新建会话'}))
  fireEvent.click(await screen.findByRole('button',{name:type==='general-chat'?'通用聊天':type==='enterprise-research'?'企业研究与分析':'电网分析与决策'}))
  if(type==='grid-analysis'){
    expect(writes).toHaveLength(0)
    fireEvent.change(screen.getByRole('combobox',{name:'主要模型'}),{target:{value:'ieee39'}})
    fireEvent.click(screen.getByRole('button',{name:'创建会话'}))
  }
  await waitFor(()=>expect(created).toHaveBeenCalledWith('thr_created'))
  expect(JSON.parse(String(writes[0].body))).toEqual({session_type:type,...(type==='grid-analysis'?{model_id:'ieee39'}:{})})
  expect(screen.queryByRole('dialog')).toBeNull()
})
it('keeps a dismissed picker from navigating when its creation response arrives late',async()=>{
  host()
  const read=globalThis.fetch
  let finish!:(response:Response)=>void
  vi.stubGlobal('fetch',vi.fn((url:string,init?:RequestInit)=>init?.method==='POST'?new Promise<Response>(resolve=>{finish=resolve}):read(url,init)))
  const created=vi.fn()
  render(<SessionNewPopover onCreated={created}/>)
  fireEvent.click(screen.getByRole('button',{name:'新建会话'}))
  fireEvent.click(await screen.findByRole('button',{name:'通用聊天'}))
  await waitFor(()=>expect(finish).toBeDefined())
  fireEvent.keyDown(document,{key:'Escape'})
  finish(Response.json({schema:'capstone-thread-snapshot/2',thread_id:'thr_late'},{headers:{'Capstone-Thread-Version':'2'}}))
  await new Promise(resolve=>setTimeout(resolve,0))
  expect(created).not.toHaveBeenCalled()
})
