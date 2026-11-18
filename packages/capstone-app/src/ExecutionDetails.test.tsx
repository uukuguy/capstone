import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, within } from '@testing-library/react'
import CapstoneAssistantThread from './CapstoneAssistantThread'

afterEach(cleanup)

it('keeps the full process and reply in the conversation and anchors actions above the fold',()=>{
  const openNetwork=vi.fn()
  const view=render(<CapstoneAssistantThread inlineExecution events={[]} networkAttemptIds={['a1']} onShowNetwork={openNetwork}
    projectedMessages={[{id:'assistant-1',role:'assistant',content:[{type:'text',text:'完整核验依据。'}],
      status:{type:'complete',reason:'stop'},metadata:{custom:{attemptId:'a1',terminalPhase:'completed',
        coreReply:'核验通过。',startedAt:'2026-11-18T00:00:00Z',finishedAt:'2026-11-18T00:00:01Z',durationMs:1000,
        activities:[{id:'call1',label:'核验原始数据',source:'tool',status:'completed'}]}}}]}
    disabled={false} isRunning={false} activity={[]} onSend={async()=>{}} onCancel={async()=>{}}/>)
  const chat=within(view.container)
  expect(chat.getByLabelText('答复摘要').textContent).toBe('核验通过。')
  expect(chat.queryByLabelText('执行过程摘要')).toBeNull()
  expect(chat.queryByRole('button',{name:'查看执行详情'})).toBeNull()
  const process=chat.getByText('核验原始数据').closest('details')!
  const formal=chat.getByText('正式回答').closest('details')!
  const action=chat.getByRole('button',{name:'查看此指令电网图'})
  const header=view.container.querySelector('.capstone-answer-header')!
  expect(header.querySelector('time')).toBeTruthy()
  expect(header.compareDocumentPosition(chat.getByLabelText('答复摘要'))&Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  expect(formal.compareDocumentPosition(process)&Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  expect(formal.open).toBe(false)
  expect(action.compareDocumentPosition(formal)&Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  fireEvent.click(chat.getByText('正式回答'))
  expect(formal.open).toBe(true)
  expect(chat.getByRole('button',{name:'查看此指令电网图'})).toBe(action)
  fireEvent.click(action)
  expect(openNetwork).toHaveBeenCalledWith('a1')
})
