import {afterEach,expect,it,vi} from 'vitest'
import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import InstructionFiles from './InstructionFiles'
import {nativeArtifactVersions,type NativeArtifact} from './nativeArtifacts'

afterEach(cleanup)
const file=(version:string,path='a',task='task'):NativeArtifact=>({
  thread_id:'thread',attempt_id:'attempt',task_id:task,file_name:'report.pdf',
  artifact_id:`file-${version.repeat(16)}-${version.repeat(64)}`,
  host_artifact_id:`file-${path.repeat(16)}-${version.repeat(64)}`,
  presentation_role:'primary',media_type:'application/pdf',size_bytes:100,
  saved_at:`2026-11-01T15:00:0${version==='b'?1:2}Z`,
} as NativeArtifact)

it('shows the latest output and keeps exact old versions behind closed history',()=>{
  const old=file('b'),latest=file('c'),onOpen=vi.fn()
  const {container}=render(<InstructionFiles files={[old,latest]} onOpen={onOpen}/>)
  expect(container.querySelectorAll('.capstone-result-products > div > button')).toHaveLength(1)
  fireEvent.click(screen.getByRole('button',{name:'打开指令文件：report.pdf'}))
  expect(onOpen).toHaveBeenLastCalledWith(latest)
  expect(container.querySelector('details')?.open).toBe(false)
  expect(container.querySelector('time')?.dateTime).toBe(latest.saved_at)
  fireEvent.click(screen.getByText('历史版本 · 1'))
  fireEvent.click(screen.getByRole('button',{name:/历史版本 1/}))
  expect(onOpen).toHaveBeenLastCalledWith(old)
  expect(container.querySelector('details time')?.getAttribute('datetime')).toBe(old.saved_at)
})
it('does not collapse same names from different paths, tasks or attempts',()=>{
  const files=[file('b'),file('c','d'),file('d','a','another'),{...file('e'),attempt_id:'another'}]
  expect(nativeArtifactVersions(files)).toHaveLength(4)
})
it('selects the newest saved version even when restored pages arrive after live events',()=>{
  const old=file('b'),latest=file('c')
  expect(nativeArtifactVersions([latest,old])[0]).toEqual({latest,history:[old]})
})
it('does not guess version identity for legacy files without host path identity',()=>{
  expect(nativeArtifactVersions([file('b'),file('c')].map(({host_artifact_id,...item})=>item))).toHaveLength(2)
})
