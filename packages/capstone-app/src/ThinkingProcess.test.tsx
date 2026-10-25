import {afterEach,expect,it,vi} from 'vitest'
import {act,cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import CapstoneAssistantThread,{projectAssistantMessages} from './CapstoneAssistantThread'
import type {EventEnvelope} from './threadProtocol'

afterEach(()=>{cleanup();localStorage.clear()})
const event=(eventType:string,eventSeq:number,payload:Record<string,unknown>={},attemptId='thinking'):EventEnvelope=>({eventId:`e${eventSeq}`,eventType,eventSeq,eventVersion:1,threadId:'thread',runId:'run',attemptId,visibility:'public',occurredAt:`2026-10-25T12:00:${String(eventSeq).padStart(2,'0')}Z`,payload})
const accepted=event('command_accepted',1,{kind:'send_auto',payload:{text:'Current instruction'}})
const started=event('attempt_started',2)
const delta=event('assistant_thinking_delta',3,{text:'Actual public thought. '})
const props={disabled:false,isRunning:true,activity:[],onSend:async()=>{},onCancel:async()=>{}}

it('shows thinking during submit before any accepted or started event',async()=>{
  let finish!:()=>void
  const onSend=vi.fn(()=>new Promise<void>(resolve=>{finish=resolve}))
  render(<CapstoneAssistantThread {...props} isRunning={false} events={[]} onSend={onSend}/>)
  fireEvent.change(screen.getByRole('textbox',{name:'Thread 指令'}),{target:{value:'Current instruction'}})
  fireEvent.click(screen.getByRole('button',{name:'发送指令'}))
  expect((await screen.findByRole('region',{name:'思考状态'})).textContent).toContain('等待执行')
  await act(async()=>finish())
})
it('shows queued thinking from acceptance before attempt_started',()=>{
  render(<CapstoneAssistantThread {...props} events={[accepted]}/>)
  expect(screen.getByRole('region',{name:'思考状态'}).textContent).toContain('等待执行')
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
it('keeps thinking for lifecycle and goal-only notes, then archives it once actual execution starts',()=>{
  const preparation=event('runtime_action',4,{task_step:{id:'task-preparation',number:1,title:'任务准备',status:'running'}})
  const goal=event('tool_completed',5,{tool_name:'agent_task_progress',tool_call_id:'goal',task_progress:{kind:'goal',text:'Recorded goal',refs:[]}})
  const nativeGoal={...event('runtime_event',5,{native_type:'tool_execution_end',task_id:'task',tool_name:'agent_task_progress',tool_call_id:'native-goal'}),eventId:'native-goal'}
  const {rerender}=render(<CapstoneAssistantThread {...props} events={[accepted,started,delta,preparation,goal,nativeGoal]}/>)
  expect(screen.getByRole('region',{name:'思考状态'}).textContent).toContain('Actual public thought.')
  const tool=event('tool_started',6,{tool_name:'read',tool_call_id:'read'})
  const executed=[accepted,started,delta,preparation,goal,nativeGoal,tool]
  rerender(<CapstoneAssistantThread {...props} events={executed}/>)
  expect(screen.queryByRole('region',{name:'思考状态'})).toBeNull()
  expect(screen.queryByText('Actual public thought.')).toBeNull()
  expect(screen.getByRole('region',{name:'工具调用过程'})).toBeTruthy()
  rerender(<CapstoneAssistantThread {...props} events={[...executed,event('tool_completed',7,{tool_name:'read',tool_call_id:'read'}),event('assistant_thinking_delta',8,{text:'LATER_TASK_THINKING'})]}/>)
  expect(screen.queryByRole('region',{name:'思考状态'})).toBeNull()
  fireEvent.click(screen.getByRole('button',{name:'展开初始思考'}))
  expect(screen.getByText('Actual public thought.')).toBeTruthy()
  expect(screen.queryByText('LATER_TASK_THINKING')).toBeNull()
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
  fireEvent.click(within(region).getByRole('button',{name:'展开初始思考'}))
  expect(within(region).getByText('Actual public thought.')).toBeTruthy()
  unmount()
  render(<CapstoneAssistantThread {...props} isRunning={false} events={[accepted,started,delta,terminal]}/>)
  expect(within(screen.getByRole('region',{name:'思考状态'})).getByText('Actual public thought.')).toBeTruthy()
})
