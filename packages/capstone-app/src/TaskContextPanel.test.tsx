import {fireEvent,render,screen} from '@testing-library/react'
import {expect,it,vi} from 'vitest'
import TaskContextPanel from './TaskContextPanel'
import type {EventEnvelope} from './threadProtocol'

it('selects a saved instruction and compares its explicitly bound predecessor',()=>{
  const task={thread_id:'thread',work_id:'work'}
  const before={schema:'capstone-task-state/1',task,revision_ref:'first',previous_revision_ref:null,open_items:[]}
  const after={...before,revision_ref:'second',previous_revision_ref:'first',business_report:{completed:['Saved review']}}
  const event:EventEnvelope={eventId:'event',eventSeq:1,eventType:'attempt_completed',eventVersion:1,
    threadId:'thread',runId:'run',attemptId:'first',occurredAt:'2026-11-22T00:00:00Z',visibility:'public',
    payload:{work_id:'work',work:{task_state:before}}}
  const locate=vi.fn()
  render(<TaskContextPanel events={[event]} workId="work" work={{task_state:after}} labels={{first:'Check inputs',second:'Write review'}} onLocate={locate}/>)
  expect(screen.getByText('Saved review')).toBeTruthy()
  expect(screen.getByText('任务进展 · 新增')).toBeTruthy()
  fireEvent.click(screen.getByRole('button',{name:'定位指令'}))
  expect(locate).toHaveBeenCalledWith('second')
  fireEvent.change(screen.getByRole('combobox'),{target:{value:'first'}})
  expect(screen.getByText('没有已记录的前序任务修订。')).toBeTruthy()
})

it('shows one selection for retries of the same instruction',()=>{
  const task={thread_id:'thread',work_id:'work'}
  const state=(revision_ref:string,turn_id:string,previous_revision_ref:string|null)=>({
    schema:'capstone-task-state/1',task,revision_ref,previous_revision_ref,execution:{turn_id},
  })
  const events:EventEnvelope[]=[state('first','turn-1',null),state('failed','turn-2','first')].map((task_state,index)=>({
    eventId:'event-'+index,eventSeq:index+1,eventType:'attempt_completed',eventVersion:1,
    threadId:'thread',runId:'run',occurredAt:'2026-11-22T00:00:00Z',visibility:'public',
    payload:{work_id:'work',work:{task_state}},
  }))
  const {container}=render(<TaskContextPanel events={events} workId="work"
    work={{task_state:state('retry','turn-2','failed')}} labels={{failed:'Write review'}} onLocate={vi.fn()}/>)
  const select=container.querySelector('select')!
  expect([...select.options].map(option=>option.value)).toEqual(['turn-2','turn-1'])
  expect(select.options[0].textContent).toBe('Write review')
  const before=container.querySelector('.task-context-panel details')
  expect(before?.textContent).toContain('"revision_ref": "first"')
})
