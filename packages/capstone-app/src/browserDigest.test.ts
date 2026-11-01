import {afterEach, expect, it, vi} from 'vitest'
import {sha256Hex} from './browserDigest'

afterEach(() => vi.unstubAllGlobals())
it('verifies SHA-256 without secure-context browser APIs', async () => {
  vi.stubGlobal('crypto', {})
  expect(await sha256Hex(new TextEncoder().encode('abc'))).toBe('ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad')
})
