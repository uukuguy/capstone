import {describe, expect, it} from 'vitest'
import {displaySessionTitle} from './sessionTitle'

describe('default session creation time', () => {
  it('uses the local time for a persisted UTC instant', () => {
    const date = new Date(2026, 9, 17, 20, 52, 30)
    const stamp = date.toISOString().replace('.000Z', 'Z')
    expect(displaySessionTitle({text:`通用聊天 · ${stamp}`,source:'default'})).toBe('通用聊天 · 10-17 20:52:30')
  })
  it('does not reinterpret user or automatic titles', () => {
    const text = '记录 · 2026-10-17T12:52:30Z'
    expect(displaySessionTitle({text,source:'user'})).toBe(text)
    expect(displaySessionTitle({text,source:'automatic'})).toBe(text)
  })
})
