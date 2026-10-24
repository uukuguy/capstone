import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import AttemptRecordPanel from './AttemptRecordPanel'
import type { AttemptRecords } from './attemptRecords'
afterEach(cleanup)

describe('AttemptRecordPanel', () => {
  it('gives clear empty feedback only after an explicit read finishes', async () => {
    const read = vi.fn().mockResolvedValue({ threadId: 'thr_1', attemptId: 'attempt_empty', instruction: '', modelContext: null, events: [], nextAfter: 0, hasMore: false })
    render(<AttemptRecordPanel attemptId="attempt_empty" read={read} />)
    expect(read).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: '读取原任务记录' }))
    expect(await screen.findByText('此任务没有可读的原始指令、模型或执行记录。')).toBeTruthy()
    expect(screen.queryByRole('button', { name: '读取后续记录' })).toBeNull()
  })
  it('reads on demand, keeps the original model and omits private model text', async () => {
    const read = vi.fn().mockResolvedValue({ threadId: 'thr_1', attemptId: 'attempt_old',
      instruction: '原始任务', modelContext: { id: 'ctx_old', modelId: 'ieee39', modelRevision: 'rev_old',
        implementationFamily: 'pandapower', selectionRevision: 'sel_old', enabledProfiles: [] },
      events: [{ eventId: 'evt_private', eventSeq: 1, eventType: 'model_response', visibility: 'diagnostic',
        eventVersion: 1, threadId: 'thr_1', runId: 'run_1', occurredAt: '2026-10-13T00:00:00Z',
        payload: { text: 'hidden reasoning' } }, { eventId: 'evt_start', eventSeq: 2, eventType: 'attempt_started', visibility: 'public',
        eventVersion: 1, threadId: 'thr_1', runId: 'run_1', occurredAt: '2026-10-13T00:00:00Z', payload: {} }], nextAfter: 2, hasMore: true } as AttemptRecords)
    render(<AttemptRecordPanel attemptId="attempt_old" read={read} />)
    expect(read).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: '读取原任务记录' }))
    await screen.findByText('原始任务')
    expect(screen.getByText(/ieee39/)).toHaveTextContent('rev_old')
    expect(screen.queryByText('hidden reasoning')).not.toBeInTheDocument()
    read.mockResolvedValueOnce({ threadId: 'thr_1', attemptId: 'attempt_old', instruction: '原始任务',
      modelContext: null, events: [], nextAfter: 2, hasMore: false })
    fireEvent.click(screen.getByRole('button', { name: '读取后续记录' }))
    await waitFor(() => expect(read).toHaveBeenLastCalledWith('attempt_old', 2))
    expect(screen.getByText(/ieee39/)).toHaveTextContent('rev_old')
  })

  it('keeps loaded records when the next page fails', async () => {
    const read = vi.fn().mockResolvedValueOnce({ threadId: 'thr_1', attemptId: 'attempt_old',
      instruction: '已保存的任务', modelContext: null, events: [], nextAfter: 0, hasMore: true })
      .mockRejectedValueOnce(new Error('offline'))
    render(<AttemptRecordPanel attemptId="attempt_old" read={read} />)
    fireEvent.click(screen.getByRole('button', { name: '读取原任务记录' }))
    await screen.findByText('已保存的任务')
    fireEvent.click(screen.getByRole('button', { name: '读取后续记录' }))
    await screen.findByRole('alert')
    expect(screen.getByText('已保存的任务')).toBeInTheDocument()
  })
  it('skips pages with no displayable events within a bounded read', async () => {
    const page = { threadId: 'thr_1', attemptId: 'attempt_old', instruction: '原任务', modelContext: null }
    const read = vi.fn().mockResolvedValueOnce({ ...page, events: [], nextAfter: 3, hasMore: true })
      .mockResolvedValueOnce({ ...page, events: [], nextAfter: 6, hasMore: false })
    render(<AttemptRecordPanel attemptId="attempt_old" read={read} />)
    fireEvent.click(screen.getByRole('button', { name: '读取原任务记录' }))
    await screen.findByText(/记录读取完毕/)
    expect(read).toHaveBeenLastCalledWith('attempt_old', 3)
  })
})
