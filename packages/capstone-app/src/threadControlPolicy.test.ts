import { expect, it } from 'vitest'
import { controlPolicy, OperationGate } from './threadControlPolicy'

it.each(['configuration', 'submitting', 'uncertain', 'running', 'unavailable'] as const)('allows draft edits but freezes send and selection during %s', phase => {
  expect(controlPolicy(phase)).toEqual({ editDraft: true, configure: false, send: false, retry: false })
})
it('allows idle controls and only retry after an interrupted attempt', () => {
  expect(controlPolicy('idle')).toEqual({ editDraft: true, configure: true, send: true, retry: true })
  expect(controlPolicy('interrupted').retry).toBe(true)
  expect(controlPolicy('interrupted').send).toBe(false)
})
it.each(['send', 'configure'] as const)('holds a synchronous owner across same-tick %s-first callbacks', first => {
  const gate = new OperationGate()
  const token = gate.acquire(true)
  expect(token).toBeTruthy()
  expect(gate.acquire(true)).toBeUndefined()
  expect(gate.owns(token)).toBe(true)
  gate.release(Symbol(first))
  expect(gate.acquire(true)).toBeUndefined()
  gate.release(token!)
  expect(gate.acquire(false)).toBeUndefined()
  expect(gate.acquire(true)).toBeTruthy()
})
