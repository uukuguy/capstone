import {afterEach,expect,it,vi} from 'vitest'
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import WorkspaceSessionEntry from './WorkspaceSessionEntry'
import SessionNavigation from './SessionNavigation'

afterEach(()=>{cleanup();vi.unstubAllGlobals();sessionStorage.clear()})
const catalog={schema:'capstone-thread-catalog/1',models:[{model_id:'ieee39',display_name:'IEEE-39',authority_model_ref:'gridctl:ieee39',diagram_provider_id:'pandapower',implementation_family:'pandapower'}],profiles:[]}
it('does not create on read and creates a selected native session without a model or command',async()=>{
  const writes:RequestInit[]=[]
  vi.stubGlobal('fetch',vi.fn(async(url:string,init?:RequestInit)=>{
    if(url.endsWith('/thread-access'))return Response.json({schema:'capstone-thread-access/1',mode:'open'})
    if(url.endsWith('/thread-catalog'))return Response.json(catalog)
    if(init?.method==='POST'){writes.push(init);return Response.json({schema:'capstone-thread-snapshot/2',thread_id:'thr_created'},{headers:{'Capstone-Thread-Version':'2'}})}
    if(url.includes('/threads?'))return Response.json({schema:'capstone-thread-list/1',threads:[],has_more:false,next_before_thread_id:null})
    return new Response('',{status:404})
  }))
  const created=vi.fn()
  render(<WorkspaceSessionEntry onCreated={created} />)
  await screen.findByRole('button',{name:'创建会话'})
  expect(writes).toHaveLength(0)
  fireEvent.click(screen.getByRole('radio',{name:'企业研究与分析'}))
  fireEvent.click(screen.getByRole('button',{name:'创建会话'}))
  await waitFor(()=>expect(created).toHaveBeenCalledWith('thr_created'))
  expect(writes).toHaveLength(1)
  expect(JSON.parse(String(writes[0].body))).toEqual({session_type:'enterprise-research'})
  expect((writes[0].headers as Record<string,string>)['Capstone-Thread-Version']).toBe('2')
})
it('uses a persisted title with model identity and keeps the raw id in details only',()=>{
  render(<SessionNavigation currentId="thr_named" items={[{threadId:'thr_named',modelId:'ieee39',implementationFamily:'pandapower',createdAt:'2026-10-17',archived:false,lastEventSeq:0,sessionTitle:{text:'线路方案比较',source:'user',revision:1,source_ref:null}}]} />)
  const link=screen.getByRole('link',{name:'线路方案比较 · ieee39'})
  expect(link.getAttribute('aria-current')).toBe('page')
  expect(link.textContent).not.toContain('thr_named')
  expect(link.getAttribute('title')).toContain('thr_named')
})

it('creates the selected registered grid resource over v1 without starting an execution',async()=>{
  const writes:RequestInit[]=[]
  vi.stubGlobal('fetch',vi.fn(async(url:string,init?:RequestInit)=>{
    if(url.endsWith('/thread-access'))return Response.json({schema:'capstone-thread-access/1',mode:'open'})
    if(url.endsWith('/thread-catalog'))return Response.json(catalog)
    if(init?.method==='POST'){writes.push(init);return Response.json({schema:'capstone-thread-snapshot/1',thread_id:'thr_grid'})}
    if(url.includes('/threads?'))return Response.json({schema:'capstone-thread-list/1',threads:[],has_more:false,next_before_thread_id:null})
    return new Response('',{status:404})
  }))
  const created=vi.fn()
  render(<WorkspaceSessionEntry onCreated={created} />)
  fireEvent.click(await screen.findByRole('radio',{name:'电网分析与决策'}))
  fireEvent.change(screen.getByRole('combobox',{name:'主要模型'}),{target:{value:'ieee39'}})
  fireEvent.click(screen.getByRole('button',{name:'创建会话'}))
  await waitFor(()=>expect(created).toHaveBeenCalledWith('thr_grid'))
  expect(writes).toHaveLength(1)
  expect(JSON.parse(String(writes[0].body))).toEqual({session_type:'grid-analysis',model_id:'ieee39'})
})
