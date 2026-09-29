import { describe, expect, it } from 'vitest'
import { listThreadFixtureIds, threadUiFixture } from './threadUiFixtures'

describe('thread UI fixtures', () => {
  it('exposes the four canonical state fixtures through one selector', () => {
    expect(listThreadFixtureIds()).toEqual([
      'idle-ieee39', 'historical-live-attempt', 'resync-required', 'interrupted-attempt',
    ])
    expect(threadUiFixture('idle-ieee39').snapshot).toMatchObject({
      thread_id: 'thr_demo_39', active_grid_page_id: 'page_ieee39', last_event_seq: 0,
    })
  })

  it('rejects unknown fixture ids instead of silently rendering a different state', () => {
    expect(() => threadUiFixture('unknown')).toThrow('unknown thread fixture')
  })
})
