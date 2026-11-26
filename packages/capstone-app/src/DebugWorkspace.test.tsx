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
  const revision = 'a'.repeat(40)
  const readSnapshotFinding = vi.fn().mockResolvedValue({summary:'已定位首条失败', next_step:'核对源码',
    event_refs:[854], gateway_refs:['call_fixture'],
    source_refs:[{repository:'capstone', revision, path:'src/example.py', line:21}]})
  const readSource = vi.fn().mockResolvedValue({revision, first_line:21, lines:['observed line']})
  render(<DebugWorkspace threadId="thr_debug" attempts={[]} attemptLabel={() => undefined}
    through={0} read={vi.fn()} readTimeline={vi.fn()} refreshSource={vi.fn()}
    allowExport={false} savedFinding="" sourceVersion=""
    readHistory={async () => [{investigation_id:'inv_debug', objective:'检查失败', status:'running'}]}
    readDiagnosis={async () => ({status:'running'})}
    readSnapshots={async () => [{snapshot_id:'snapshot-1', status:'running'}]}
    readSnapshotFinding={readSnapshotFinding} readEvidence={vi.fn()} readSource={readSource}/>)

  fireEvent.click(screen.getByRole('button',{name:'查看调查历史'}))
  await screen.findByRole('option',{name:'检查失败'})
  fireEvent.change(screen.getByRole('combobox',{name:'调查'}), {target:{value:'inv_debug'}})
  fireEvent.click(await screen.findByRole('button',{name:'查看已保存快照'}))
  fireEvent.change(await screen.findByRole('combobox',{name:'证据快照'}), {target:{value:'snapshot-1'}})
  fireEvent.click(screen.getByRole('button',{name:'查看阶段结论'}))

  await screen.findByText('已定位首条失败')
  expect(screen.getByText('下一步 · 核对源码')).toBeTruthy()
  expect(readSnapshotFinding).toHaveBeenCalledWith('inv_debug','snapshot-1')
  expect(screen.getByText('#854')).toBeTruthy()
  expect(screen.getByText('call_fixture')).toBeTruthy()
  fireEvent.click(screen.getByRole('button',{name:'capstone src/example.py:21'}))
  await screen.findByText('21 observed line', {normalizer:text=>text.replace(/\s+/g,' ').trim()})
  expect(readSource).toHaveBeenCalledWith('inv_debug', new URLSearchParams({
    repository:'capstone', path:'src/example.py', line:'21',
  }))
  readSource.mockResolvedValueOnce({revision:'b'.repeat(40), first_line:21, lines:['wrong revision']})
  fireEvent.click(screen.getByRole('button',{name:'capstone src/example.py:21'}))
  await screen.findByText('返回的源码版本与快照引用不同。')
  expect(screen.queryByText(/wrong revision|observed line/)).toBeNull()
  expect(screen.queryByRole('button',{name:'下载调查记录'})).toBeNull()
})
