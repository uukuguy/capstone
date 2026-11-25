import {cleanup, fireEvent, render, screen, waitFor} from '@testing-library/react'
import {afterEach, expect, it, vi} from 'vitest'
import DebugWorkspace from './DebugWorkspace'

afterEach(cleanup)

it('approves and revokes reviewed materials for the selected investigation snapshot', async () => {
  const snapshot = 'a'.repeat(64)
  const reviewExport = vi.fn().mockResolvedValue(undefined)
  render(<DebugWorkspace threadId="thr_debug" attempts={[]} attemptLabel={() => undefined}
    through={0} read={vi.fn()} readTimeline={vi.fn()} refreshSource={vi.fn()}
    allowExport savedFinding="" sourceVersion=""
    readHistory={async () => [{investigation_id:'inv_debug', objective:'检查失败', status:'completed'}]}
    readDiagnosis={async () => ({status:'completed', answer:'现场诊断答复'})}
    readSnapshots={async () => [{snapshot_id:snapshot, status:'completed'}]}
    reviewExport={reviewExport}/>)

  fireEvent.click(screen.getByRole('button',{name:'查看调查历史'}))
  await screen.findByRole('option',{name:'检查失败'})
  fireEvent.change(screen.getByRole('combobox',{name:'调查'}), {target:{value:'inv_debug'}})
  fireEvent.click(await screen.findByRole('button',{name:'查看已保存快照'}))
  fireEvent.change(await screen.findByRole('combobox',{name:'证据快照'}), {target:{value:snapshot}})
  fireEvent.click(screen.getByText('审核快照外带材料'))
  expect(screen.getByLabelText<HTMLTextAreaElement>('已审阅结论').value).toBe('')
  fireEvent.change(screen.getByLabelText('已审阅结论'), {target:{value:'已审阅的失败结论'}})
  fireEvent.change(screen.getByLabelText('复现数据（JSON）'), {target:{value:'{"case":"fixture"}'}})
  fireEvent.click(screen.getByRole('button',{name:'核准外带'}))
  await screen.findByText('该快照的外带材料已核准。')
  expect(reviewExport).toHaveBeenCalledWith('inv_debug', snapshot, {
    diagnosis_markdown:'已审阅的失败结论', reproduction:{case:'fixture'},
  })
  fireEvent.click(screen.getByRole('button',{name:'撤回核准'}))
  await waitFor(() => expect(reviewExport).toHaveBeenLastCalledWith('inv_debug', snapshot, null))
})

it('shows a saved finding on site with export disabled', async () => {
  const readSnapshotFinding = vi.fn().mockResolvedValue({summary:'已定位首条失败', next_step:'核对源码'})
  render(<DebugWorkspace threadId="thr_debug" attempts={[]} attemptLabel={() => undefined}
    through={0} read={vi.fn()} readTimeline={vi.fn()} refreshSource={vi.fn()}
    allowExport={false} savedFinding="" sourceVersion=""
    readHistory={async () => [{investigation_id:'inv_debug', objective:'检查失败', status:'running'}]}
    readDiagnosis={async () => ({status:'running'})}
    readSnapshots={async () => [{snapshot_id:'snapshot-1', status:'running'}]}
    readSnapshotFinding={readSnapshotFinding} readEvidence={vi.fn()}/>)

  fireEvent.click(screen.getByRole('button',{name:'查看调查历史'}))
  await screen.findByRole('option',{name:'检查失败'})
  fireEvent.change(screen.getByRole('combobox',{name:'调查'}), {target:{value:'inv_debug'}})
  fireEvent.click(await screen.findByRole('button',{name:'查看已保存快照'}))
  fireEvent.change(await screen.findByRole('combobox',{name:'证据快照'}), {target:{value:'snapshot-1'}})
  fireEvent.click(screen.getByRole('button',{name:'查看阶段结论'}))

  await screen.findByText('已定位首条失败')
  expect(screen.getByText('下一步 · 核对源码')).toBeTruthy()
  expect(readSnapshotFinding).toHaveBeenCalledWith('inv_debug','snapshot-1')
  expect(screen.queryByRole('button',{name:'下载调查记录'})).toBeNull()
})
