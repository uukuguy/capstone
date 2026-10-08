import { afterEach, describe, expect, it, vi } from 'vitest'
import { prepareWorkbench } from './workbenchPreparation'

afterEach(() => vi.unstubAllGlobals())
const frame = (component: string, status: string, complete = false) =>
  JSON.stringify({ schema: 'capstone-workbench-preparation/1', component, status, complete }) + '\n'

describe('workbench readiness stream', () => {
  it('publishes chunked component progress and admits only a completed ready stream', async () => {
    const text = frame('api', 'ready') + frame('database', 'ready')
      + frame('worker:pypsa', 'preparing') + frame('worker:pypsa', 'ready') + frame('workbench', 'ready', true)
    const encoder = new TextEncoder()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(new ReadableStream({ start(controller) {
      controller.enqueue(encoder.encode(text.slice(0, 19)))
      controller.enqueue(encoder.encode(text.slice(19)))
      controller.close()
    } }))))
    const updates = vi.fn()
    await prepareWorkbench('', new AbortController().signal, updates)
    expect(updates.mock.calls.map(([value]) => value)).toEqual([
      { component: 'api', status: 'ready' }, { component: 'database', status: 'ready' },
      { component: 'worker:pypsa', status: 'preparing' }, { component: 'worker:pypsa', status: 'ready' },
    ])
  })
  it.each([
    frame('api', 'ready') + frame('database', 'failed'),
    frame('api', 'ready') + frame('database', 'ready'),
    frame('api', 'ready') + frame('database', 'ready') + frame('worker:pypsa', 'preparing') + frame('workbench', 'ready', true),
  ])('does not admit failed, truncated or incomplete dependencies', async text => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(text)))
    await expect(prepareWorkbench('', new AbortController().signal, vi.fn())).rejects.toThrow()
  })
})
