import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { StrictMode } from 'react'
import ThreadLiveEntry from './ThreadLiveEntry'
import App from './App'
import { threadUiFixture } from './threadUiFixtures'
import {navigateSession} from './sessionNavigationState'
import {setMemorySessionLimit} from './workspaceSessionCache'

afterEach(() => {
  cleanup()
  window.history.replaceState({}, '', '/')
  sessionStorage.removeItem('capstone.thread.operatorToken')
  localStorage.clear()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

const snapshot = {
  schema: 'capstone-thread-snapshot/1', thread_id: 'thr_demo_39',
  run: { run_id: 'run_001', state: 'open' },
  active_model_context: {
    id: 'ctx_ieee39_7', model_id: 'ieee39', model_revision: '7',
    implementation_family: 'pandapower', selection_revision: 'sel_2',
  },
  active_grid_page_id: 'page_ieee39', current_attempt: null,
  last_event_seq: 0, base_event_seq: 0,
}

describe('ThreadLiveEntry', () => {
  it('retains each visited session conversation and resource DOM across switches and new-session entry',async()=>{
    const streams:{id:string;signal?:AbortSignal|null}[]=[]
    let firstReplay=true
    let releaseOther!:()=>void
    const otherReady=new Promise<void>(resolve=>{releaseOther=resolve})
    const fetcher=vi.fn(async(url:string|URL,_init?:RequestInit)=>{
      const path=String(url),id=path.match(/\/threads\/(thr_[a-z0-9_]+)/)?.[1]??'thr_demo_39'
      if(path.endsWith('/thread-access'))return new Response(JSON.stringify({schema:'capstone-thread-access/1',mode:'open'}))
      if(path.includes('/threads?'))return new Response(JSON.stringify({schema:'capstone-thread-list/1',threads:['thr_demo_39','thr_other'].map((thread_id,index)=>({thread_id,model_id:'ieee39',implementation_family:'pandapower',created_at:'2026-11-17',archived:false,last_event_seq:0,session_title:{text:index?'会话乙':'会话甲',source:'user',revision:1,source_ref:null}})),has_more:false,next_before_thread_id:null}),{headers:{'Capstone-Thread-Version':'2'}})
      if(path.endsWith('/workbench-preparation')||path.endsWith('/models')||path.endsWith('/input-catalog'))return new Response('',{status:404})
      if(path.endsWith('/catalog')||path.endsWith('/thread-catalog'))return new Response(JSON.stringify(threadUiFixture('idle-ieee39').catalog))
      if(path.endsWith('/metadata'))return new Response(JSON.stringify({archived:false}))
      if(path.includes('/events/stream')){streams.push({id,signal:_init?.signal});return new Response(new ReadableStream({start(){}}))}
      if(path.includes('/history?'))return new Response(JSON.stringify({schema:'capstone-thread-history/1',thread_id:id,before_event_seq:1,next_before_event_seq:1,has_more:false,events:[]}))
      if(path.includes('/events?')){
        if(id==='thr_demo_39'&&firstReplay){firstReplay=false;await new Promise(resolve=>setTimeout(resolve,100))}
        return new Response(JSON.stringify({schema:'capstone-thread-events/1',thread_id:id,after_event_seq:0,next_event_seq:0,has_more:false,events:[]}))
      }
      if(path.endsWith('/threads/thr_other'))await otherReady
      return new Response(JSON.stringify({...snapshot,thread_id:id}))
    })
    vi.stubGlobal('fetch',fetcher)
    render(<ThreadLiveEntry threadId="thr_demo_39" presentation="workspace" />)
    const composer=await screen.findByRole('textbox',{name:'Thread 指令'})
    const navigation=screen.getByRole('complementary',{name:'工作空间导航'})
    const sessionList=navigation.querySelector('.session-navigation')
    const footer=navigation.querySelector('.workspace-navfoot')
    const firstRow=await screen.findByRole('link',{name:/^会话甲/})
    const secondRow=screen.getByRole('link',{name:/^会话乙/})
    const listScroll=navigation.querySelector('.session-navigation-scroll') as HTMLElement
    listScroll.scrollTop=87
    const catalogReads=()=>fetcher.mock.calls.filter(([url])=>String(url).includes('/threads?')).length
    // Rendering the composer does not mean history replay and SSE startup finished.
    await waitFor(()=>expect(streams.find(stream=>stream.id==='thr_demo_39')).toBeDefined())
    const initialStream=streams.find(stream=>stream.id==='thr_demo_39')!
    expect(initialStream.signal?.aborted).toBe(false)
    fireEvent.click(screen.getByRole('button',{name:'打开电气拓扑'}))
    fireEvent.click(screen.getByRole('button',{name:'全屏'}))
    const viewport=document.querySelector('.capstone-chat-viewport') as HTMLElement
    const resource=screen.getByRole('complementary',{name:'电气拓扑'})
    const initialCatalogReads=catalogReads()
    viewport.scrollTop=123;resource.querySelector('.workspace-product-paper')!.scrollTop=67
    await act(async()=>fireEvent.click(secondRow))
    expect(screen.getByRole('complementary',{name:'工作空间导航'})).toBe(navigation)
    expect(navigation.querySelector('.session-navigation')).toBe(sessionList)
    expect(navigation.querySelector('.workspace-navfoot')).toBe(footer)
    expect(screen.getByRole('link',{name:/^会话甲/})).toBe(firstRow)
    expect(screen.getByRole('link',{name:/^会话乙/})).toBe(secondRow)
    expect(firstRow.getAttribute('aria-current')).toBeNull()
    expect(secondRow.getAttribute('aria-current')).toBe('page')
    expect(listScroll.scrollTop).toBe(87)
    expect(screen.getByText('正在准备会话…')).toBeTruthy()
    expect(catalogReads()).toBe(initialCatalogReads)
    await act(async()=>releaseOther())
    await waitFor(()=>expect(screen.getByRole('textbox',{name:'Thread 指令'})).not.toBe(composer))
    await waitFor(()=>expect(initialStream.signal?.aborted).toBe(true))
    expect(screen.getByRole('complementary',{name:'工作空间导航'})).toBe(navigation)
    expect(catalogReads()).toBe(initialCatalogReads)
    await act(async()=>navigateSession('thr_demo_39'))
    await waitFor(()=>expect(screen.getByRole('textbox',{name:'Thread 指令'})).toBe(composer))
    expect(viewport.scrollTop).toBe(123)
    expect(screen.getByRole('complementary',{name:'电气拓扑'})).toBe(resource)
    expect(resource.querySelector('.workspace-product-paper')!.scrollTop).toBe(67)
    expect(screen.getByRole('button',{name:'恢复左右布局'})).toBeTruthy()
    await act(async()=>navigateSession('new'))
    await screen.findByRole('heading',{name:'新建任务会话'})
    expect(screen.getByRole('complementary',{name:'工作空间导航'})).toBe(navigation)
    await act(async()=>navigateSession('thr_demo_39'))
    await waitFor(()=>expect(screen.getByRole('textbox',{name:'Thread 指令'})).toBe(composer))
    expect(viewport.scrollTop).toBe(123)
    await act(async()=>setMemorySessionLimit(10))
    const clock=vi.spyOn(Date,'now').mockReturnValue(Date.now()+7*86400000)
    for(let i=0;i<10;i++){
      const previous=screen.getByRole('textbox',{name:'Thread 指令'})
      await act(async()=>navigateSession(`thr_other_${i}`))
      await waitFor(()=>expect(screen.getByRole('textbox',{name:'Thread 指令'})).not.toBe(previous))
    }
    expect(composer.isConnected).toBe(false)
    expect(screen.getByRole('complementary',{name:'工作空间导航'})).toBe(navigation)
    expect(navigation.querySelector('.session-navigation')).toBe(sessionList)
    await act(async()=>navigateSession('thr_demo_39'))
    const restored=await screen.findByRole('textbox',{name:'Thread 指令'})
    expect(restored).not.toBe(composer)
    await waitFor(()=>expect(screen.getByRole('button',{name:'恢复左右布局'})).toBeTruthy())
    expect((restored.closest('.capstone-assistant-thread')!.querySelector('.capstone-chat-viewport') as HTMLElement).scrollTop).toBe(123)
    expect(screen.getByRole('complementary',{name:'电气拓扑'}).querySelector('.workspace-product-paper')!.scrollTop).toBe(67)
    expect(fetcher.mock.calls.filter(([, init])=>(init as RequestInit|undefined)?.method==='POST')).toHaveLength(1)
    clock.mockRestore()
  },15000)
  it('opens conversation content while the independent catalog request is pending',async()=>{
    let releaseCatalog!:(response:Response)=>void
    const catalog=new Promise<Response>(resolve=>{releaseCatalog=resolve})
    vi.stubGlobal('fetch',vi.fn(async(url:string|URL)=>{
      const path=String(url)
      if(path.endsWith('/thread-access'))return new Response(JSON.stringify({schema:'capstone-thread-access/1',mode:'open'}))
      if(path.includes('/threads?'))return catalog
      if(path.endsWith('/catalog')||path.endsWith('/thread-catalog'))return new Response(JSON.stringify(threadUiFixture('idle-ieee39').catalog))
      if(path.endsWith('/metadata'))return new Response(JSON.stringify({archived:false}))
      if(path.includes('/events/stream'))return new Response(new ReadableStream({start(){}}))
      if(path.includes('/history?'))return new Response(JSON.stringify({schema:'capstone-thread-history/1',thread_id:'thr_demo_39',before_event_seq:1,next_before_event_seq:1,has_more:false,events:[]}))
      if(path.includes('/events?'))return new Response(JSON.stringify({schema:'capstone-thread-events/1',thread_id:'thr_demo_39',after_event_seq:0,next_event_seq:0,has_more:false,events:[]}))
      if(path.endsWith('/workbench-preparation')||path.endsWith('/models')||path.endsWith('/input-catalog'))return new Response('',{status:404})
      return new Response(JSON.stringify(snapshot))
    }))
    render(<ThreadLiveEntry threadId="thr_demo_39" presentation="workspace"/>)
    const composer=await screen.findByRole('textbox',{name:'Thread 指令'})
    const navigation=screen.getByRole('complementary',{name:'工作空间导航'})
    const list=navigation.querySelector('.session-navigation')
    await act(async()=>releaseCatalog(new Response(JSON.stringify({schema:'capstone-thread-list/1',threads:[{thread_id:'thr_catalog_late',model_id:'ieee39',implementation_family:'pandapower',created_at:'2026-11-17',archived:false,last_event_seq:0,session_title:{text:'后台目录到达',source:'user',revision:1,source_ref:null}}],has_more:false,next_before_thread_id:null}),{headers:{'Capstone-Thread-Version':'2'}})))
    await screen.findByRole('link',{name:/^后台目录到达/})
    expect(screen.getByRole('textbox',{name:'Thread 指令'})).toBe(composer)
    expect(screen.getByRole('complementary',{name:'工作空间导航'})).toBe(navigation)
    expect(navigation.querySelector('.session-navigation')).toBe(list)
  })
  it('starts the independent catalog after operator authentication at the new-session entry',async()=>{
    window.history.replaceState({},'','/?thread=new')
    const fetcher=vi.fn(async(url:string|URL)=>{
      const path=String(url)
      if(path.endsWith('/thread-access'))return new Response(JSON.stringify({schema:'capstone-thread-access/1',mode:'operator'}))
      if(path.includes('/threads?'))return new Response(JSON.stringify({schema:'capstone-thread-list/1',threads:[],has_more:false,next_before_thread_id:null}),{headers:{'Capstone-Thread-Version':'2'}})
      return new Response('',{status:404})
    })
    vi.stubGlobal('fetch',fetcher)
    render(<ThreadLiveEntry threadId="new" presentation="workspace"/>)
    const input=await screen.findByLabelText('Operator token')
    const namespace=sessionStorage.getItem('capstone.thread.storageSession')
    fireEvent.change(input,{target:{value:'test-only-operator'}})
    fireEvent.click(screen.getByRole('button',{name:/^连接$/}))
    await waitFor(()=>expect(fetcher.mock.calls.some(([url])=>String(url).includes('/threads?'))).toBe(true))
    expect(sessionStorage.getItem('capstone.thread.storageSession')).not.toBe(namespace)
  })
  it('keeps the workspace navigation and a new-session exit when the selected session is missing',async()=>{
    vi.stubGlobal('fetch',vi.fn(async(url:string|URL)=>{
      if(String(url).endsWith('/thread-access'))return new Response(JSON.stringify({schema:'capstone-thread-access/1',mode:'open'}))
      if(String(url).includes('/threads?'))return new Response(JSON.stringify({schema:'capstone-thread-list/1',threads:[],has_more:false,next_before_thread_id:null}),{headers:{'Capstone-Thread-Version':'2'}})
      return new Response(JSON.stringify({detail:'thread not found'}),{status:404})
    }))
    render(<ThreadLiveEntry threadId="thr_missing" presentation="workspace" />)
    expect(await screen.findByText('此会话不存在或已删除。请从左侧选择其他会话，或新建会话。')).toBeTruthy()
    expect(screen.getByRole('button',{name:'会话导航'})).toBeTruthy()
    expect(screen.getByRole('button',{name:'新建会话'})).toBeTruthy()
    expect(document.querySelector('.thread-token-shell')).toBeNull()
  })
  it('opens a version-one host without version echo in the shared workspace with complete input tools', async () => {
    const fetcher = vi.fn(async (url: string | URL, init?: RequestInit) => {
      const path = String(url)
      if (path.endsWith('/workbench-preparation')) return new Response('', {status:404})
      if (path.endsWith('/thread-access')) return new Response(JSON.stringify({schema:'capstone-thread-access/1', mode:'open'}))
      if (path.includes('/threads?')) return new Response(JSON.stringify({schema:'capstone-thread-list/1',threads:[],has_more:false,next_before_thread_id:null}))
      if (path.endsWith('/catalog')||path.endsWith('/thread-catalog')) return new Response(JSON.stringify(threadUiFixture('idle-ieee39').catalog))
      if (path.endsWith('/models') || path.endsWith('/input-catalog')) return new Response('', {status:404})
      if (path.endsWith('/metadata')) return new Response(JSON.stringify({archived:false}))
      if (path.includes('/events/stream')) return new Response(new ReadableStream({start(){}}))
      if (path.includes('/history?')) return new Response(JSON.stringify({schema:'capstone-thread-history/1',thread_id:'thr_demo_39',before_event_seq:1,next_before_event_seq:1,has_more:false,events:[]}))
      if (path.includes('/events?')) return new Response(JSON.stringify({schema:'capstone-thread-events/1',thread_id:'thr_demo_39',after_event_seq:0,next_event_seq:0,has_more:false,events:[]}))
      return new Response(JSON.stringify(snapshot))
    })
    vi.stubGlobal('fetch', fetcher)
    render(<ThreadLiveEntry threadId="thr_demo_39" presentation="workspace" />)
    expect(await screen.findByRole('navigation', {name:'任务会话'})).toBeTruthy()
    expect(await screen.findByRole('button', {name:'深度研究'})).toBeTruthy()
    expect(screen.queryByRole('button', {name:'本轮上下文'})).toBeNull()
    expect(screen.queryByRole('button', {name:'开始任务'})).toBeNull()
    expect(screen.queryByRole('button', {name:'保存任务'})).toBeNull()
    const composer=screen.getByRole('textbox',{name:'Thread 指令'})
    fireEvent.change(composer,{target:{value:'仍在当前会话的草稿'}})
    fireEvent.click(screen.getByRole('button',{name:'新建会话'}))
    await screen.findByRole('button',{name:'重试创建'})
    expect(screen.getByRole('textbox',{name:'Thread 指令'})).toBe(composer)
    expect((composer as HTMLTextAreaElement).value).toBe('仍在当前会话的草稿')
    expect(screen.queryByRole('dialog',{name:'新建会话'})).toBeNull()
    expect(fetcher.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(1)
  })
  it('shows actual startup progress and hides all input until preparation completes', async () => {
    let stream: ReadableStreamDefaultController<Uint8Array>
    const encoder = new TextEncoder()
    const fetcher = vi.fn(async (url: string | URL) => {
      if (String(url).endsWith('/workbench-preparation')) return new Response(new ReadableStream({ start(controller) { stream = controller } }))
      return new Response(JSON.stringify({ schema: 'capstone-thread-access/1', mode: 'operator' }))
    })
    vi.stubGlobal('fetch', fetcher)
    render(<ThreadLiveEntry threadId="new" />)
    const push = (component: string, status: string, complete = false) =>
      stream.enqueue(encoder.encode(JSON.stringify({ schema: 'capstone-workbench-preparation/1', component, status, complete }) + '\n'))
    await act(async () => { push('api', 'ready'); push('database', 'ready'); push('worker:pypsa', 'preparing') })
    expect(screen.getByText('PyPSA 计算工具')).toBeTruthy()
    expect(screen.getByText('准备中')).toBeTruthy()
    expect(screen.queryByRole('textbox')).toBeNull()
    expect(fetcher).toHaveBeenCalledTimes(1)
    await act(async () => { push('worker:pypsa', 'ready'); push('workbench', 'ready', true) })
    expect(await screen.findByLabelText('Operator token')).toBeTruthy()
    expect(screen.queryByLabelText('工作台准备进度')).toBeNull()
    expect(fetcher.mock.calls.map(([url]) => String(url))).toEqual(['/api/v1/workbench-preparation', '/api/v1/thread-access'])
  })
  it('opens the workspace without a token and creates one Thread under StrictMode', async () => {
    window.history.replaceState({},'','/?thread=new')
    const fetcher = vi.fn(async (url: string | URL, init?: RequestInit) => {
      if (String(url).endsWith('/workbench-preparation')) return new Response('', { status: 404 })
      if (String(url).endsWith('/thread-access')) return new Response(JSON.stringify({ schema: 'capstone-thread-access/1', mode: 'open' }))
      if (String(url).includes('/history?')) return new Response(JSON.stringify({ schema: 'capstone-thread-history/1',
        thread_id: 'thr_demo_39', before_event_seq: 1, next_before_event_seq: 1, has_more: false, events: [] }))
      if (String(url).includes('/events/stream')) return new Response(new ReadableStream({ start() {} }))
      if (String(url).includes('/events?after=')) return new Response(JSON.stringify({
        schema: 'capstone-thread-events/1', thread_id: 'thr_demo_39', after_event_seq: 0, next_event_seq: 0, has_more: false, events: [],
      }))
      if (init?.method === 'POST') expect(init.headers).not.toHaveProperty('Authorization')
      return new Response(JSON.stringify(snapshot))
    })
    vi.stubGlobal('fetch', fetcher)
    render(<StrictMode><App /></StrictMode>)
    expect(await screen.findByRole('region', { name: '电网模型区' })).toBeTruthy()
    expect(screen.queryByRole('textbox', { name: 'Operator token' })).toBeNull()
    expect(sessionStorage.getItem('capstone.thread.operatorToken')).toBeNull()
    expect(fetcher.mock.calls.filter(([url, init]) => String(url) === '/api/v1/threads' && init?.method === 'POST')).toHaveLength(1)
  })

  it('creates a new conversation from a visible button without typing a URL', async () => {
    sessionStorage.setItem('capstone.thread.operatorToken', 'private-token')
    const fetcher = vi.fn(async (url: string | URL, init?: RequestInit) => {
      if (String(url).endsWith('/workbench-preparation')) return new Response('', { status: 404 })
      if (String(url).endsWith('/thread-access')) return new Response(JSON.stringify({ schema: 'capstone-thread-access/1', mode: 'operator' }))
      if (String(url).endsWith('/catalog')) return new Response(JSON.stringify(threadUiFixture('idle-ieee39').catalog))
      if (String(url).endsWith('/models')) return new Response('', { status: 404 })
      const id = init?.method === 'POST' ? 'thr_second' : 'thr_demo_39'
      if (String(url).includes('/history?')) return new Response(JSON.stringify({ schema: 'capstone-thread-history/1',
        thread_id: String(url).includes('thr_second') ? 'thr_second' : 'thr_demo_39', before_event_seq: 1, next_before_event_seq: 1, has_more: false, events: [] }))
      if (String(url).includes('/events/stream')) return new Response(new ReadableStream({ start() {} }))
      if (String(url).includes('/events?after=')) return new Response(JSON.stringify({
        schema: 'capstone-thread-events/1', thread_id: String(url).includes('thr_second') ? 'thr_second' : 'thr_demo_39',
        after_event_seq: 0, next_event_seq: 0, has_more: false, events: [],
      }))
      return new Response(JSON.stringify({ ...snapshot, thread_id: String(url).includes('thr_second') ? 'thr_second' : id }))
    })
    vi.stubGlobal('fetch', fetcher)
    render(<ThreadLiveEntry threadId="thr_demo_39" />)
    await screen.findByRole('region', { name: '电网模型区' })
    fireEvent.click(screen.getByRole('button', { name: '对话设置' }))
    await waitFor(() => expect((screen.getByRole('checkbox', { name: 'PyPSA 电网分析' }) as HTMLInputElement).disabled).toBe(false))
    fireEvent.click(screen.getByRole('checkbox', { name: 'PyPSA 电网分析' }))
    fireEvent.click(screen.getByRole('button', { name: '保存工具选择' }))
    fireEvent.click(screen.getByRole('button', { name: '新建对话' }))
    await waitFor(() => expect(new URLSearchParams(window.location.search).get('thread')).toBe('thr_second'))
    expect(fetcher.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(1)
    expect(await screen.findByRole('region', { name: '电网模型区' })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: '对话设置' }))
    expect((screen.getByRole('checkbox', { name: 'PyPSA 电网分析' }) as HTMLInputElement).checked).toBe(false)
    expect((screen.getByRole('checkbox', { name: 'pandapower 静态分析' }) as HTMLInputElement).checked).toBe(true)
    window.history.pushState({}, '', '/?thread=thr_demo_39')
    act(() => window.dispatchEvent(new PopStateEvent('popstate')))
    await screen.findByRole('region', { name: '电网模型区' })
    fireEvent.click(screen.getByRole('button', { name: '对话设置' }))
    expect((screen.getByRole('checkbox', { name: 'PyPSA 电网分析' }) as HTMLInputElement).checked).toBe(false)
  })

  it('loads a real Thread workspace through HTTP snapshot, page, and SSE adapters', async () => {
    sessionStorage.setItem('capstone.thread.operatorToken', 'private-token')
    vi.stubGlobal('fetch', vi.fn(async (url: string | URL) => {
      if (String(url).endsWith('/workbench-preparation')) return new Response('', { status: 404 })
      if (String(url).endsWith('/thread-access')) return new Response(JSON.stringify({ schema: 'capstone-thread-access/1', mode: 'operator' }))
      if (String(url).includes('/history?')) return new Response(JSON.stringify({ schema: 'capstone-thread-history/1',
        thread_id: 'thr_demo_39', before_event_seq: 1, next_before_event_seq: 1, has_more: false, events: [] }))
      if (String(url).includes('/events/stream')) return new Response('', { status: 200 })
      if (String(url).includes('/events?after=')) return new Response(JSON.stringify({
        schema: 'capstone-thread-events/1', thread_id: 'thr_demo_39',
        after_event_seq: 0, next_event_seq: 0, has_more: false, events: [],
      }), { status: 200 })
      return new Response(JSON.stringify(snapshot), { status: 200 })
    }))

    render(<ThreadLiveEntry threadId="thr_demo_39" />)

    expect(await screen.findByRole('region', { name: '电网模型区' })).toBeTruthy()
    expect(screen.getByText('ieee39 · pandapower')).toBeTruthy()
  })

  it('creates a default IEEE-39 Thread only once under StrictMode', async () => {
    sessionStorage.setItem('capstone.thread.operatorToken', 'private-token')
    const fetcher = vi.fn(async (url: string | URL, init?: RequestInit) => {
      if (String(url).endsWith('/workbench-preparation')) return new Response('', { status: 404 })
      if (String(url).endsWith('/thread-access')) return new Response(JSON.stringify({ schema: 'capstone-thread-access/1', mode: 'operator' }))
      if (String(url).includes('/history?')) return new Response(JSON.stringify({ schema: 'capstone-thread-history/1',
        thread_id: 'thr_demo_39', before_event_seq: 1, next_before_event_seq: 1, has_more: false, events: [] }))
      if (String(url) === '/api/v1/threads' && init?.method === 'POST') {
        expect(init.body).toBe(JSON.stringify({ model_id: 'ieee39' }))
        return new Response(JSON.stringify(snapshot), { status: 201 })
      }
      if (String(url).includes('/events/stream')) return new Response('', { status: 200 })
      if (String(url).includes('/events?after=')) return new Response(JSON.stringify({
        schema: 'capstone-thread-events/1', thread_id: 'thr_demo_39',
        after_event_seq: 0, next_event_seq: 0, has_more: false, events: [],
      }), { status: 200 })
      return new Response(JSON.stringify(snapshot), { status: 200 })
    })
    vi.stubGlobal('fetch', fetcher)

    const first = render(<StrictMode><ThreadLiveEntry threadId="new" /></StrictMode>)

    expect(await screen.findByRole('region', { name: '电网模型区' })).toBeTruthy()
    expect(fetcher).toHaveBeenCalledWith('/api/v1/threads', expect.objectContaining({ method: 'POST' }))
    expect(fetcher.mock.calls.filter(([url, init]) => url === '/api/v1/threads' && init?.method === 'POST')).toHaveLength(1)
    expect(new URLSearchParams(window.location.search).get('thread')).toBe('thr_demo_39')
    first.unmount()
    render(<App />)
    expect(await screen.findByRole('region', { name: '电网模型区' })).toBeTruthy()
    expect(fetcher.mock.calls.filter(([url, init]) => url === '/api/v1/threads' && init?.method === 'POST')).toHaveLength(1)
  })
})
