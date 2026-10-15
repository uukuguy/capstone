import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import ResearchEvidence, { parseResearchSnapshot } from './ResearchEvidence'

afterEach(cleanup)
const snapshot = { research_id: 'research-1', revision: 2, goal: '检查当前场景', condition_refs: [],
  claims: [{ claim_id: 'claim-1', statement: '该解释尚待核验', status: 'pending', refs: [] }],
  notes: [{ note_id: 'note-1', text: '计算未收敛，保留已完成部分', refs: ['evidence:one'] }],
  open_questions: ['还缺少哪些参数？'] }

describe('ResearchEvidence', () => {
  it('shows pending judgments and work notes as records rather than verified calculations', () => {
    render(<ResearchEvidence snapshot={parseResearchSnapshot(snapshot)} />)
    fireEvent.click(screen.getByText('研究判断与工作记录 · 修订 2'))
    expect(screen.getByText('待核验')).toBeTruthy()
    expect(screen.getByText('该解释尚待核验')).toBeTruthy()
    expect(screen.getByText('计算未收敛，保留已完成部分')).toBeTruthy()
    expect(screen.getByText('还缺少哪些参数？')).toBeTruthy()
    expect(screen.queryByText('核验通过')).toBeNull()
  })
  it('declines malformed snapshots and keeps supported status separate from source admission', () => {
    expect(parseResearchSnapshot({ ...snapshot, claims: [{ ...snapshot.claims[0], status: 'invented' }] })).toBeUndefined()
    expect(parseResearchSnapshot({ ...snapshot, claims: [{ ...snapshot.claims[0], status: 'supported', refs: [] }] })).toBeUndefined()
    render(<ResearchEvidence snapshot={undefined} />)
    expect(screen.queryByText(/研究判断/)).toBeNull()
  })
})
