import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import CapstoneAssistantThread from './CapstoneAssistantThread'
import ThreadWorkspace from './ThreadWorkspace'
import SessionNavigation from './SessionNavigation'

afterEach(() => { cleanup(); sessionStorage.clear();localStorage.clear() })
it('keeps pinned sessions after collapsing and reopening the sidebar',()=>{
  localStorage.setItem('capstone.workspace.navigation-open','true')
  const items=['a','b'].map(threadId=>({threadId,modelId:null,sessionTitle:{text:`会话${threadId}`,source:'user' as const,revision:1,source_ref:null}}))
  render(<ThreadWorkspace conversationOnly sidebar={<SessionNavigation items={items}/>}/>)
  fireEvent.contextMenu(screen.getByRole('link',{name:'会话b'}))
  fireEvent.click(screen.getByRole('menuitem',{name:'置顶'}))
  const toggle=screen.getByRole('button',{name:'会话导航'})
  for(let i=0;i<3;i++){
    fireEvent.click(toggle);fireEvent.click(toggle)
    expect(screen.getAllByRole('link')[0].textContent).toBe('会话b')
    expect(JSON.parse(localStorage.getItem('capstone.session-pins:workspace')!)).toEqual(['b'])
  }
})
it('cancels inline rename with Escape while keeping the navigation open',()=>{
  localStorage.setItem('capstone.workspace.navigation-open','true')
  const rename=vi.fn(async()=>{})
  render(<ThreadWorkspace conversationOnly sidebar={<SessionNavigation items={[{threadId:'a',modelId:null,sessionTitle:{text:'测试会话',source:'user',revision:1,source_ref:null}}]} actions={{rename,archive:vi.fn(async()=>{}),remove:vi.fn(async()=>{}),archived:vi.fn(async()=>({threads:[],hasMore:false,nextBeforeThreadId:null}))}}/>}/>)
  fireEvent.contextMenu(screen.getByRole('link',{name:'测试会话'}))
  fireEvent.click(screen.getByRole('menuitem',{name:'改名'}))
  const input=screen.getByRole('textbox',{name:'会话名称'})
  fireEvent.change(input,{target:{value:'不保存的名称'}})
  fireEvent.keyDown(input,{key:'Escape'})
  expect(screen.getByRole('button',{name:'会话导航'}).getAttribute('aria-expanded')).toBe('true')
  expect(screen.queryByRole('textbox',{name:'会话名称'})).toBeNull()
  expect(screen.getByRole('link',{name:'测试会话'})).toBeTruthy()
  expect(rename).not.toHaveBeenCalled()
})

it('keeps both sidebars independently visible and remembers navigation width and visibility',()=>{
  localStorage.setItem('capstone.workspace.navigation-open','true')
  const view=render(<ThreadWorkspace conversationOnly sidebar={<p>会话列表</p>} resourcePanel={<p>成果内容</p>} resourcePanelOpen><p>对话</p></ThreadWorkspace>)
  const toggle=screen.getByRole('button',{name:'会话导航'})
  expect(toggle.getAttribute('aria-expanded')).toBe('true')
  const divider=screen.getByRole('separator',{name:'调整会话栏宽度'})
  fireEvent.keyDown(divider,{key:'ArrowRight'})
  expect(divider.getAttribute('aria-valuenow')).toBe('232')
  fireEvent.click(toggle)
  expect(toggle.getAttribute('aria-expanded')).toBe('false')
  expect(document.querySelector('.has-resource-panel')).toBeTruthy()
  view.unmount()
  render(<ThreadWorkspace conversationOnly sidebar={<p>会话列表</p>} resourcePanel={<p>成果内容</p>} resourcePanelOpen />)
  expect(screen.getByRole('button',{name:'会话导航'}).getAttribute('aria-expanded')).toBe('false')
  fireEvent.click(screen.getByRole('button',{name:'会话导航'}))
  expect(screen.getByRole('separator',{name:'调整会话栏宽度'}).getAttribute('aria-valuenow')).toBe('232')
})

it('closes overlay navigation with its button, outside area and Escape without closing products', () => {
  localStorage.setItem('capstone.workspace.navigation-open','false')
  render(<ThreadWorkspace conversationOnly resourcePanel={<p>结果表</p>} resourcePanelOpen sidebar={<p>会话列表</p>}><p>对话</p></ThreadWorkspace>)
  const toggle=screen.getByRole('button',{name:'会话导航'})
  for(const action of ['button','outside','escape']) {
    fireEvent.click(toggle)
    expect(toggle.getAttribute('aria-expanded')).toBe('true')
    if(action==='button')fireEvent.click(screen.getByRole('button',{name:'收起会话导航'}))
    else if(action==='outside')fireEvent.click(screen.getByRole('button',{name:'关闭会话导航遮罩'}))
    else fireEvent.keyDown(window,{key:'Escape'})
    expect(toggle.getAttribute('aria-expanded')).toBe('false')
    expect(document.querySelector('.has-resource-panel')).toBeTruthy()
    expect(document.activeElement).toBe(toggle)
  }
})

