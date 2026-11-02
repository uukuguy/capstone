import { describe, expect, it, vi } from 'vitest'
import { commandKey, randomUuid } from './commandKey'

describe('command keys', () => {
  it('creates version 4 UUIDs without the secure-context UUID API', () => {
    const uuid = vi.spyOn(crypto, 'randomUUID').mockImplementation(() => { throw new Error('unavailable') })
    expect(randomUuid()).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/)
    expect(uuid).not.toHaveBeenCalled()
    uuid.mockRestore()
  })
  it('uses random bytes without relying on secure-context-only randomUUID', () => {
    const random = vi.spyOn(crypto, 'getRandomValues')
    const first = commandKey()
    const second = commandKey()
    expect(random).toHaveBeenCalledTimes(2)
    expect(first).toMatch(/^[0-9a-f]{32}$/)
    expect(second).not.toBe(first)
    random.mockRestore()
  })
})
