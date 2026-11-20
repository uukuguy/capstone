import {afterEach,expect,it,vi} from 'vitest'
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import CapstoneAssistantThread from './CapstoneAssistantThread'
import {MessageNotSentError} from '@assistant-ui/react'
afterEach(()=>{cleanup();sessionStorage.clear()})
it('submits through the ordinary composer and discards obsolete saved settings', async () => {
  const onSend = vi.fn(async (..._args: unknown[]) => { throw new MessageNotSentError('receipt unknown') })
  const props = {events: [], disabled: false, isRunning: false, activity: [], onSend, onCancel: async () => {}, storageKey: 'old-draft'}
  sessionStorage.setItem('old-draft.input', JSON.stringify({mode: 'capstone', deep_research: true, context: {include_refs: [], exclude_refs: []}}))
  const view = render(<CapstoneAssistantThread {...props}/>)
  expect(screen.queryByRole('button', {name: '深度研究'})).toBeNull()
  fireEvent.change(screen.getByRole('textbox', {name: 'Thread 指令'}), {target: {value: '保留未确认指令'}})
  fireEvent.click(screen.getByRole('button', {name: '发送指令'}))
  await waitFor(() => expect(onSend).toHaveBeenCalledOnce())
  expect(onSend.mock.calls[0]?.[2]).not.toHaveProperty('deep_research')
  view.unmount()
  render(<CapstoneAssistantThread {...props}/>)
  expect(screen.getByRole('textbox', {name: 'Thread 指令'})).toHaveProperty('value', '保留未确认指令')
})
