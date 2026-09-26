import { describe, expect, it, vi } from 'vitest'
import { commandKey } from './commandKey'

describe('command keys', () => {
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