it('clamps a narrow window without replacing the preferred split and can reset it', () => {
  localStorage.clear()
  let width=1600
  const rect=vi.spyOn(HTMLElement.prototype,'getBoundingClientRect').mockImplementation(()=>({x:0,y:0,left:0,top:0,width,height:800,right:width,bottom:800,toJSON:()=>({})}))
  render(<ThreadWorkspace conversationOnly resourcePanel={<p>结果表</p>} resourcePanelOpen><p>对话</p></ThreadWorkspace>)
  const separator=screen.getByRole('separator')
  fireEvent.keyDown(separator,{key:'End'})
  expect(separator.getAttribute('aria-valuenow')).toBe('70')
  width=800;fireEvent.resize(window)
  expect(Number(separator.getAttribute('aria-valuenow'))).toBeLessThan(70)
  expect(localStorage.getItem('capstone.workspace.conversation-share')).toBe('70')
  width=1600;fireEvent.resize(window)
  expect(separator.getAttribute('aria-valuenow')).toBe('70')
  fireEvent.click(screen.getByRole('button',{name:'恢复默认比例'}))
  expect(separator.getAttribute('aria-valuenow')).toBe('60')
  rect.mockRestore();localStorage.clear()
})

it('bounds pointer resizing and keeps the split when the product workspace is expanded', () => {
  localStorage.clear()
  vi.stubGlobal('PointerEvent', MouseEvent)
  const rect=vi.spyOn(HTMLElement.prototype,'getBoundingClientRect').mockReturnValue({x:0,y:0,left:0,top:0,width:1000,height:800,right:1000,bottom:800,toJSON:()=>({})})
  const parentMove=vi.fn()
  render(<div onPointerMove={parentMove}><ThreadWorkspace conversationOnly resourcePanel={<p>结果表</p>} resourcePanelOpen><p>对话</p></ThreadWorkspace></div>)
  const separator=screen.getByRole('separator')
  fireEvent.pointerDown(separator,{button:0,clientX:450})
  fireEvent.pointerMove(separator,{clientX:900})
  expect(separator.getAttribute('aria-valuenow')).toBe('63')
  expect(parentMove).not.toHaveBeenCalled()
  fireEvent.pointerUp(separator)
  fireEvent.click(screen.getByRole('button',{name:'扩大成果区'}))
  expect(document.querySelector('.is-resource-expanded')).toBeTruthy()
  fireEvent.click(screen.getByRole('button',{name:'恢复左右布局'}))
  expect(separator.getAttribute('aria-valuenow')).toBe('63')
  rect.mockRestore();vi.unstubAllGlobals();localStorage.clear()
})

it('lets the keyboard resize and restore the conversation/product split', () => {
  localStorage.clear()
  const view=render(<ThreadWorkspace conversationOnly resourcePanel={<p>真实成果</p>} resourcePanelOpen><p>对话</p></ThreadWorkspace>)
  const separator=screen.getByRole('separator',{name:'调整对话与成果宽度'})
  expect(separator.getAttribute('aria-valuenow')).toBe('60')
  fireEvent.keyDown(separator,{key:'ArrowRight'})
  expect(separator.getAttribute('aria-valuenow')).toBe('62')
  view.unmount()
  render(<ThreadWorkspace conversationOnly resourcePanel={<p>真实成果</p>} resourcePanelOpen><p>对话</p></ThreadWorkspace>)
  expect(screen.getByRole('separator').getAttribute('aria-valuenow')).toBe('62')
  localStorage.clear()
})

it('uses the existing chat and composer for persisted Work messages without execution or model controls', async () => {
  const send = vi.fn(async () => {})
  render(<CapstoneAssistantThread events={[]} projectedMessages={[{ id: 'work_one-message-0', role: 'user', content: '已保存的目标' }]}
    disabled={false} isRunning={false} activity={[]} onSend={send} onCancel={async () => {}}
    composerMode="text" emptyState={<p>描述工作目标</p>} runtimeStatus="已保存，未执行"
    composerLabel="任务目标" sendLabel="保存任务" />)
  expect(screen.getByText('已保存的目标')).toBeTruthy()
  expect(screen.queryByText('实时响应')).toBeNull()
  expect(screen.queryByRole('button', { name: '选择技能' })).toBeNull()
  fireEvent.change(screen.getByRole('textbox', { name: '任务目标' }), { target: { value: '补充资料' } })
  fireEvent.click(screen.getByRole('button', { name: '保存任务' }))
  await waitFor(() => expect(send).toHaveBeenCalledWith('automatic', '补充资料'))
  expect(screen.queryByText('正在生成回答…')).toBeNull()
})
