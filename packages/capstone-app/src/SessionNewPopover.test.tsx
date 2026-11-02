import {afterEach,expect,it,vi} from 'vitest'
import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import SessionNewPopover from './SessionNewPopover'
afterEach(()=>{cleanup();vi.unstubAllGlobals();sessionStorage.clear()})
function host(mode='open'){
  const writes:RequestInit[]=[]
  let finish!:(response:Response)=>void
  vi.stubGlobal('fetch',vi.fn(async(url:string,init?:RequestInit)=>{
    if(url.endsWith('/thread-access'))return Response.json({schema:'capstone-thread-access/1',mode})
    if(init?.method==='POST'){writes.push(init);return new Promise<Response>(resolve=>{finish=resolve})}
    return new Response('',{status:503})
  }))
  return {writes,finish:()=>finish(Response.json({schema:'capstone-thread-snapshot/2',thread_id:'thr_created'},{headers:{'Capstone-Thread-Version':'2'}}))}
}
it('creates directly once and preserves the current draft while pending without loading resources',async()=>{
  const api=host(),created=vi.fn()
  render(<><SessionNewPopover onCreated={created}/><textarea aria-label="当前草稿" defaultValue="继续原问题"/></>)
  const trigger=screen.getByRole('button',{name:'新建会话'})
  fireEvent.click(trigger);fireEvent.click(trigger)
  await waitFor(()=>expect(api.writes).toHaveLength(1))
  expect(screen.queryByRole('dialog')).toBeNull()
  expect(screen.queryByRole('radio')).toBeNull()
  expect((screen.getByRole('textbox',{name:'当前草稿'}) as HTMLTextAreaElement).value).toBe('继续原问题')
  expect(JSON.parse(String(api.writes[0].body))).toEqual({session_type:'enterprise-research'})
  expect((api.writes[0].headers as Record<string,string>)['Capstone-Thread-Version']).toBe('2')
  await act(async()=>api.finish())
  expect(created).toHaveBeenCalledExactlyOnceWith('thr_created')
})
it('does not navigate after the user switches sessions during creation',async()=>{
  const api=host(),created=vi.fn()
  render(<SessionNewPopover onCreated={created}/>)
  fireEvent.click(screen.getByRole('button',{name:'新建会话'}))
  await waitFor(()=>expect(api.writes).toHaveLength(1))
  fireEvent(window,new PopStateEvent('popstate'))
  await act(async()=>api.finish())
  expect(created).not.toHaveBeenCalled()
})
it('requests authentication before creating an operator session',async()=>{
  const api=host('operator'),created=vi.fn()
  render(<SessionNewPopover onCreated={created}/>)
  fireEvent.click(screen.getByRole('button',{name:'新建会话'}))
  fireEvent.change(await screen.findByLabelText('Operator token'),{target:{value:'test-token'}})
  expect(api.writes).toHaveLength(0)
  fireEvent.click(screen.getByRole('button',{name:'连接'}))
  await waitFor(()=>expect(api.writes).toHaveLength(1))
  expect((api.writes[0].headers as Record<string,string>).Authorization).toBe('Bearer test-token')
  await act(async()=>api.finish())
})
it('allows a rejected saved token to be replaced before retrying creation',async()=>{
  sessionStorage.setItem('capstone.thread.operatorToken','expired')
  const created=vi.fn()
  vi.stubGlobal('fetch',vi.fn(async(url:string,init?:RequestInit)=>{
    if(url.endsWith('/thread-access'))return Response.json({schema:'capstone-thread-access/1',mode:'operator'})
    if((init?.headers as Record<string,string>).Authorization==='Bearer expired')return Response.json({detail:'Unauthorized'},{status:401})
    return Response.json({schema:'capstone-thread-snapshot/2',thread_id:'thr_created'},{headers:{'Capstone-Thread-Version':'2'}})
  }))
  render(<SessionNewPopover onCreated={created}/>)
  fireEvent.click(screen.getByRole('button',{name:'新建会话'}))
  fireEvent.change(await screen.findByLabelText('Operator token'),{target:{value:'replacement'}})
  fireEvent.click(screen.getByRole('button',{name:'连接'}))
  await waitFor(()=>expect(created).toHaveBeenCalledWith('thr_created'))
})
