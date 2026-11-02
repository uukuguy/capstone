import {expect,it} from 'vitest'
import {instructionExecutionLabel} from './InstructionMarkers'

it('uses terminal state and recorded duration without inferring success from files',()=>{
  expect(instructionExecutionLabel('completed','293000')).toBe('✓ 已完成 · 4分53秒')
  expect(instructionExecutionLabel('failed','189000')).toBe('! 失败 · 3分9秒')
  expect(instructionExecutionLabel('cancelled','1000')).toBe('已取消 · 1秒')
  expect(instructionExecutionLabel(undefined,'1000')).toBe('')
})
it('updates running duration and does not invent missing timing',()=>{
  expect(instructionExecutionLabel('running',undefined,'2026-10-18T00:00:00Z',Date.parse('2026-10-18T00:00:12Z'))).toBe('运行中 · 12秒')
  expect(instructionExecutionLabel('failed')).toBe('! 失败')
})
