import {Activity,useEffect,useState} from 'react'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {act,cleanup,fireEvent,render,screen,waitFor,within} from '@testing-library/react'
import SessionNavigation,{SessionAdjacentControls} from './SessionNavigation'
const items=['a','b','c'].map(threadId=>({threadId,modelId:null,implementationFamily:null,createdAt:'2026-10-24',archived:false,lastEventSeq:0,sessionTitle:{text:`会话${threadId}`,source:'user' as const,source_ref:null,revision:1}}))
it('anchors deletion confirmation beside its menu instead of the screen center',()=>{
  render(<SessionNavigation items={items} actions={{rename:vi.fn(),archive:vi.fn(),remove:vi.fn(),archived:vi.fn()}}/>)
  fireEvent.contextMenu(screen.getByRole('link',{name:'会话a'}),{clientX:160,clientY:120})
  fireEvent.click(screen.getByRole('menuitem',{name:'删除'}))
  expect(screen.getByRole('alertdialog').style.left).toBe('160px')
  expect(screen.getByRole('alertdialog').style.top).toBe('120px')
})
it('offers a hover delete action for archived sessions and requires confirmation',async()=>{
  const actions={rename:vi.fn(),archive:vi.fn(),remove:vi.fn(async()=>{}),archived:vi.fn(async()=>({threads:[{...items[2],archived:true}],hasMore:false,nextBeforeThreadId:null}))}
  render(<SessionNavigation items={items.slice(0,1)} actions={actions}/>)
  fireEvent.click(screen.getByRole('button',{name:'已归档会话'}))
  fireEvent.click(await screen.findByRole('button',{name:'删除会话：会话c'}))
  expect(actions.remove).not.toHaveBeenCalled()
  expect(document.activeElement).toBe(within(screen.getByRole('alertdialog')).getByRole('button',{name:'删除'}))
  fireEvent.click(within(screen.getByRole('alertdialog')).getByRole('button',{name:'删除'}))
  await waitFor(()=>expect(actions.remove).toHaveBeenCalledWith('c'))
  expect(actions.archive).not.toHaveBeenCalled()
  await waitFor(()=>expect(screen.queryByRole('link',{name:'会话c'})).toBeNull())
})
it('restores pinned sessions outside the recent page',async()=>{
  localStorage.setItem('capstone.session-pins:older',JSON.stringify(['c']))
  const history=vi.fn(async()=>items)
  render(<SessionNavigation items={items.slice(0,1)} storageKey="older" actions={{rename:vi.fn(),archive:vi.fn(),remove:vi.fn(),archived:vi.fn(),history}}/>)
  expect(await screen.findByRole('link',{name:'会话c'})).toBeTruthy()
  expect(screen.queryByRole('link',{name:'会话b'})).toBeNull()
})
it('does not navigate after an archive response arrives in another workspace',async()=>{
  window.history.replaceState({},'','/?workspace=A')
  let finish!:()=>void
  const actions={rename:vi.fn(async()=>{}),archive:vi.fn(()=>new Promise<void>(resolve=>{finish=resolve})),remove:vi.fn(async()=>{}),archived:vi.fn(async()=>({threads:[{...items[2],archived:true}],hasMore:false,nextBeforeThreadId:null}))}
  render(<SessionNavigation items={items.slice(0,2)} currentId="b" actions={actions}/>)
  fireEvent.click(screen.getByRole('button',{name:'已归档会话'}))
  fireEvent.click(await screen.findByRole('link',{name:'会话c'}))
  await waitFor(()=>expect(actions.archive).toHaveBeenCalled())
  window.history.replaceState({},'','/?workspace=B')
  await act(async()=>finish())
  expect(new URLSearchParams(location.search).get('workspace')).toBe('B')
  expect(new URLSearchParams(location.search).get('thread')).toBeNull()
})
beforeEach(()=>{
  vi.spyOn(HTMLElement.prototype,'clientHeight','get').mockReturnValue(200)
  vi.spyOn(HTMLElement.prototype,'scrollHeight','get').mockImplementation(function(this:HTMLElement){return this.querySelectorAll('a').length>=3?2000:200})
})
afterEach(()=>{cleanup();window.history.replaceState({},'','/');sessionStorage.clear();localStorage.clear();vi.restoreAllMocks()})
function clampScroll(list:HTMLElement){
  let top=0
  Object.defineProperty(list,'scrollTop',{configurable:true,get:()=>top,set:(value:number)=>{top=Math.max(0,Math.min(value,list.scrollHeight-list.clientHeight))}})
  Object.defineProperty(list,'scrollHeight',{configurable:true,get:()=>list.querySelectorAll('a').length>=3?2000:200})
}
it('restores a fractional bottom offset when integer layout dimensions round down',()=>{
  vi.spyOn(HTMLElement.prototype,'scrollHeight','get').mockReturnValue(840)
  sessionStorage.setItem('capstone.session-navigation.scroll:workspace:active','640.5')
  const view=render(<SessionNavigation items={items}/>)
  const list=view.container.querySelector('.session-navigation-scroll') as HTMLElement
  expect(list.scrollTop).toBe(640.5)
})
it('holds the nearest available bottom while a shorter preparation list waits for full layout',async()=>{
  let height=800
  vi.spyOn(HTMLElement.prototype,'scrollHeight','get').mockImplementation(()=>height)
  sessionStorage.setItem('capstone.session-navigation.scroll:workspace:active','640.5')
  const view=render(<SessionNavigation items={items.slice(0,2)}/>)
  const list=view.container.querySelector('.session-navigation-scroll') as HTMLElement
  expect(list.scrollTop).toBe(600)
  fireEvent.scroll(list)
  expect(sessionStorage.getItem('capstone.session-navigation.scroll:workspace:active')).toBe('640.5')
  height=840
  view.rerender(<SessionNavigation items={items}/>)
  await waitFor(()=>expect(list.scrollTop).toBe(640.5))
})
it('captures End scrolling before routing even when its browser scroll event has not arrived',()=>{
  const view=render(<SessionNavigation items={items} currentId="a"/>)
  const list=view.container.querySelector('.session-navigation-scroll') as HTMLElement
  fireEvent.keyDown(list,{key:'End'})
  list.scrollTop=640
  fireEvent.click(screen.getByRole('link',{name:'会话b'}))
  expect(sessionStorage.getItem('capstone.session-navigation.scroll:workspace:active')).toBe('640')
  view.unmount()
  const next=render(<SessionNavigation items={items} currentId="b"/>)
  expect(next.container.querySelector('.session-navigation-scroll')?.scrollTop).toBe(640)
})
it('rejects cold-mount programmatic zero after restoration but accepts dragging the scrollbar',()=>{
  sessionStorage.setItem('capstone.session-navigation.scroll:workspace:active','640')
  const view=render(<SessionNavigation items={items}/>)
  const list=view.container.querySelector('.session-navigation-scroll') as HTMLElement
  expect(list.scrollTop).toBe(640)
  list.scrollTop=0;fireEvent.scroll(list)
  expect(sessionStorage.getItem('capstone.session-navigation.scroll:workspace:active')).toBe('640')
  expect(list.scrollTop).toBe(640)
  fireEvent.pointerDown(list)
  list.scrollTop=210;fireEvent.scroll(list)
  expect(sessionStorage.getItem('capstone.session-navigation.scroll:workspace:active')).toBe('210')
})
it('transfers the live global position between retained Activity lists before route effects run',()=>{
  function RetainedNavigation(){
    const [current,setCurrent]=useState('a')
    useEffect(()=>{const route=()=>setCurrent(new URLSearchParams(location.search).get('thread')??'a');window.addEventListener('popstate',route);return()=>window.removeEventListener('popstate',route)},[])
    return <>{['a','b'].map(id=><Activity key={id} mode={current===id?'visible':'hidden'}><SessionNavigation items={items} currentId={id}/></Activity>)}</>
  }
  const view=render(<RetainedNavigation/>)
  const lists=view.container.querySelectorAll<HTMLElement>('.session-navigation-scroll')
  fireEvent.keyDown(lists[0],{key:'End'});lists[0].scrollTop=640
  fireEvent.click(within(lists[0]).getByRole('link',{name:'会话b'}))
  expect(lists[1].scrollTop).toBe(640)
  lists[1].scrollTop=0;fireEvent.scroll(lists[1])
  expect(lists[1].scrollTop).toBe(640)
  fireEvent.pointerDown(lists[1]);lists[1].scrollTop=210;fireEvent.scroll(lists[1])
  fireEvent.click(within(lists[1]).getByRole('link',{name:'会话a'}))
  expect(lists[0].scrollTop).toBe(210)
})
it('defers archived position restoration until asynchronous rows can contain it',async()=>{
  let finish!:(page:{threads:typeof items;hasMore:boolean;nextBeforeThreadId:null})=>void
  const actions={rename:vi.fn(async()=>{}),archive:vi.fn(async()=>{}),remove:vi.fn(async()=>{}),archived:vi.fn(()=>new Promise<{threads:typeof items;hasMore:boolean;nextBeforeThreadId:null}>(resolve=>{finish=resolve}))}
  sessionStorage.setItem('capstone.session-navigation.scroll:workspace:archived','640')
  const view=render(<SessionNavigation items={items} actions={actions}/>)
  const list=view.container.querySelector('.session-navigation-scroll') as HTMLElement
  clampScroll(list)
  fireEvent.wheel(list);list.scrollTop=140;fireEvent.scroll(list)
  fireEvent.click(screen.getByRole('button',{name:'已归档会话'}))
  fireEvent.scroll(list)
  expect(sessionStorage.getItem('capstone.session-navigation.scroll:workspace:archived')).toBe('640')
  await act(async()=>finish({threads:items,hasMore:false,nextBeforeThreadId:null}))
  await waitFor(()=>expect(list.scrollTop).toBe(640))
  fireEvent.click(screen.getByRole('button',{name:'返回最近会话'}))
  expect(list.scrollTop).toBe(140)
})
it('defers an active position until late rows arrive instead of overwriting it with a clamped zero',async()=>{
  sessionStorage.setItem('capstone.session-navigation.scroll:workspace:active','640')
  const view=render(<SessionNavigation items={[]}/>)
  const list=view.container.querySelector('.session-navigation-scroll') as HTMLElement
  clampScroll(list);list.scrollTop=640;fireEvent.scroll(list)
  expect(sessionStorage.getItem('capstone.session-navigation.scroll:workspace:active')).toBe('640')
  view.rerender(<SessionNavigation items={items}/>)
  await waitFor(()=>expect(list.scrollTop).toBe(640))
})
it.each(['wheel','touchstart','keydown'])('lets user %s cancel a pending restore',async kind=>{
  sessionStorage.setItem('capstone.session-navigation.scroll:workspace:active','640')
  const view=render(<SessionNavigation items={[]}/>)
  const list=view.container.querySelector('.session-navigation-scroll') as HTMLElement
  clampScroll(list)
  if(kind==='keydown')fireEvent.keyDown(list,{key:'PageDown'})
  else fireEvent(list,new Event(kind,{bubbles:true}))
  fireEvent.scroll(list)
  view.rerender(<SessionNavigation items={items}/>)
  await act(async()=>{})
  expect(list.scrollTop).toBe(0)
  expect(sessionStorage.getItem('capstone.session-navigation.scroll:workspace:active')).toBe('0')
})
it('restores the global list position when a cached session becomes visible again',()=>{
  const view=render(<Activity mode="visible"><SessionNavigation items={items} currentId="a"/></Activity>)
  const list=view.container.querySelector('.session-navigation-scroll') as HTMLElement
  fireEvent.wheel(list);list.scrollTop=640;fireEvent.scroll(list)
  view.rerender(<Activity mode="hidden"><SessionNavigation items={items} currentId="a"/></Activity>)
  sessionStorage.setItem('capstone.session-navigation.scroll:workspace:active','860')
  view.rerender(<Activity mode="visible"><SessionNavigation items={items} currentId="b"/></Activity>)
  expect(list.scrollTop).toBe(860)
})
it('does not replace the global position with hidden layout zero during Activity teardown',()=>{
  const view=render(<Activity mode="visible"><SessionNavigation items={items}/></Activity>)
  const list=view.container.querySelector('.session-navigation-scroll') as HTMLElement
  fireEvent.wheel(list);list.scrollTop=640;fireEvent.scroll(list)
  Object.defineProperty(list,'clientHeight',{configurable:true,value:0})
  list.scrollTop=0
  view.rerender(<Activity mode="hidden"><SessionNavigation items={items}/></Activity>)
  expect(sessionStorage.getItem('capstone.session-navigation.scroll:workspace:active')).toBe('640')
  sessionStorage.setItem('capstone.session-navigation.scroll:workspace:active','860')
  Object.defineProperty(list,'clientHeight',{configurable:true,value:200})
  view.rerender(<Activity mode="visible"><SessionNavigation items={items}/></Activity>)
  expect(list.scrollTop).toBe(860)
})
it('does not reposition a scrolled list to the selected row during a session switch',()=>{
  const view=render(<SessionNavigation items={items} currentId="a"/>)
  const list=view.container.querySelector('.session-navigation-scroll') as HTMLElement
  Object.defineProperty(list,'getClientRects',{value:()=>[new DOMRect(0,0,200,200)]})
  Object.defineProperty(list,'getBoundingClientRect',{value:()=>new DOMRect(0,0,200,200)})
  Object.defineProperty(screen.getByRole('link',{name:'会话b'}),'getBoundingClientRect',{value:()=>new DOMRect(0,-100,180,20)})
  fireEvent.wheel(list);list.scrollTop=640;fireEvent.scroll(list)
  view.rerender(<SessionNavigation items={items} currentId="b"/>)
  expect(list.scrollTop).toBe(640)
})
it('reloads pins when a cached navigation becomes visible again',()=>{
  const view=render(<Activity mode="visible"><SessionNavigation items={items}/></Activity>)
  view.rerender(<Activity mode="hidden"><SessionNavigation items={items}/></Activity>)
  localStorage.setItem('capstone.session-pins:workspace',JSON.stringify(['c']))
  window.dispatchEvent(new Event('capstone-session-pins'))
  view.rerender(<Activity mode="visible"><SessionNavigation items={items}/></Activity>)
  expect(screen.getAllByRole('link')[0].textContent).toContain('会话c')
})
it('loads pins from the new namespace when the navigation scope changes',()=>{
  localStorage.setItem('capstone.session-pins:second',JSON.stringify(['c']))
  const view=render(<SessionNavigation items={items} storageKey="first"/>)
  view.rerender(<SessionNavigation items={items} storageKey="second"/>)
  expect(screen.getAllByRole('link')[0].textContent).toContain('会话c')
})
it('switches sessions without replacing the document and preserves ordinary modified links',()=>{
  const history=vi.spyOn(window.history,'pushState'),pop=vi.fn();window.addEventListener('popstate',pop)
  render(<SessionNavigation items={items} currentId="b" />)
  expect(screen.getByRole('link',{name:'会话b'}).getAttribute('aria-current')).toBe('page')
  fireEvent.click(screen.getByRole('link',{name:'会话c'}))
  expect(history).toHaveBeenCalledTimes(1);expect(pop).toHaveBeenCalledTimes(1)
  fireEvent.click(screen.getByRole('link',{name:'会话a'}),{ctrlKey:true})
  expect(history).toHaveBeenCalledTimes(1)
  history.mockRestore();window.removeEventListener('popstate',pop)
})
it('uses displayed ordering for adjacent sessions and disables boundaries',()=>{
  const view=render(<SessionAdjacentControls items={items} currentId="b" />)
  fireEvent.click(screen.getByRole('button',{name:'上一会话'}))
  expect(new URLSearchParams(window.location.search).get('thread')).toBe('a')
  view.rerender(<SessionAdjacentControls items={items} currentId="a" />)
  expect((screen.getByRole('button',{name:'上一会话'})as HTMLButtonElement).disabled).toBe(true)
  fireEvent.click(screen.getByRole('button',{name:'下一会话'}))
  expect(new URLSearchParams(window.location.search).get('thread')).toBe('b')
})
it('pins through the context menu and keeps the preference after remount',()=>{
  const view=render(<SessionNavigation items={items} currentId="b"/>)
  fireEvent.contextMenu(screen.getByRole('link',{name:'会话c'}),{clientX:20,clientY:40})
  fireEvent.click(screen.getByRole('menuitem',{name:'置顶'}))
  expect(screen.getAllByRole('link')[0].textContent).toContain('会话c')
  view.unmount();render(<SessionNavigation items={items} currentId="b"/>)
  expect(screen.getAllByRole('link')[0].textContent).toContain('会话c')
})
it('shows the host update timestamp in the session tooltip without substituting creation time',()=>{
  render(<SessionNavigation items={[{...items[0],createdAt:'2020-01-01T00:00:00Z',updatedAt:'2026-10-25T01:02:03Z'},items[1]]}/>)
  const title=screen.getByRole('link',{name:'会话a'}).getAttribute('title')!
  expect(title).toContain('最后更新：')
  expect(title).toContain('2026')
  expect(title).not.toContain('2020')
  expect(screen.getByRole('link',{name:'会话b'}).getAttribute('title')).toContain('最后更新：暂无记录')
})
it('loads older archived sessions and retains the first page',async()=>{
  const actions={rename:vi.fn(async()=>{}),archive:vi.fn(async()=>{}),remove:vi.fn(async()=>{}),archived:vi.fn()
    .mockResolvedValueOnce({threads:[items[0]],hasMore:true,nextBeforeThreadId:'a'})
    .mockResolvedValueOnce({threads:[items[2]],hasMore:false,nextBeforeThreadId:null})}
  render(<SessionNavigation items={items} actions={actions}/>)
  fireEvent.click(screen.getByRole('button',{name:'已归档会话'}))
  fireEvent.click(await screen.findByRole('button',{name:'读取更多归档会话'}))
  await waitFor(()=>expect(actions.archived).toHaveBeenLastCalledWith('a'))
  expect(await screen.findByRole('link',{name:'会话c'})).toBeTruthy()
  expect(screen.getByRole('link',{name:'会话a'})).toBeTruthy()
  expect(screen.queryByRole('button',{name:'读取更多归档会话'})).toBeNull()
})
it('restores an archived session before navigating and returns it to recent sessions',async()=>{
  let finish!:()=>void
  const actions={rename:vi.fn(async()=>{}),archive:vi.fn(()=>new Promise<void>(resolve=>{finish=resolve})),remove:vi.fn(async()=>{}),archived:vi.fn(async()=>({threads:[{...items[2],archived:true}],hasMore:false,nextBeforeThreadId:null}))}
  render(<SessionNavigation items={items.slice(0,2)} currentId="b" actions={actions}/>)
  fireEvent.click(screen.getByRole('button',{name:'已归档会话'}))
  fireEvent.click(await screen.findByRole('link',{name:'会话c'}))
  await waitFor(()=>expect(actions.archive).toHaveBeenCalledWith('c',false))
  expect(new URLSearchParams(location.search).get('thread')).toBeNull()
  await act(async()=>finish())
  await waitFor(()=>expect(new URLSearchParams(location.search).get('thread')).toBe('c'))
  expect(screen.getByRole('heading',{name:'最近会话'})).toBeTruthy()
  expect(screen.getByRole('link',{name:'会话c'})).toBeTruthy()
  expect(screen.queryByRole('button',{name:'返回最近会话'})).toBeNull()
})
it('keeps the archive and location unchanged when restoring a session fails',async()=>{
  const actions={rename:vi.fn(async()=>{}),archive:vi.fn(async()=>{throw new Error('offline')}),remove:vi.fn(async()=>{}),archived:vi.fn(async()=>({threads:[{...items[2],archived:true}],hasMore:false,nextBeforeThreadId:null}))}
  render(<SessionNavigation items={items.slice(0,2)} currentId="b" actions={actions}/>)
  fireEvent.click(screen.getByRole('button',{name:'已归档会话'}))
  fireEvent.click(await screen.findByRole('link',{name:'会话c'}))
  expect((await screen.findByRole('alert')).textContent).toContain('会话恢复失败')
  expect(screen.getByRole('button',{name:'返回最近会话'})).toBeTruthy()
  expect(new URLSearchParams(location.search).get('thread')).toBeNull()
})
it('restores active list scroll after visiting archived sessions',async()=>{
  const actions={rename:vi.fn(async()=>{}),archive:vi.fn(async()=>{}),remove:vi.fn(async()=>{}),archived:vi.fn(async()=>({threads:[items[2]],hasMore:false,nextBeforeThreadId:null}))}
  const view=render(<SessionNavigation items={items} actions={actions}/>)
  const list=view.container.querySelector('.session-navigation-scroll') as HTMLDivElement
  fireEvent.wheel(list);list.scrollTop=140;fireEvent.scroll(list)
  fireEvent.click(screen.getByRole('button',{name:'已归档会话'}))
  await screen.findByRole('link',{name:'会话c'})
  fireEvent.wheel(list);list.scrollTop=20;fireEvent.scroll(list)
  fireEvent.click(screen.getByRole('button',{name:'返回最近会话'}))
  expect(list.scrollTop).toBe(140)
})
it('ignores an older archive response after reopening the archive',async()=>{
  let resolveOld!:(page:{threads:typeof items;hasMore:boolean;nextBeforeThreadId:null})=>void
  const actions={rename:vi.fn(async()=>{}),archive:vi.fn(async()=>{}),remove:vi.fn(async()=>{}),archived:vi.fn()
    .mockImplementationOnce(()=>new Promise(resolve=>{resolveOld=resolve}))
    .mockResolvedValueOnce({threads:[items[2]],hasMore:false,nextBeforeThreadId:null})}
  render(<SessionNavigation items={items} actions={actions}/>)
  fireEvent.click(screen.getByRole('button',{name:'已归档会话'}))
  fireEvent.click(screen.getByRole('button',{name:'返回最近会话'}))
  fireEvent.click(screen.getByRole('button',{name:'已归档会话'}))
  await screen.findByRole('link',{name:'会话c'})
  await act(async()=>resolveOld({threads:[items[0]],hasMore:false,nextBeforeThreadId:null}))
  expect(screen.getByRole('link',{name:'会话c'})).toBeTruthy()
  expect(screen.queryByRole('link',{name:'会话a'})).toBeNull()
})
it('double-clicks to rename without navigation and supports archive recovery and confirmed deletion',async()=>{
  const actions={rename:vi.fn(async()=>{}),archive:vi.fn(async()=>{}),remove:vi.fn(async()=>{}),archived:vi.fn(async()=>({threads:[items[2]],hasMore:false,nextBeforeThreadId:null}))}
  render(<SessionNavigation items={items} currentId="b" actions={actions}/>)
  fireEvent.doubleClick(screen.getByRole('link',{name:'会话a'}))
  fireEvent.change(screen.getByRole('textbox',{name:'会话名称'}),{target:{value:'新的会话名称'}})
  fireEvent.submit(screen.getByRole('textbox',{name:'会话名称'}).closest('form')!)
  await waitFor(()=>expect(actions.rename).toHaveBeenCalledWith('a','新的会话名称'))
  expect(await screen.findByRole('link',{name:'新的会话名称'})).toBeTruthy()
  fireEvent.click(screen.getByRole('button',{name:'已归档会话'}))
  await waitFor(()=>expect(actions.archived).toHaveBeenCalled())
  const archived=await screen.findByRole('link',{name:'会话c'})
  fireEvent.contextMenu(archived)
  fireEvent.click(screen.getByRole('menuitem',{name:'恢复会话'}))
  await waitFor(()=>expect(actions.archive).toHaveBeenCalledWith('c',false))
  fireEvent.click(screen.getByRole('button',{name:'返回最近会话'}))
  fireEvent.contextMenu(screen.getByRole('link',{name:'会话c'}))
  fireEvent.click(screen.getByRole('menuitem',{name:'删除'}))
  expect(actions.remove).not.toHaveBeenCalled()
  fireEvent.click(within(screen.getByRole('alertdialog')).getByRole('button',{name:'删除'}))
  await waitFor(()=>expect(actions.remove).toHaveBeenCalledWith('c'))
})
