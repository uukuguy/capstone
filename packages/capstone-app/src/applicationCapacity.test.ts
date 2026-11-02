import {afterEach,expect,it,vi} from 'vitest'
import {applicationCapacity,initializeApplicationCapacity,readRuntimeCapacity,CapacityError,observeCapacity} from './applicationCapacity'
import {projectNativeArtifacts} from './nativeArtifacts'
import {readNetworkCamera} from './threadNetworkCamera'
import {capacityFailureNotice,parseCapacityFailure} from './capacityFailure'
import {readDraft,writeDraft,canReconnect} from './threadSessionState'
import {parseNativeArtifact} from './nativeArtifacts'
import {HttpThreadTransport} from './threadHttpTransport'
import {readThreadAccess} from './threadAccess'
import {parseContextProductRefs} from './threadProducts'
import {resultProjectionHistoryText} from './threadSystemNotices'

afterEach(()=>{initializeApplicationCapacity();sessionStorage.clear();vi.unstubAllGlobals()})
it('keeps normal soft limits observable and interrupts debug mode with exact provenance',()=>{
  initializeApplicationCapacity({schema:'capstone-capacity-profile/1',mode:'normal',limits:{preview_bytes:4}})
  expect(observeCapacity(5,'preview_bytes','native-preview')).toBe(true)
  initializeApplicationCapacity({schema:'capstone-capacity-profile/1',mode:'debug',fingerprint:'test-profile',limits:{preview_bytes:4}})
  let failure:unknown
  try{observeCapacity(5,'preview_bytes','native-preview')}catch(error){failure=error}
  expect(failure).toBeInstanceOf(CapacityError)
  expect(failure).toMatchObject({dimension:'preview_bytes',actual:5,effective:4,mode:'debug',location:'native-preview',source:'test-profile'})
  expect((failure as Error).message).toContain('native-preview')
  expect(canReconnect(failure)).toBe(false)
  expect(()=>initializeApplicationCapacity({schema:'capstone-capacity-profile/1',mode:'other',limits:{}})).toThrow(CapacityError)
})
it('does not swallow debug capacity failures while projecting published file events',()=>{
  initializeApplicationCapacity({schema:'capstone-capacity-profile/1',mode:'debug',limits:{artifact_file_bytes:1}})
  const id=`file-${'c'.repeat(16)}-${'a'.repeat(64)}`
  const artifact={schema:'capstone-process-artifact/1',scope:'instruction',thread_id:'thr_one',run_id:'run_one',turn_id:'turn_one',attempt_id:'attempt_one',work_id:'work_one',task_snapshot_id:'snapshot_one',goal_revision:1,task_id:'task_one',artifact_id:id,executor_identity_sha256:'d'.repeat(64),source_status:'completed',file_name:'report.html',media_type:'text/html',sha256:'a'.repeat(64),size_bytes:2,download_url:`/api/v1/threads/thr_one/attempts/attempt_one/artifacts/${id}`}
  expect(()=>projectNativeArtifacts([{visibility:'public',eventType:'native_artifact_published',threadId:'thr_one',runId:'run_one',turnId:'turn_one',attemptId:'attempt_one',payload:{artifact}}] as never)).toThrow(CapacityError)
})
it('interrupts debug camera eviction instead of silently restoring an empty view',()=>{
  initializeApplicationCapacity({schema:'capstone-capacity-profile/1',mode:'debug',limits:{ui_camera_storage_bytes:3}})
  sessionStorage.setItem('cameras',JSON.stringify({view:{x:0,y:0,width:1,height:1}}))
  expect(()=>readNetworkCamera('cameras','view')).toThrow(CapacityError)
})
it('preserves exact public debug diagnostics and rejects untrusted extra failure fields',()=>{
  const capacity={code:'capacity_exceeded',dimension:'preview_bytes',actual:5,limit:4,unit:'bytes',phase:'artifact.preview',retryable:false,mode:'debug',fatal:true,effective:4,source:'application_capacity',location:'artifact.preview'}
  expect(parseCapacityFailure(capacity)).toMatchObject({fatal:true,effective:4})
  const notice=capacityFailureNotice({failure:{code:'capacity_exceeded',capacity}})
  expect(notice).toContain('debug')
  expect(notice).toContain('application_capacity')
  expect(notice).toContain('artifact.preview')
  expect(parseCapacityFailure({...capacity,raw_exception:'private'})).toBeUndefined()
})
it('does not retry or erase a structured server debug interruption',async()=>{
  const capacity={code:'capacity_exceeded',dimension:'artifact_file_bytes',actual:5,limit:4,unit:'bytes',phase:'artifact.read',retryable:false,mode:'debug',fatal:true,effective:4,source:'application_capacity',location:'artifact.read'}
  const fetcher=vi.fn().mockResolvedValue(new Response(JSON.stringify({detail:capacity}),{status:413}))
  const transport=new HttpThreadTransport('','',fetcher)
  await expect(transport.getSnapshot('thr_one')).rejects.toMatchObject({name:'CapacityError',actual:5,effective:4,mode:'debug',fatal:true,source:'application_capacity',location:'artifact.read'})
  expect(fetcher).toHaveBeenCalledTimes(1)
})
it('installs immutable validated startup overrides and rejects unknown, zero and invalid limits',()=>{
  const snapshot=initializeApplicationCapacity({artifact_file_bytes:1024,input_text_chars:40})
  expect(Object.isFrozen(snapshot.limits)).toBe(true)
  expect(applicationCapacity('artifact_file_bytes')).toBe(1024)
  for(const overrides of [{unknown_capacity:1},{artifact_file_bytes:0},{input_text_chars:1.2},{input_text_chars:-1}])expect(()=>initializeApplicationCapacity(overrides as never)).toThrow(CapacityError)
  expect(applicationCapacity('artifact_file_bytes')).toBe(1024)
})
it('bootstraps effective public capacity and refuses invalid advertised values',async()=>{
  const fetcher=vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({schema:'capstone-capacity-profile/1',limits:{input_text_chars:321},fingerprint:'effective-one'}))).mockResolvedValueOnce(new Response(JSON.stringify({schema:'capstone-capacity-profile/1',limits:{unknown_field:12}})))
  expect((await readRuntimeCapacity('',undefined,fetcher)).limits.input_text_chars).toBe(321)
  await expect(readRuntimeCapacity('',undefined,fetcher)).rejects.toThrow(/unknown_field/)
  expect(applicationCapacity('input_text_chars')).toBe(321)
})
it('keeps a long draft intact and reports a configured overflow instead of silently truncating',()=>{
  initializeApplicationCapacity({input_text_chars:50_000})
  const text='指令'.repeat(12_000)
  writeDraft('test',text)
  expect(readDraft('test')).toBe(text)
  initializeApplicationCapacity({input_text_chars:20})
  expect(()=>readDraft('test')).toThrow(/input_text_chars/)
  expect(()=>writeDraft('other',text)).toThrow(/input_text_chars/)
})
it('uses initialized capacity while parsing real file descriptors',()=>{
  const file={schema:'capstone-process-artifact/1',scope:'instruction',thread_id:'thr_one',run_id:'run_one',turn_id:'turn_one',attempt_id:'attempt_one',work_id:'work_one',task_snapshot_id:'snapshot_one',goal_revision:1,task_id:'task_one',artifact_id:`file-${'c'.repeat(16)}-${'a'.repeat(64)}`,executor_identity_sha256:'d'.repeat(64),source_status:'completed',file_name:'large.svg',media_type:'image/svg+xml',sha256:'a'.repeat(64),size_bytes:5*1024*1024,download_url:`/api/v1/threads/thr_one/attempts/attempt_one/artifacts/file-${'c'.repeat(16)}-${'a'.repeat(64)}`}
  initializeApplicationCapacity({artifact_file_bytes:6*1024*1024})
  expect(parseNativeArtifact(file,'thr_one','attempt_one').size_bytes).toBe(file.size_bytes)
  initializeApplicationCapacity({artifact_file_bytes:1024})
  expect(()=>parseNativeArtifact(file,'thr_one','attempt_one')).toThrow()
})
it('consumes published access capacity before the first thread payload read',async()=>{
  const fetcher=vi.fn().mockResolvedValue(new Response(JSON.stringify({schema:'capstone-thread-access/1',mode:'open',capacity:{schema:'capstone-capacity-profile/1',limits:{event_page_bytes:30}}})))
  vi.stubGlobal('fetch',fetcher)
  await readThreadAccess('',new AbortController().signal)
  const transport=new HttpThreadTransport('','',vi.fn().mockResolvedValue(new Response(JSON.stringify({body:'x'.repeat(40)}))))
  await expect(transport.getSnapshot('thr_one')).rejects.toThrow(/event_page_bytes/)
})
it('allows more than four exact references when configured and rejects the configured boundary',()=>{
  const refs=Array.from({length:6},(_,i)=>({ref:{schema:'capstone-product-ref/1',thread_id:'thr_one',product_id:`file_${i}`,origin:'native_file',scope:'instruction',event_seq:i+1,revision:null,digest:'a'.repeat(64),work_id:'work_one',attempt_id:'attempt_one',producer_attempt_id:null},purpose:'historical-context'}))
  initializeApplicationCapacity({product_reference_count:6})
  expect(parseContextProductRefs(refs)).toHaveLength(6)
  initializeApplicationCapacity({product_reference_count:5})
  expect(()=>parseContextProductRefs(refs)).toThrow(/product_reference_count/)
})
it('reports a genuine snapshot result window without claiming unrelated model results are current',()=>{
  const snapshot={activeModelContext:{id:'ctx_one'},applicationState:{result_projection_history:{has_more:true,omitted_count:9,model_context_id:'ctx_one'}}}
  expect(resultProjectionHistoryText(snapshot as never)).toContain('9 份较早结果')
  snapshot.applicationState.result_projection_history.model_context_id='ctx_other'
  expect(resultProjectionHistoryText(snapshot as never)).toBeUndefined()
})
