import {StrictMode} from 'react'
import {afterEach,expect,it,vi} from 'vitest'
import {cleanup,render,screen,waitFor} from '@testing-library/react'
import WorkspaceSessionEntry from './WorkspaceSessionEntry'
import SessionNavigation from './SessionNavigation'
import {rememberWorkspaceThread} from './workspaceEntry'
afterEach(()=>{cleanup();vi.unstubAllGlobals();sessionStorage.clear();localStorage.clear();window.history.replaceState({},'','/')})
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
it.each([['thr_saved','thr_saved'],['thr_missing','thr_recent'],[undefined,'thr_recent']])('restores threadless entry using saved %s then recent session',async(saved,expected)=>{
  window.history.replaceState({},'','/?workspace=enterprise')
  if(saved)rememberWorkspaceThread(saved)
  const threads=['thr_recent','thr_saved'].map(thread_id=>({thread_id,model_id:null,implementation_family:null,minimum_protocol_version:2,created_at:'2026-10-31',archived:false,last_event_seq:0}))
  const fetcher=vi.fn(async(url:string,_init?:RequestInit)=>url.endsWith('/thread-access')?Response.json({schema:'capstone-thread-access/1',mode:'open'}):Response.json({schema:'capstone-thread-list/1',threads,has_more:false,next_before_thread_id:null}))
  vi.stubGlobal('fetch',fetcher)
  render(<WorkspaceSessionEntry onCreated={vi.fn()}/>)
  await waitFor(()=>expect(new URLSearchParams(location.search).get('thread')).toBe(expected))
  expect(fetcher.mock.calls.every(([,init])=>!init?.method||init.method==='GET')).toBe(true)
})
it('creates exactly one session when threadless history is empty',async()=>{
  const created=vi.fn(),writes:RequestInit[]=[]
  vi.stubGlobal('fetch',vi.fn(async(url:string,init?:RequestInit)=>{
    if(url.endsWith('/thread-access'))return Response.json({schema:'capstone-thread-access/1',mode:'open'})
    if(init?.method==='POST'){writes.push(init);return Response.json({schema:'capstone-thread-snapshot/2',thread_id:'thr_first'},{headers:{'Capstone-Thread-Version':'2'}})}
    return Response.json({schema:'capstone-thread-list/1',threads:[],has_more:false,next_before_thread_id:null})
  }))
  render(<StrictMode><WorkspaceSessionEntry onCreated={created}/></StrictMode>)
  await waitFor(()=>expect(created).toHaveBeenCalledExactlyOnceWith('thr_first'))
  expect(writes).toHaveLength(1)
})
it('finds the saved session beyond the first history page',async()=>{
  window.history.replaceState({},'','/?workspace=enterprise')
  rememberWorkspaceThread('thr_older')
  const calls:string[]=[]
  vi.stubGlobal('fetch',vi.fn(async(url:string)=>{
    calls.push(url)
    if(url.endsWith('/thread-access'))return Response.json({schema:'capstone-thread-access/1',mode:'open'})
    const older=url.includes('before='),id=older?'thr_older':'thr_recent'
    return Response.json({schema:'capstone-thread-list/1',threads:[{thread_id:id,model_id:null,implementation_family:null,minimum_protocol_version:2,created_at:'2026-10-31',archived:false,last_event_seq:0}],has_more:!older,next_before_thread_id:older?null:id})
  }))
  render(<WorkspaceSessionEntry onCreated={vi.fn()}/>)
  await waitFor(()=>expect(new URLSearchParams(location.search).get('thread')).toBe('thr_older'))
  expect(calls.some(url=>url.includes('before=thr_recent'))).toBe(true)
})
it('does not override a user selection made while history is loading',async()=>{
  let complete!:(value:Response)=>void
  vi.stubGlobal('fetch',vi.fn(async(url:string)=>url.endsWith('/thread-access')?Response.json({schema:'capstone-thread-access/1',mode:'open'}):new Promise<Response>(resolve=>{complete=resolve})))
  const created=vi.fn()
  render(<WorkspaceSessionEntry onCreated={created}/>)
  await waitFor(()=>expect(complete).toBeTypeOf('function'))
  window.history.replaceState({},'','/?workspace=enterprise&thread=thr_chosen')
  complete(Response.json({schema:'capstone-thread-list/1',threads:[],has_more:false,next_before_thread_id:null}))
  await new Promise(resolve=>setTimeout(resolve,0))
  expect(new URLSearchParams(location.search).get('thread')).toBe('thr_chosen')
  expect(created).not.toHaveBeenCalled()
})
it('does not interpret failed history reads as an empty workspace',async()=>{
  const created=vi.fn()
  vi.stubGlobal('fetch',vi.fn(async(url:string)=>url.endsWith('/thread-access')?Response.json({schema:'capstone-thread-access/1',mode:'open'}):new Response('',{status:403})))
  render(<WorkspaceSessionEntry onCreated={created}/>)
  expect(await screen.findByRole('alert')).toBeTruthy()
  expect(created).not.toHaveBeenCalled()
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
