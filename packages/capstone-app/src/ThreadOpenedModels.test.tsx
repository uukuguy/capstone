import { afterEach, expect, it } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import ThreadFixtureApp from './ThreadFixtureApp'
import { CapstoneThreadClient, type ThreadCommand } from './threadClient'
import { threadUiFixture } from './threadUiFixtures'

afterEach(cleanup)

function nativeClient() {
  const fixture = structuredClone(threadUiFixture('idle-ieee39'))
  const snapshot = fixture.snapshot as Record<string, unknown>
  let context = snapshot.active_model_context as Record<string, unknown>
  const models = ['ieee39', 'case57'].map((model_id) => ({ entry_id: `mdl_${model_id}`, model_id,
    model_revision: context.model_revision, implementation_family: 'pandapower', authority_model_ref: `gridctl:${model_id}`,
    display_name: model_id === 'ieee39' ? 'IEEE-39' : 'case57', diagram_provider_id: 'pandapower', last_active_seq: 0 }))
  let current = models[0].entry_id
  const events: Record<string, unknown>[] = []
  const commands: ThreadCommand[] = []
  const workspace = () => ({ schema: 'capstone-thread-model-workspace/1', thread_id: 'thr_demo_39', run_id: 'run_001',
    event_seq: events.length, current_entry_id: current, models, blocked_reason: null })
  const client = new CapstoneThreadClient({
    getSnapshot: async () => ({ ...snapshot, active_model_context: context, last_event_seq: events.length }),
    getModels: async () => workspace(),
    getCatalog: async () => ({ schema: 'capstone-thread-catalog/1', models: models.map(({ model_id, authority_model_ref, display_name, diagram_provider_id, implementation_family }) =>
      ({ model_id, authority_model_ref, display_name, diagram_provider_id, implementation_family })), profiles: [] }),
    readEvents: async (threadId, after) => ({ schema: 'capstone-thread-events/1', thread_id: threadId, after_event_seq: after,
      next_event_seq: events.length, has_more: false, events: events.filter((event) => Number(event.event_seq) > after) }),
    sendCommand: async (command) => {
      commands.push(command)
      const append = (event_type: string, payload: Record<string, unknown>) => events.push({ event_id: `evt_${events.length + 1}`,
        event_seq: events.length + 1, event_type, event_version: 1, thread_id: 'thr_demo_39', run_id: 'run_001',
        model_context_id: context.id, occurred_at: '2026-10-08T00:00:00Z', visibility: 'public', payload })
      if (command.kind === 'activate_model') {
        const target = models.find((model) => model.entry_id === command.payload.entry_id)!
        const previous = context
        context = { ...context, id: `ctx_${target.model_id}`, model_id: target.model_id }
        current = target.entry_id
        append('model_context_activated', { command_id: command.command_id, model_context: context,
          active_grid_page_id: `page_${target.model_id}`, previous_context: previous, previous_grid_page_id: `page_${previous.model_id}` })
        append('model_workspace_changed', { command_id: command.command_id, kind: command.kind, current_model_name: target.display_name })
      }
      return { schema: 'capstone-command-receipt/1', thread_id: command.thread_id, command_id: command.command_id,
        idempotency_key: command.idempotency_key, status: 'accepted', accepted_event_seq: events.length }
    },
  })
  return { client, commands }
}

it('changes an opened model with all tools disabled and creates no conversation Attempt', async () => {
  const { client, commands } = nativeClient()
  render(<ThreadFixtureApp client={client} threadId="thr_demo_39" disabledToolIds={['pandapower-static-analysis', 'pypsa-business-cases']} />)
  fireEvent.click(await screen.findByRole('button', { name: '当前模型：IEEE-39' }))
  fireEvent.click(screen.getByRole('button', { name: '设为当前模型：case57' }))
  await screen.findByRole('button', { name: '当前模型：case57' })
  expect(commands.map((command) => command.kind)).toEqual(['activate_model'])
  expect(document.querySelectorAll('[aria-label="用户指令"]')).toHaveLength(0)
  expect(await screen.findAllByText('当前模型已切换至 case57。')).toHaveLength(1)
})

it.each([
  ['切换至已打开的 case57 电网模型', ['activate_model']],
  ['切换至case57，然后分析母线情况', ['activate_model', 'send_auto']],
])('handles explicit control instruction %s once', async (text, kinds) => {
  const { client, commands } = nativeClient()
  render(<ThreadFixtureApp client={client} threadId="thr_demo_39" />)
  const input = await screen.findByRole('textbox', { name: 'Thread 指令' })
  await waitFor(() => expect((input as HTMLTextAreaElement).disabled).toBe(false))
  fireEvent.change(input, { target: { value: text } })
  fireEvent.click(screen.getByRole('button', { name: '发送指令' }))
  await waitFor(() => expect(commands.map((command) => command.kind)).toEqual(kinds))
  if (kinds.length > 1) {
    expect(commands[1].payload.text).toBe('分析母线情况')
    expect(commands[1].expected_event_seq).toBe(2)
  }
})
