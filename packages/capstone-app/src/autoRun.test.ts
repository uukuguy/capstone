import { describe, expect, it, vi } from 'vitest'
import { nextAutomaticAction, runAutomaticSession } from './autoRun'
import type { SessionStatus } from './types'

const ready: SessionStatus = {
  session_id: 'session-one', run_id: 'run-one', application_id: 'pypsa-business-cases',
  state: 'ready', error_code: null, accepted_turns: 0, completed_turns: 0,
}

describe('automatic run decisions', () => {
  it('starts once, then waits for the session to become ready', () => {
    expect(nextAutomaticAction(null, 3)).toBe('start')
    expect(nextAutomaticAction({ ...ready, state: 'pending' }, 3)).toBe('wait')
  })

  it('submits only the first uncommitted instruction', () => {
    expect(nextAutomaticAction(ready, 3)).toEqual({ submit: 1 })
    expect(nextAutomaticAction({ ...ready, accepted_turns: 1 }, 3)).toBe('wait')
    expect(nextAutomaticAction({ ...ready, accepted_turns: 1, completed_turns: 1 }, 3))
      .toEqual({ submit: 2 })
  })

  it('closes only after all committed answers and stops at terminal states', () => {
    expect(nextAutomaticAction({ ...ready, accepted_turns: 3, completed_turns: 3 }, 3))
      .toBe('close')
    for (const state of ['completed', 'failed', 'interrupted'] as const) {
      expect(nextAutomaticAction({ ...ready, state }, 3)).toBe('done')
    }
  })
})

describe('automatic session coordinator', () => {
  it('waits for each completed step to be presented before submitting the next one', async () => {
    const submitted: number[] = []
    const presented: number[] = []
    let releaseFirst: (() => void) | undefined
    const firstPresentation = new Promise<void>((resolve) => { releaseFirst = resolve })
    let completed = 0
    let closed = false
    const controller = new AbortController()
    const client = {
      createSession: async () => ({ session_id: 'session-one', run_id: null,
        application_id: 'pypsa-business-cases', state: 'pending' as const }),
      status: async () => ({ ...ready, state: closed ? 'completed' as const : 'ready' as const,
        accepted_turns: completed, completed_turns: completed }),
      submitTurn: async (_sid: string, _instruction: string, _key: string) => {
        submitted.push(++completed)
      },
      close: async () => { closed = true },
    }
    const run = runAutomaticSession(client, 'pypsa-business-cases', 'regional-demand-stress',
      ['第一步', '第二步'], null, controller.signal, new Map(), () => {}, () => {},
      async () => {}, async (_sid, ordinal) => {
        presented.push(ordinal)
        if (ordinal === 1) await firstPresentation
      })
    await vi.waitFor(() => expect(presented).toEqual([1]))
    expect(submitted).toEqual([1])
    releaseFirst?.()
    await run
    expect(submitted).toEqual([1, 2])
    expect(presented).toEqual([1, 2])
  })

  it('submits three registered instructions sequentially and closes once', async () => {
    const submitted: string[] = []
    const keys: string[] = []
    let committed = 0
    let closed = false
    const controller = new AbortController()
    const client = {
      createSession: async () => ({ session_id: 'session-one', run_id: null,
        application_id: 'pypsa-business-cases', state: 'pending' as const }),
      status: async () => ({ ...ready, state: closed ? 'completed' as const : 'ready' as const,
        accepted_turns: committed, completed_turns: committed }),
      submitTurn: async (_sid: string, instruction: string, key: string) => {
        submitted.push(instruction)
        keys.push(key)
        committed += 1
        return { session_id: 'session-one', ordinal: committed, state: 'accepted' }
      },
      close: async (_sid: string, key: string) => {
        keys.push(key)
        closed = true
        return { session_id: 'session-one', state: 'closing' }
      },
    }
    const created: string[] = []
    const completedSessionId = await runAutomaticSession(client, 'pypsa-business-cases', 'regional-demand-stress',
      ['打开模型', '建立情景', '比较结果'], null, controller.signal, new Map(),
      (session) => created.push(session.session_id), () => {}, async () => {})
    expect(created).toEqual(['session-one'])
    expect(completedSessionId).toBe('session-one')
    expect(submitted).toEqual(['打开模型', '建立情景', '比较结果'])
    expect(keys).toHaveLength(4)
    expect(new Set(keys).size).toBe(4)
    expect(closed).toBe(true)
  })

  it('stops future commands after the operator stops an accepted turn', async () => {
    const controller = new AbortController()
    const submitted: string[] = []
    const client = {
      createSession: async () => ({ session_id: 'session-one', run_id: null,
        application_id: 'pypsa-business-cases', state: 'pending' as const }),
      status: async () => ({ ...ready, accepted_turns: submitted.length,
        completed_turns: submitted.length }),
      submitTurn: async (_sid: string, instruction: string) => {
        submitted.push(instruction)
        controller.abort()
        return { session_id: 'session-one', ordinal: submitted.length, state: 'accepted' }
      },
      close: async () => ({ session_id: 'session-one', state: 'closing' }),
    }
    await runAutomaticSession(client, 'pypsa-business-cases', 'regional-demand-stress',
      ['打开模型', '建立情景'], null, controller.signal, new Map(), () => {}, () => {}, async () => {})
    expect(submitted).toEqual(['打开模型'])
  })
})
