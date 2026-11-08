import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import CapstoneAssistantThread,{projectAssistantActivity} from './CapstoneAssistantThread'
import type {EventEnvelope} from './threadProtocol'

afterEach(()=>{cleanup();localStorage.clear();sessionStorage.clear()})
const record=(seq:number,native:string,activity?:Record<string,string>):EventEnvelope=>({
 eventId:'skill-'+seq,eventSeq:seq,eventVersion:1,eventType:'runtime_event',threadId:'thread',
 runId:'run',attemptId:'attempt',visibility:'public',occurredAt:'2026-11-08T00:00:00Z',
 payload:{native_type:native,task_id:'task',tool_name:'agent_skill',tool_call_id:'load',activity}})
it('restores skill loading and honest application details in the existing process view',()=>{
 const events=[{...record(0,''),eventType:'attempt_started',payload:{}},
  record(1,'tool_execution_start'),record(2,'tool_execution_end',{
  operation:'data-investigation · 已加载',output_excerpt:'方法已加载；尚不表示已应用或验证通过。 版本 sha256:abc'}),
  {...record(3,''),eventType:'attempt_completed',payload:{answer:'已保存阶段记录。'}}]
 const projected=projectAssistantActivity(events)
 expect(projected).toHaveLength(1)
 expect(projected[0].label).toBe('data-investigation')
 expect(projected[0].skillName).toBe('data-investigation')
 expect(projected[0].operation).toBe('data-investigation · 已加载')
 render(<CapstoneAssistantThread events={events} disabled={false} isRunning={false} activity={[]} onSend={async()=>{}} onCancel={async()=>{}}/>)
 fireEvent.click(screen.getByRole('button',{name:'查看执行过程'}))
 expect(screen.getAllByText(/data-investigation/).length).toBeGreaterThan(0)
 expect(screen.getAllByText(/尚不表示已应用或验证通过/).length).toBeGreaterThan(0)
 expect(document.querySelector('.capstone-chat-activity-item.is-skill')).toBeTruthy()
})
