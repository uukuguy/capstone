import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'
import { afterEach, describe, expect, it, vi } from 'vitest'
import InferenceEvidencePanel from './InferenceEvidencePanel'
import type { ResultProjection } from './threadProtocol'

const projection: ResultProjection = {
  resultId: 'projection_1', resultRef: 'result:checked', evidenceRefs: ['evidence:checked'],
  threadId: 'thread_1', runId: 'run_1', turnId: 'turn_1', attemptId: 'attempt_1',
  modelContextId: 'context_old', modelId: 'historical-model', modelRevision: 'revision:old',
  source: { capabilityId: 'constraints.violations', domainPackId: 'pack', implementationFamily: 'family' },
  status: 'partial', summary: [
    { metricId: 'checked', label: '已核验数值数', value: 8 },
    { metricId: 'unavailable', label: '未核验数值数', value: 3 },
  ], tables: [], elementRefs: [], unavailableReason: '部分指标缺少限值',
}
const props = {
  attemptId: 'attempt_1', admitted: true, resultRefs: ['result:checked'],
  evidenceRefs: ['evidence:checked'], projections: [projection], failures: [],
}
afterEach(cleanup)

describe('InferenceEvidencePanel', () => {
  it('retains actual call parameters and failure status without treating them as successful evidence', () => {
    render(<InferenceEvidencePanel {...props} executions={[{ id: 'call-1', tool: 'grid_analysis_run',
      capability: 'short_circuit.iec60909', ok: false, parameters: { case: 'max' },
      resultRefs: [], evidenceRefs: [], sequence: 7 }]} />)
    fireEvent.click(screen.getByText('调用参数与返回状态 · 1 项'))
    fireEvent.click(screen.getByText('短路电流 · 调用失败'))
    expect(screen.getByText(/"case": "max"/)).toBeVisible()
    expect(screen.getByText('call-1')).toBeVisible()
  })

  it('shows checked and unchecked values without presenting partial checks as full success', () => {
    render(<InferenceEvidencePanel {...props} />)
    fireEvent.click(screen.getByText('约束核验'))
    expect(screen.getByText('部分结果')).toBeTruthy()
    expect(screen.getByText('已核验数值数')).toBeTruthy()
    expect(screen.getByText('未核验数值数')).toBeTruthy()
    expect(screen.getByText('部分指标缺少限值')).toBeTruthy()
    expect(screen.queryByText('全部核验通过')).toBeNull()
    expect(screen.getByText('historical-model')).toBeTruthy()
    expect(screen.getByText('evidence:checked')).not.toBeVisible()
    fireEvent.click(screen.getByText('技术追溯 · 1 条证据'))
    expect(screen.getByText('evidence:checked')).toBeVisible()
  })

  it('links an admitted item to its exact calculation result', () => {
    const onSelectResult = vi.fn()
    render(<InferenceEvidencePanel {...props} onSelectResult={onSelectResult} />)
    fireEvent.click(screen.getByText('约束核验'))
    fireEvent.click(screen.getByRole('button', { name: '查看对应计算结果' }))
    expect(onSelectResult).toHaveBeenCalledWith('projection_1')
  })

  it('does not display unadmitted or foreign-attempt calculation facts', () => {
    render(<InferenceEvidencePanel {...props} admitted={false} projections={[
      projection, { ...projection, attemptId: 'other_attempt', resultId: 'foreign', modelId: 'foreign-model' },
    ]} />)
    expect(screen.queryByText('已核验数值数')).toBeNull()
    expect(screen.queryByText('historical-model')).toBeNull()
    expect(screen.queryByText('foreign-model')).toBeNull()
    expect(screen.queryByText('evidence:checked')).toBeNull()
  })

  it('excludes a historical projection even when it reuses the admitted result reference', () => {
    render(<InferenceEvidencePanel {...props} projections={[{ ...projection, attemptId: 'other_attempt' }]} />)
    expect(screen.queryByText('historical-model')).toBeNull()
    expect(screen.queryByText('已核验数值数')).toBeNull()
  })

  it('retains failed execution records without inventing an explanation or numerical evidence', () => {
    render(<InferenceEvidencePanel {...props} admitted={false} resultRefs={[]} evidenceRefs={[]} projections={[]}
      failures={[{ id: 'failure_1', kind: 'execution', tool: 'analysis.run', message: '', code: 'solver_failed', phase: 'execute', sequence: 7 }]} />)
    const record = screen.getByRole('region', { name: '执行失败记录' })
    expect(within(record).getByText('失败原因未提供')).toBeTruthy()
    expect(screen.queryByText('计算引用已准入')).toBeNull()
    expect(screen.queryByText(/短路电流为零/)).toBeNull()
    fireEvent.click(within(record).getByText('技术追溯'))
    expect(within(record).getByText('solver_failed')).toBeVisible()
  })

  it('preserves all admitted references, including references without result mappings', () => {
    const refs = Array.from({ length: 1024 }, (_, index) => `evidence:${index}`)
    render(<InferenceEvidencePanel {...props} projections={[]} resultRefs={[]} evidenceRefs={refs} />)
    fireEvent.click(screen.getByText('其他已准入引用 · 1024 条'))
    expect(screen.getByText('evidence:0')).toBeVisible()
    expect(screen.getByText('evidence:1023')).toBeVisible()
  })
})
