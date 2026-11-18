import {useState} from 'react'
import {afterEach,expect,it,vi} from 'vitest'
import {cleanup,fireEvent,render,screen,within,waitFor} from '@testing-library/react'
import {ExecutionDetailEntry,ExecutionDetailsContext,ExecutionDetailsSurface} from './ExecutionDetails'
import CapstoneAssistantThread from './CapstoneAssistantThread'

afterEach(cleanup)
function Example(){
  const [target,setTarget]=useState<HTMLDivElement|null>(null)
  const [tick,setTick]=useState(0)
  return <><ExecutionDetailsSurface onTarget={setTarget}/>
    <ExecutionDetailsContext.Provider value={{target,open:vi.fn()}}>
      <div aria-label="主会话"><ExecutionDetailEntry id="attempt-1" label="检查方案" status="已结束">
        <details><summary>工具记录</summary><p>原工具结果</p></details><p>完整回答 {tick}</p>
      </ExecutionDetailEntry></div>
    </ExecutionDetailsContext.Provider><button onClick={()=>setTick(tick+1)}>更新</button></>
}
it('keeps full records in the right reader and preserves folds across updates',()=>{
  render(<Example/>)
  const reader=screen.getByLabelText('执行详情记录')
  expect(within(reader).getByText('完整回答 0')).toBeTruthy()
  expect(within(screen.getByLabelText('主会话')).queryByText('完整回答 0')).toBeNull()
  const fold=within(reader).getByText('工具记录').closest('details')!
  fireEvent.click(within(reader).getByText('工具记录'))
  fireEvent.click(screen.getByText('更新'))
  expect(fold.open).toBe(true)
  expect(within(reader).getByText('完整回答 1')).toBeTruthy()
})
it('keeps the original reader inline when no right-panel context exists',()=>{
  render(<ExecutionDetailEntry id="old" label="旧记录" status="已结束"><p>历史回答</p></ExecutionDetailEntry>)
  expect(screen.getByText('历史回答')).toBeTruthy()
  expect(screen.queryByRole('button',{name:'查看执行详情'})).toBeNull()
})
it('does not drag a historical reader to the end when new content arrives',async()=>{
  render(<Example/>)
  const reader=screen.getByLabelText('执行详情记录')
  Object.defineProperties(reader,{clientHeight:{value:200},scrollHeight:{value:1000}})
  reader.scrollTop=100
  fireEvent.scroll(reader)
  fireEvent.click(screen.getByText('更新'))
  await waitFor(()=>expect(screen.getByText('有更新 · 回到当前')).toBeTruthy())
  expect(reader.scrollTop).toBe(100)
  fireEvent.click(screen.getByText('有更新 · 回到当前'))
  expect(reader.scrollTop).toBe(1000)
})
it('moves a real assistant answer into the same execution reader',()=>{
  const target=document.createElement('div')
  document.body.append(target)
  const open=vi.fn()
  const view=render(<ExecutionDetailsContext.Provider value={{target,open}}>
    <CapstoneAssistantThread events={[]} projectedMessages={[
      {id:'user-1',role:'user',content:[{type:'text',text:'检查方案'}]},
      {id:'assistant-1',role:'assistant',content:[{type:'text',text:'方案详细结论'}],status:{type:'complete',reason:'stop'},metadata:{custom:{attemptId:'a1',instruction:'检查方案',terminalPhase:'completed'}}}
    ]} disabled={false} isRunning={false} activity={[]} onSend={async()=>{}} onCancel={async()=>{}}/>
  </ExecutionDetailsContext.Provider>)
  expect(within(target).getByText('方案详细结论')).toBeTruthy()
  expect(within(view.container).queryByText('方案详细结论')).toBeNull()
  fireEvent.click(within(view.container).getByRole('button',{name:'查看执行详情'}))
  expect(open).toHaveBeenCalledOnce()
  view.unmount()
  target.remove()
})

