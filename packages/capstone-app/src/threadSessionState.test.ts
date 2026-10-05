import { afterEach, describe, expect, it, vi } from 'vitest'
import { canReconnect, readDraft, readPendingCommands, reconnectDelay, rotateStorageNamespace, storageNamespace, writeDraft, writePendingCommands } from './threadSessionState'
import { ThreadTransportError } from './threadHttpTransport'
import { buildThreadCommand } from './threadClient'

afterEach(() => { sessionStorage.clear(); vi.restoreAllMocks() })

describe('Thread browser-session recovery', () => {
  const command = buildThreadCommand({ threadId: 'thr_one', runId: 'run_one', kind: 'send_auto',
    commandId: 'cmd_one', idempotencyKey: 'idem_one', expectedEventSeq: 17, payload: { text: 'original instruction' } })

  it('restores the exact unresolved envelope and guards the Thread identity', () => {
    writePendingCommands('one', [command])
    expect(readPendingCommands('one', 'thr_one')).toEqual([command])
    expect(readPendingCommands('one', 'thr_other')).toEqual([])
    expect(readDraft('one')).toBe('original instruction')
    writeDraft('one', 'newer unsent draft')
    expect(readDraft('one')).toBe('newer unsent draft')
    writePendingCommands('one', [])
    expect(readPendingCommands('one', 'thr_one')).toEqual([])
    expect(readDraft('one')).toBe('newer unsent draft')
  })

  it('separates API origins and rotates authentication sessions without embedding tokens', () => {
    const first = storageNamespace('https://one.example')
    expect(storageNamespace('https://one.example')).toBe(first)
    expect(storageNamespace('https://two.example')).not.toBe(first)
    rotateStorageNamespace()
    expect(storageNamespace('https://one.example')).not.toBe(first)
  })

  it('survives unavailable browser storage and rejects corrupt commands', () => {
    sessionStorage.setItem('one.commands', '{bad json')
    expect(readPendingCommands('one', 'thr_one')).toEqual([])
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('disabled') })
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('disabled') })
    expect(() => writeDraft('one', 'draft')).not.toThrow()
    expect(() => writePendingCommands('one', [command])).not.toThrow()
    expect(readDraft('one')).toBe('')
  })

  it('bounds retry intervals and stops on auth failures', () => {
    expect([0, 1, 2, 10].map(reconnectDelay)).toEqual([1000, 2000, 4000, 15000])
    expect(canReconnect(new ThreadTransportError(503, 'unavailable'))).toBe(true)
    expect(canReconnect(new ThreadTransportError(401, 'unauthorized'))).toBe(false)
    expect(canReconnect(new ThreadTransportError(403, 'forbidden'))).toBe(false)
    expect(canReconnect(new DOMException('cancelled', 'AbortError'))).toBe(false)
  })
})
