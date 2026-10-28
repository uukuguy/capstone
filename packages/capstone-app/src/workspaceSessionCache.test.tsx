import {Activity,useRef} from 'react'
import {afterEach,expect,it,vi} from 'vitest'
import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {memorySessionLimit,readSessionVisits,recordSessionVisit,retainSessions,SessionCacheSetting,SessionReadingProvider,sessionObjectUrl,setMemorySessionLimit,useSessionObjectUrls,useSessionReadingPositions,useSessionViewState} from './workspaceSessionCache'
afterEach(()=>{cleanup();localStorage.clear();vi.unstubAllGlobals()})
it('keeps the current session and evicts the least recently visited session',()=>{
  expect(retainSessions(['a','b','c'],'a',3)).toEqual(['b','c','a'])
  expect(retainSessions(['b','c','a'],'d',3)).toEqual(['c','a','d'])
  expect(retainSessions(['a','b'],'a',1)).toEqual(['a'])
})
it('persists an adjustable limit and rejects invalid values',()=>{
  expect(memorySessionLimit()).toBe(10)
  render(<SessionCacheSetting/>)
  expect(screen.getAllByRole('option').map(option=>(option as HTMLOptionElement).value)).toEqual(['10','20','50'])
  fireEvent.change(screen.getByRole('combobox',{name:'最多同时保留会话'}),{target:{value:'50'}})
  expect(memorySessionLimit()).toBe(50)
  setMemorySessionLimit(5);expect(memorySessionLimit()).toBe(50)
  setMemorySessionLimit(Infinity);expect(memorySessionLimit()).toBe(50)
})
it('retains frequently switched sessions while aging out old popularity',()=>{
  const now=Date.UTC(2026,9,25),hour=3600000
  expect(retainSessions(['a','b'],'c',2,{a:{switches:8,lastOpenedAt:now-hour},b:{switches:1,lastOpenedAt:now-1000},c:{switches:1,lastOpenedAt:now}},now)).toEqual(['a','c'])
  expect(retainSessions(['a','b'],'c',2,{a:{switches:100,lastOpenedAt:now-7*24*hour},b:{switches:1,lastOpenedAt:now-1000},c:{switches:1,lastOpenedAt:now}},now)).toEqual(['b','c'])
})
it('persists real switch counts and the last open time without sharing access namespaces',()=>{
  const first=recordSessionVisit('alice',{},'a',1000)
  recordSessionVisit('alice',first,'a',2000)
  expect(readSessionVisits('alice').a).toEqual({switches:2,lastOpenedAt:2000})
  expect(readSessionVisits('bob')).toEqual({})
  localStorage.setItem('capstone.workspace.memory-sessions','5')
  expect(memorySessionLimit()).toBe(10)
})
function Reader(){
  const root=useRef<HTMLDivElement>(null)
  useSessionReadingPositions(root)
  const [selected,setSelected]=useSessionViewState('selected','report')
  return <div ref={root}><button onClick={()=>setSelected('metrics')}>{selected}</button><div data-reading-key="reader" data-testid="reader"/></div>
}
function WorkspaceReaders(){
  const root=useRef<HTMLDivElement>(null)
  useSessionReadingPositions(root)
  return <div ref={root}><aside className="workspace-navigation"><div data-reading-key="navigation" data-testid="navigation"/></aside><div data-reading-key="conversation" data-testid="conversation"/><div data-reading-key="products" data-testid="products"/></div>
}
it('excludes global navigation from session restore, scroll saving and pagehide snapshots',()=>{
  for(const [threadId,top] of [['a',130],['b',450]] as const){
    const key=`capstone.workspace.reading:global-navigation:${threadId}`
    localStorage.setItem(key,JSON.stringify({schema:1,values:{},positions:{'[data-reading-key="navigation"]':{top:300,left:0},'[data-reading-key="conversation"]':{top,left:0},'[data-reading-key="products"]':{top:top+20,left:0}}}))
    const view=render(<SessionReadingProvider namespace="global-navigation" threadId={threadId}><WorkspaceReaders/></SessionReadingProvider>)
    expect(screen.getByTestId('navigation').scrollTop).toBe(0)
    expect(screen.getByTestId('conversation').scrollTop).toBe(top)
    expect(screen.getByTestId('products').scrollTop).toBe(top+20)
    const navigation=screen.getByTestId('navigation')
    navigation.scrollTop=640;fireEvent.scroll(navigation)
    navigation.scrollTop=810
    window.dispatchEvent(new Event('pagehide'))
    expect(JSON.parse(localStorage.getItem(key)!).positions['[data-reading-key="navigation"]'].top).toBe(300)
    view.unmount()
    expect(JSON.parse(localStorage.getItem(key)!).positions['[data-reading-key="navigation"]'].top).toBe(300)
  }
})
it('restores lightweight reading state from disk after the retained view is removed',()=>{
  const first=render(<SessionReadingProvider namespace="test" threadId="a"><Reader/></SessionReadingProvider>)
  fireEvent.click(screen.getByRole('button',{name:'report'}))
  screen.getByTestId('reader').scrollTop=130
  first.unmount()
  render(<SessionReadingProvider namespace="test" threadId="b"><Reader/></SessionReadingProvider>)
  expect(screen.getByRole('button',{name:'report'})).toBeTruthy()
  cleanup()
  render(<SessionReadingProvider namespace="test" threadId="a"><Reader/></SessionReadingProvider>)
  expect(screen.getByRole('button',{name:'metrics'})).toBeTruthy()
  expect(screen.getByTestId('reader').scrollTop).toBe(130)
})
it('keeps preview URLs during hidden activity and releases them when the session is removed',()=>{
  const create=vi.fn(()=> 'blob:preview'),revoke=vi.fn()
  vi.stubGlobal('URL',class extends URL {static createObjectURL=create;static revokeObjectURL=revoke})
  let urls:Map<string,string>|undefined
  function Preview(){urls=useSessionObjectUrls();return <p>preview</p>}
  const view=render(<SessionReadingProvider namespace="test" threadId="a"><Activity mode="visible"><Preview/></Activity></SessionReadingProvider>)
  expect(sessionObjectUrl(urls,'product','one',new Uint8Array([1]),'application/pdf')).toBe('blob:preview')
  view.rerender(<SessionReadingProvider namespace="test" threadId="a"><Activity mode="hidden"><Preview/></Activity></SessionReadingProvider>)
  expect(revoke).not.toHaveBeenCalled()
  view.rerender(<SessionReadingProvider namespace="test" threadId="a"><Activity mode="visible"><Preview/></Activity></SessionReadingProvider>)
  sessionObjectUrl(urls,'product','one',new Uint8Array([1]),'application/pdf')
  expect(create).toHaveBeenCalledTimes(1)
  view.unmount();expect(revoke).toHaveBeenCalledWith('blob:preview')
})