it('keeps the committed core reply and recorded progress in the enterprise conversation',()=>{
  const target=document.createElement('div')
  document.body.append(target)
  const openNetwork=vi.fn()
  const view=render(<ExecutionDetailsContext.Provider value={{target,open:vi.fn(),inlineSummary:true}}>
    <CapstoneAssistantThread events={[]} networkAttemptIds={['a1']} onShowNetwork={openNetwork} projectedMessages={[
      {id:'assistant-1',role:'assistant',content:[{type:'text',text:`两项核验均通过。\n\n${'已核对原始数据。'.repeat(50)}\n\n完整核验依据。`}],
        status:{type:'complete',reason:'stop'},metadata:{custom:{attemptId:'a1',terminalPhase:'completed',
          coreReply:'核验均通过，报告附有原始数据。',
          taskSteps:[
            {id:'task-preparation',title:'任务准备',number:1,status:'completed'},
            {id:'task-execution',title:'执行任务',number:2,status:'completed'},
            {id:'task-finalization-1',title:'核验与结果整理',number:3,status:'completed'},
            {id:'validate-source',title:'核对源数据覆盖范围',number:4,status:'completed'},
          ],
          activities:[{id:'call1',label:'核验原始数据',source:'tool',status:'completed'},
            {id:'call2',label:'计算潮流',source:'tool',status:'completed'}]}}}
    ]} disabled={false} isRunning={false} activity={[]} onSend={async()=>{}} onCancel={async()=>{}}/>
  </ExecutionDetailsContext.Provider>)
  expect(within(view.container).getByText('核验均通过，报告附有原始数据。')).toBeTruthy()
  expect(within(view.container).queryByText('两项核验均通过。')).toBeNull()
  const process=within(view.container).getByLabelText('执行过程摘要')
  for(const title of ['任务准备','执行任务','核验与结果整理'])expect(within(process).queryByText(title)).toBeNull()
  expect(within(process).getByText('核对源数据覆盖范围')).toBeTruthy()
  for(const title of ['核验原始数据','计算潮流'])expect(within(process).getByText(title).closest('details')).toBeNull()
  fireEvent.click(within(view.container).getByRole('button',{name:'查看此指令电网图'}))
  expect(openNetwork).toHaveBeenCalledWith('a1')
  expect(within(view.container).queryByText('完整核验依据。')).toBeNull()
  expect(within(target).getByText('完整核验依据。')).toBeTruthy()
  view.unmount()
  target.remove()
})

it('replays the enterprise core reply and leaves legacy answers in the full reader',()=>{
  const target=document.createElement('div')
  document.body.append(target)
  const event=(seq:number,answer:string,summary?:string)=>({
    eventId:`event-${seq}`,eventSeq:seq,eventType:'attempt_completed',eventVersion:1,
    threadId:'thread',runId:'run',attemptId:`attempt-${seq}`,visibility:'public' as const,
    occurredAt:'2026-11-18T00:00:00Z',payload:{answer,answer_core_summary:summary},
  })
  const view=render(<ExecutionDetailsContext.Provider value={{target,open:vi.fn(),inlineSummary:true}}>
    <CapstoneAssistantThread events={[event(1,'历史正式答复'),event(2,'当前正式答复','当前核心结论')]}
      disabled={false} isRunning={false} activity={[]} onSend={async()=>{}} onCancel={async()=>{}}/>
  </ExecutionDetailsContext.Provider>)
  expect(within(view.container).getAllByLabelText('答复摘要')).toHaveLength(1)
  expect(within(view.container).getByText('当前核心结论')).toBeTruthy()
  expect(within(view.container).getAllByRole('button',{name:'查看正式回答与执行详情'})).toHaveLength(2)
  for(const answer of ['历史正式答复','当前正式答复']){
    expect(within(view.container).queryByText(answer)).toBeNull()
    expect(within(target).getByText(answer)).toBeTruthy()
  }
  view.unmount()
  target.remove()
})
