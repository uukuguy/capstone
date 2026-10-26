import {afterEach,expect,it,vi} from 'vitest'
import {act,cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import CapstoneAssistantThread,{projectAssistantMessages} from './CapstoneAssistantThread'
import type {EventEnvelope} from './threadProtocol'
import ThinkingProcess,{projectInitialThinking} from './ThinkingProcess'

afterEach(()=>{cleanup();localStorage.clear()})
const event=(eventType:string,eventSeq:number,payload:Record<string,unknown>={},attemptId='thinking'):EventEnvelope=>({eventId:`e${eventSeq}`,eventType,eventSeq,eventVersion:1,threadId:'thread',runId:'run',attemptId,visibility:'public',occurredAt:`2026-10-25T12:00:${String(eventSeq).padStart(2,'0')}Z`,payload})
const accepted=event('command_accepted',1,{kind:'send_auto',payload:{text:'Current instruction'}})
const started=event('attempt_started',2)
const delta=event('assistant_thinking_delta',3,{text:'Actual public thought. '})
const props={disabled:false,isRunning:true,activity:[],onSend:async()=>{},onCancel:async()=>{}}

it('excludes acceptance queue time from thinking duration once execution starts',()=>{
  const thinking=projectInitialThinking([accepted,started,delta,event('attempt_completed',4,{answer:'Answer only.'})],'thinking')!
  expect(thinking.startedAt).toBe(started.occurredAt)
  render(<ThinkingProcess thinking={thinking} storageKey="duration"/>)
  expect(screen.getByRole('button',{name:'展开初始思考'}).textContent).toBe('Thinking · 2.0s')
})
it('deduplicates retained thinking and stops it at admitted organization without exposing other streams',()=>{
  const tool=event('tool_started',4,{tool_name:'read',tool_call_id:'read'})
  const later=event('assistant_thinking_delta',5,{text:'After reading.'})
  const privateText={...event('assistant_thinking_delta',6,{text:'PRIVATE'}),visibility:'diagnostic' as const}
  const other=event('assistant_thinking_delta',7,{text:'OTHER'},'other')
  const organized=event('runtime_action',8,{task_step:{id:'inspect',number:1,title:'Inspect',status:'running'}})
  const thinking=projectInitialThinking([accepted,started,delta,tool,later,later,privateText,other,organized,event('assistant_thinking_delta',9,{text:'TASK_OWNED'})],'thinking',4,8)!
  expect(thinking.text).toBe('Actual public thought. ')
  expect(thinking.continuationText).toBe('After reading.')
  expect(thinking.endedAt).toBe(tool.occurredAt)
})

it.each([false,true])('keeps thinking before the answer during streaming and after completion (tools=%s)',withTool=>{
  const {rerender}=render(<CapstoneAssistantThread {...props} events={[accepted,started,delta]}/>)
  const assertOrder=()=>{
    const message=document.querySelector('.is-assistant[data-attempt-id="thinking"]')!
    const thinking=message.querySelector('.capstone-thinking-process')!
    const answer=message.querySelector('.capstone-chat-body')!
    expect(message.querySelectorAll('.capstone-thinking-process')).toHaveLength(1)
    expect(thinking.compareDocumentPosition(answer)&Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  }
  assertOrder()
  const execution=withTool?[event('tool_started',4,{tool_name:'read',tool_call_id:'read'}),event('tool_completed',5,{tool_name:'read',tool_call_id:'read'})]:[]
  rerender(<CapstoneAssistantThread {...props} isRunning={false} events={[accepted,started,delta,...execution,event('attempt_completed',6,{answer:'Answer only.'})]}/>)
  assertOrder()
  expect(screen.getByRole('button',{name:'展开初始思考'}).getAttribute('aria-expanded')).toBe('false')
})

it('shows thinking during submit before any accepted or started event',async()=>{
  let finish!:()=>void
  const onSend=vi.fn(()=>new Promise<void>(resolve=>{finish=resolve}))
  render(<CapstoneAssistantThread {...props} isRunning={false} events={[]} onSend={onSend}/>)
  fireEvent.change(screen.getByRole('textbox',{name:'Thread 指令'}),{target:{value:'Current instruction'}})
  fireEvent.click(screen.getByRole('button',{name:'发送指令'}))
  expect((await screen.findByRole('region',{name:'思考状态'})).textContent).toContain('Thinking…')
  await act(async()=>finish())
})
it('shows queued thinking from acceptance before attempt_started',()=>{
  render(<CapstoneAssistantThread {...props} events={[accepted]}/>)
  expect(screen.getByRole('region',{name:'思考状态'}).textContent).toContain('Thinking…')
})
it('streams only public current-attempt thinking and keeps it out of the answer',()=>{
  const {rerender}=render(<CapstoneAssistantThread {...props} events={[accepted,started,delta]}/>)
  expect(within(screen.getByRole('region',{name:'思考状态'})).getByText('Actual public thought.')).toBeTruthy()
  const next=event('assistant_thinking_delta',4,{text:'More supplied text.'})
  const secret={...event('assistant_thinking_delta',5,{text:'PRIVATE_DIAGNOSTIC'}),visibility:'diagnostic' as const}
  const other=event('assistant_thinking_delta',6,{text:'OTHER_ATTEMPT'},'other')
  rerender(<CapstoneAssistantThread {...props} events={[accepted,started,delta,next,secret,other]}/>)
  const current=within(document.querySelector('.is-assistant[data-attempt-id="thinking"]') as HTMLElement)
  expect(current.getByRole('region',{name:'思考状态'}).textContent).toContain('Actual public thought. More supplied text.')
  expect(current.queryByText('OTHER_ATTEMPT')).toBeNull()
  expect(screen.queryByText('PRIVATE_DIAGNOSTIC')).toBeNull()
  const projected=projectAssistantMessages([accepted,started,delta,next,event('attempt_completed',7,{answer:'Answer only.'})])
  const answer=projected.find(message=>message.id==='assistant-thinking')!
  expect(JSON.stringify(answer.content)).not.toContain('Actual public thought')
  expect(JSON.stringify(answer.content)).toContain('Answer only.')
})
it('folds thinking at the first tool and retains later lightweight deltas in the same bounded record',()=>{
  const preparation=event('runtime_action',4,{task_step:{id:'task-preparation',number:1,title:'任务准备',status:'running'}})
  const goal=event('tool_completed',5,{tool_name:'agent_task_progress',tool_call_id:'goal',task_progress:{kind:'goal',text:'Recorded goal',refs:[]}})
  const nativeGoal={...event('runtime_event',5,{native_type:'tool_execution_end',task_id:'task',tool_name:'agent_task_progress',tool_call_id:'native-goal'}),eventId:'native-goal'}
  const {rerender}=render(<CapstoneAssistantThread {...props} events={[accepted,started,delta,preparation,goal,nativeGoal]}/>)
  expect(screen.getByRole('region',{name:'思考状态'}).textContent).toContain('Actual public thought.')
  const tool=event('tool_started',6,{tool_name:'read',tool_call_id:'read'})
  const executed=[accepted,started,delta,preparation,goal,nativeGoal,tool]
  rerender(<CapstoneAssistantThread {...props} events={executed}/>)
  const thinking=screen.getByRole('region',{name:'初始思考记录'})
  expect(within(thinking).getByRole('button',{name:'展开初始思考'}).textContent).toBe('Thinking · 4.0s')
  expect(screen.getByRole('region',{name:'工具调用过程'})).toBeTruthy()
  rerender(<CapstoneAssistantThread {...props} events={[...executed,event('tool_completed',7,{tool_name:'read',tool_call_id:'read'}),event('assistant_thinking_delta',8,{text:'LATER_TASK_THINKING'})]}/>)
  expect(screen.queryByRole('region',{name:'思考状态'})).toBeNull()
  expect(screen.queryByText('LATER_TASK_THINKING')).toBeNull()
  expect(screen.queryByText('当前记录未提供任务计划。')).toBeNull()
  fireEvent.click(screen.getByRole('button',{name:'放大阅读执行过程'}))
  const reader=within(screen.getByRole('dialog',{name:'执行过程'}))
  expect(reader.getByRole('region',{name:'初始思考记录'}).textContent).toContain('LATER_TASK_THINKING')
  expect(reader.getByRole('region',{name:'初始思考记录'}).textContent).toContain('Actual public thought.')
})
it('never shows a missing-thinking placeholder alongside supplied 823-character public thinking',()=>{
  const text='Public supplied thinking '.repeat(40).slice(0,823)
  render(<CapstoneAssistantThread {...props} events={[accepted,started,event('assistant_thinking_delta',3,{text})]}/>)
  expect(screen.getByRole('region',{name:'思考状态'}).textContent).toContain(text.trim())
  expect(screen.queryByText('当前记录未提供公开思考摘要。')).toBeNull()
})
it('uses one clickable muted trigger and no invented body while waiting for supplied text',()=>{
  render(<CapstoneAssistantThread {...props} events={[accepted,started]}/>)
  const region=within(screen.getByRole('region',{name:'思考状态'}))
  expect(region.getByRole('button',{name:'折叠初始思考'}).textContent).toBe('Thinking…')
  expect(region.queryByText('当前记录未提供公开思考摘要。')).toBeNull()
})
it('follows streamed text until the reader scrolls up and resumes only at the bottom',()=>{
  const thinking={text:'First supplied text',phase:'running' as const,handedOff:false}
  const {rerender}=render(<ThinkingProcess thinking={thinking} storageKey="scroll-test"/>)
  const body=document.querySelector('.capstone-thinking-copy') as HTMLElement
  Object.defineProperties(body,{scrollHeight:{value:400,configurable:true},clientHeight:{value:96,configurable:true}})
  rerender(<ThinkingProcess thinking={{...thinking,text:'More supplied text'}} storageKey="scroll-test"/>)
  expect(body.scrollTop).toBe(400)
  body.scrollTop=100;fireEvent.scroll(body)
  rerender(<ThinkingProcess thinking={{...thinking,text:'Another supplied delta'}} storageKey="scroll-test"/>)
  expect(body.scrollTop).toBe(100)
  body.scrollTop=304;fireEvent.scroll(body)
  Object.defineProperty(body,'scrollHeight',{value:600,configurable:true})
  rerender(<ThinkingProcess thinking={{...thinking,text:'Final supplied delta'}} storageKey="scroll-test"/>)
  expect(body.scrollTop).toBe(600)
})
it('hands off to recorded business steps without hiding the plan during later thinking',()=>{
  const step=event('runtime_action',4,{task_step:{id:'business-inspect',number:1,title:'Inspect selected business records',status:'running'}})
  const {rerender}=render(<CapstoneAssistantThread {...props} events={[accepted,started,delta,step]}/>)
  expect(screen.queryByRole('region',{name:'思考状态'})).toBeNull()
  expect(screen.getByText('Inspect selected business records')).toBeTruthy()
  rerender(<CapstoneAssistantThread {...props} events={[accepted,started,delta,step,event('assistant_thinking_delta',5,{text:'LATER_TASK_THINKING'})]}/>)
  expect(screen.getByText('Inspect selected business records')).toBeTruthy()
  expect(screen.queryByText('LATER_TASK_THINKING')).toBeNull()
})
it('keeps a goal-only progress note secondary when direct bash execution starts',()=>{
  const goal=event('tool_completed',3,{tool_name:'agent_task_progress',capability:'agent_task_progress',ok:true,tool_call_id:'goal',task_progress:{kind:'goal',text:'Recorded goal without a task plan',refs:[]}})
  const {rerender}=render(<CapstoneAssistantThread {...props} events={[accepted,goal]}/>)
  expect(screen.getByRole('region',{name:'思考状态'})).toBeTruthy()
  rerender(<CapstoneAssistantThread {...props} events={[accepted,goal,event('tool_started',4,{tool_name:'bash',tool_call_id:'bash-direct'})]}/>)
  expect(screen.queryByRole('region',{name:'思考状态'})).toBeNull()
  expect(screen.getByRole('region',{name:'工具调用过程'})).toBeTruthy()
  expect(screen.getByText('Recorded goal without a task plan')).toBeTruthy()
  expect(screen.queryByText('当前记录未提供任务计划。')).toBeNull()
})
it.each(['completed','failed','cancelled','interrupted'] as const)('auto-folds thinking at %s and permits manual reopening on replay',phase=>{
  const {rerender,unmount}=render(<CapstoneAssistantThread {...props} events={[accepted,started,delta]}/>)
  const terminal=event(`attempt_${phase}`,4,phase==='completed'?{answer:'Answer only.'}:{})
  rerender(<CapstoneAssistantThread {...props} isRunning={false} events={[accepted,started,delta,terminal]}/>)
  expect(screen.queryByText('Actual public thought.')).toBeNull()
  const region=screen.getByRole('region',{name:'思考状态'})
  expect(region.getAttribute('data-phase')).toBe(phase)
  expect(within(region).getByRole('button',{name:'展开初始思考'}).textContent).toBe('Thinking · 2.0s')
  fireEvent.click(within(region).getByRole('button',{name:'展开初始思考'}))
  expect(within(region).getByText('Actual public thought.')).toBeTruthy()
  unmount()
  render(<CapstoneAssistantThread {...props} isRunning={false} events={[accepted,started,delta,terminal]}/>)
  expect(within(screen.getByRole('region',{name:'思考状态'})).getByText('Actual public thought.')).toBeTruthy()
})
