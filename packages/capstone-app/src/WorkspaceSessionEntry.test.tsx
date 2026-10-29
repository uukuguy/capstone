import {StrictMode} from 'react'
import {afterEach,expect,it,vi} from 'vitest'
import {cleanup,render,screen,waitFor} from '@testing-library/react'
import WorkspaceSessionEntry from './WorkspaceSessionEntry'
import SessionNavigation from './SessionNavigation'
afterEach(()=>{cleanup();vi.unstubAllGlobals();sessionStorage.clear();window.history.replaceState({},'','/')})
it('opens the direct new-session entry over v2 without selecting resources or waiting for history',async()=>{
  window.history.replaceState({},'','/?workspace=enterprise&thread=new')
  const writes:RequestInit[]=[]
  vi.stubGlobal('fetch',vi.fn(async(url:string,init?:RequestInit)=>{
    if(url.endsWith('/thread-access'))return Response.json({schema:'capstone-thread-access/1',mode:'open'})
    if(init?.method==='POST'){writes.push(init);return Response.json({schema:'capstone-thread-snapshot/2',thread_id:'thr_created'},{headers:{'Capstone-Thread-Version':'2'}})}
    if(url.includes('/threads?'))return new Promise<Response>(()=>{})
    return new Response('',{status:503})
  }))
  const created=vi.fn()
  render(<StrictMode><WorkspaceSessionEntry onCreated={created}/></StrictMode>)
  await waitFor(()=>expect(created).toHaveBeenCalledExactlyOnceWith('thr_created'))
  expect(writes).toHaveLength(1)
  expect(JSON.parse(String(writes[0].body))).toEqual({session_type:'enterprise-research'})
  expect((writes[0].headers as Record<string,string>)['Capstone-Thread-Version']).toBe('2')
  expect(screen.queryByRole('radio')).toBeNull()
  expect(screen.queryByRole('combobox')).toBeNull()
})
it('does not create a session merely by opening a workspace URL',async()=>{
  window.history.replaceState({},'','/?workspace=enterprise')
  const fetcher=vi.fn(async(url:string,_init?:RequestInit)=>url.endsWith('/thread-access')?Response.json({schema:'capstone-thread-access/1',mode:'open'}):Response.json({threads:[],has_more:false,next_before_thread_id:null}))
  vi.stubGlobal('fetch',fetcher)
  render(<WorkspaceSessionEntry onCreated={vi.fn()}/>)
  await waitFor(()=>expect(screen.getAllByRole('button',{name:'新建会话'})).toHaveLength(2))
  expect(fetcher.mock.calls.every(([,init])=>!init?.method||init.method==='GET')).toBe(true)
})
it('rejects an invalid creation response without navigating',async()=>{
  vi.stubGlobal('fetch',vi.fn(async(url:string)=>{
    if(url.endsWith('/thread-access'))return Response.json({schema:'capstone-thread-access/1',mode:'open'})
    return Response.json({schema:'capstone-thread-snapshot/2',thread_id:'../invalid'},{headers:{'Capstone-Thread-Version':'2'}})
  }))
  const created=vi.fn()
  render(<WorkspaceSessionEntry compact onCreated={created}/>)
  expect((await screen.findByRole('alert')).textContent).toContain('会话创建响应无效')
  expect(created).not.toHaveBeenCalled()
})
it('uses a persisted title with model identity and keeps the raw id in details only',()=>{
  render(<SessionNavigation currentId="thr_named" items={[{threadId:'thr_named',modelId:'ieee39',implementationFamily:'pandapower',createdAt:'2026-10-17',archived:false,lastEventSeq:0,sessionTitle:{text:'线路方案比较',source:'user',revision:1,source_ref:null}}]} />)
  const link=screen.getByRole('link',{name:'线路方案比较 · ieee39'})
  expect(link.getAttribute('aria-current')).toBe('page')
  expect(link.textContent).not.toContain('thr_named')
  expect(link.getAttribute('title')).toContain('thr_named')
})
