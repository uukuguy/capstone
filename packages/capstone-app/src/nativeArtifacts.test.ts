import {initializeApplicationCapacity} from './applicationCapacity'
import {afterEach,expect,it} from 'vitest'
import {parseNativeArtifacts,groupNativeArtifacts} from './nativeArtifacts'

it('groups host-declared purposes without guessing from filename or promoting task scope',()=>{
  const primary={...file,presentation_role:'primary' as const}
  const support={...file,presentation_role:'support' as const}
  const reproduction={...file,presentation_role:'reproduction' as const}
  expect(groupNativeArtifacts([file,primary,support,reproduction] as never)).toEqual({primary:[primary],support:[support],reproduction:[reproduction],other:[file]})
})
it('rejects an unknown presentation role',()=>{
  expect(()=>parseNativeArtifacts(page({...file,presentation_role:'accepted'}),'thr_one','attempt_one')).toThrow()
})
it('preserves actual limited-delivery warnings without claiming a clean result',()=>{
  const artifact={...file,presentation_role:'primary',delivery_status:'limited',delivery_limitations:['图表未独立核验']}
  expect(parseNativeArtifacts(page(artifact),'thr_one','attempt_one').artifacts).toEqual([artifact])
  expect(()=>parseNativeArtifacts(page({...artifact,delivery_status:'quality_passed'}),'thr_one','attempt_one')).toThrow()
  expect(()=>parseNativeArtifacts(page({...artifact,delivery_limitations:[{raw:'exception'}]}),'thr_one','attempt_one')).toThrow()
})

const digest='a'.repeat(64)
const file={schema:'capstone-process-artifact/1',scope:'instruction',thread_id:'thr_one',run_id:'run_one',turn_id:'turn_one',attempt_id:'attempt_one',work_id:'work_one',task_snapshot_id:'task_snapshot',goal_revision:1,task_id:'native_one',artifact_id:`file-${'b'.repeat(16)}-${digest}`,executor_identity_sha256:'c'.repeat(64),source_status:'completed',file_name:'结果.md',media_type:'text/markdown',sha256:digest,size_bytes:12,download_url:`/api/v1/threads/thr_one/attempts/attempt_one/artifacts/file-${'b'.repeat(16)}-${digest}`}
const page=(artifact:unknown=file)=>({schema:'capstone-process-artifacts/1',thread_id:'thr_one',attempt_id:'attempt_one',artifacts:[artifact],has_more:false,next_after:4})
it('admits a bounded persisted instruction file and preserves its complete identity',()=>{
  expect(parseNativeArtifacts(page(),'thr_one','attempt_one',0).artifacts).toEqual([file])
})
it.each(['text/html','image/svg+xml'])('admits persisted %s files for preview and task adoption without changing failed provenance',media_type=>{
  const artifact={...file,media_type,source_status:'cancelled'}
  expect(parseNativeArtifacts(page(artifact),'thr_one','attempt_one').artifacts).toEqual([artifact])
})
it.each([{thread_id:'thr_other'},{attempt_id:'attempt_other'},{scope:'task'},{file_name:'../report.md'},{download_url:'https://untrusted.test/report'},{sha256:'d'.repeat(64)},{media_type:'application/javascript'},{size_bytes:4*1024*1024+1}])('rejects a file outside its ownership or public content bounds: %j',change=>{
  initializeApplicationCapacity({artifact_file_bytes:4*1024*1024})
  expect(()=>parseNativeArtifacts(page({...file,...change}),'thr_one','attempt_one',0)).toThrow()
})
it('accepts an empty record page with forward progress and rejects a stuck cursor',()=>{
  expect(parseNativeArtifacts({...page(),artifacts:[],has_more:true},'thr_one','attempt_one',0)).toEqual({artifacts:[],hasMore:true,nextAfter:4})
  expect(()=>parseNativeArtifacts({...page(),artifacts:[],has_more:true,next_after:0},'thr_one','attempt_one',0)).toThrow()
})

afterEach(()=>initializeApplicationCapacity())
