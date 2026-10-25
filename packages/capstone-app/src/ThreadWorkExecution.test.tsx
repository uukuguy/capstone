import { afterEach, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import ThreadLiveEntry from './ThreadLiveEntry'
import ThreadWorkAdapter from './ThreadWorkAdapter'
import { HttpThreadTransport } from './threadHttpTransport'
import { writePendingCommands } from './threadSessionState'
import { buildStartWorkCommand } from './threadWorkProtocol'
import {webcrypto} from 'node:crypto'
import type { WorkCommand } from './threadWorkProtocol'

afterEach(() => { cleanup(); vi.unstubAllGlobals(); sessionStorage.clear(); localStorage.clear(); window.history.replaceState({}, '', '/') })

/** In-memory HTTP authority fixture. It never invokes a Provider or simulator. */
function authority({ lostStart = false, lostCancel = false, lostMessage=false, rejectMessage=false, modelFree = false, existingWork = false, native = false, nativeAvailable=true,legacySaved=false,modelControls=false } = {}) {
  const model = { id: 'ctx_one', model_id: 'ieee39', model_revision: `revision:sha256:${'c'.repeat(64)}`, implementation_family: 'pandapower', selection_revision: 'sel_one' }
  const context = { binding: { thread_id: 'thr_work', work_id: 'work_one', research_id: 'research-one' }, goal_revision: 1,
    snapshot_id: 'task_one', model_contexts: modelFree||native ? [] : [model], resource_refs: [] }
  const work = { work_id: 'work_one', goal: '测试目标', goal_revision: 1, revision: 1, status: modelFree ? 'blocked' : 'ready',
    blocked_reason: modelFree ? 'execution_unavailable' : null, latest_attempt_id: null as string | null,
    cancel_requested: false, messages: native&&!legacySaved?[]:['测试目标'], task_context: context, ...(native?{conversation_mode:!legacySaved}:{}) }
  let upgraded = modelFree || existingWork || native
  let saved = modelFree || existingWork
  let attempt: Record<string, unknown> | null = null
  let stream: ReadableStreamDefaultController<Uint8Array> | undefined
  const events: Record<string, unknown>[] = []
  const projections: Record<string, unknown>[] = []
  const files:Record<string,unknown>[]=[]
  let materials:Record<string,unknown>[]=[]
  const receipts = new Map<string, Record<string, unknown>>()
  const commands: WorkCommand[] = []
  let attemptsCreated = 0
  let snapshots = 0
  let openedModel = false
  function projection() {
    const reason = modelFree ? 'execution_unavailable' : attempt ? 'attempt_in_progress' : null
    return { ...work, start_available: reason === null, start_unavailable_reason: reason }
  }
  function snapshot() {
    const base = { schema: 'capstone-thread-snapshot/1', thread_id: 'thr_work', run: { run_id: 'run_work', state: 'open' },
      active_model_context: modelFree||(native&&!openedModel) ? null : model, active_grid_page_id: modelFree||(native&&!openedModel) ? null : 'page_one', current_attempt: attempt,
      last_event_seq: events.length, base_event_seq: 0, result_projections: projections }
    return upgraded ? { ...base, schema: 'capstone-thread-snapshot/2', minimum_protocol_version: 2,
      selected_model_context_id: modelFree||(native&&!openedModel) ? null : model.id, works: saved ? [projection()] : [], task_context: saved ? context : null,
      ...(native?{session_type:'general-chat',native_execution:{available:nativeAvailable&&!openedModel,unavailable_reason:nativeAvailable&&!openedModel?null:'native_executor_unavailable'}}:{}) } : base
  }
  function append(type: string, payload: Record<string, unknown>, withAttempt = false) {
    const event = { event_id: `evt_${events.length + 1}`, event_seq: events.length + 1, event_type: type, event_version: 2,
      thread_id: 'thr_work', run_id: 'run_work', occurred_at: '2026-10-17T00:00:00Z', visibility: 'public', payload,
      ...(withAttempt ? { attempt_id: 'attempt_one', turn_id: 'turn_one', ...(!native?{model_context_id: 'ctx_one', selection_revision: 'sel_one'}:{}) } : {}) }
    events.push(event)
    try { stream?.enqueue(new TextEncoder().encode(`data: ${JSON.stringify(event)}\n\n`)) }
    catch { /* Durable server events remain readable when the client stream has disconnected. */ }
    return event.event_seq
  }
  function started() {
    work.status = 'running'; work.revision += 1; attempt = { ...attempt, phase: 'running' }
    append('attempt_started', { work_id: work.work_id, work: projection() }, true)
  }
  function publishFile(name:string,role?:'primary') {
    const digest='2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824'
    const artifact_id=`file-${String(files.length+1).repeat(16)}-${digest}`
    const artifact={schema:'capstone-process-artifact/1',scope:'instruction',thread_id:'thr_work',run_id:'run_work',turn_id:'turn_one',attempt_id:'attempt_one',work_id:'work_one',task_snapshot_id:'task_one',goal_revision:1,task_id:'native_one',artifact_id,executor_identity_sha256:'c'.repeat(64),source_status:'completed',file_name:name,media_type:name.endsWith('.html')?'text/html':name.endsWith('.csv')?'text/csv':'text/markdown',sha256:digest,size_bytes:5,download_url:`/api/v1/threads/thr_work/attempts/attempt_one/artifacts/${artifact_id}`}
    const published={...artifact,...(role?{presentation_role:role}:{})}
    files.push(published);append('native_artifact_published',{artifact:published,work_id:'work_one'},true)
  }
  function finish(cancelled = false) {
    work.status = cancelled ? 'cancelled' : 'completed'; work.revision += 1; work.cancel_requested = false; attempt = null
    const result = { schema: 'capstone-result-projection/1.0', result_id: 'result_one',
      result_ref: `result:sha256:${'a'.repeat(64)}`, evidence_refs: [`evidence:sha256:${'b'.repeat(64)}`],
      thread_id: 'thr_work', run_id: 'run_work', turn_id: 'turn_one', attempt_id: 'attempt_one',
      model_context_id: 'ctx_one', model_id: 'ieee39', model_revision: model.model_revision,
      source: { capability_id: 'analysis.run', domain_pack_id: 'pandapower-static-analysis', implementation_family: 'pandapower' },
      status: 'completed', summary: [], tables: [], element_refs: [], overlay: null }
    if (!cancelled&&!native) projections.push(result)
    if(native&&!cancelled)work.messages=[]
    append(cancelled ? 'attempt_cancelled' : 'attempt_completed', { work_id: work.work_id, work: projection(),
      ...(cancelled ? { reason: 'user_requested' } : { answer: '来自真实事件的测试结果', ...(!native?{result_projections: [result]}:{}) }) }, true)
  }
  const response = (body: unknown) => new Response(JSON.stringify(body), { headers: { 'Capstone-Thread-Version': '2' } })
  function indexedProducts(){return events.filter(event=>event.event_type==='native_artifact_published'||['attempt_completed','attempt_cancelled'].includes(String(event.event_type))).map(event=>{
    const original=(event.payload as {artifact?:Record<string,unknown>}).artifact
    const artifact=original?files.find(file=>file.artifact_id===original.artifact_id)||original:undefined
    const ref={schema:'capstone-product-ref/1',thread_id:'thr_work',product_id:`product_${String(event.event_seq).padStart(32,'0')}`,origin:artifact?'native_file':'process_record',scope:'instruction',event_seq:event.event_seq,revision:null,digest:artifact?.sha256||'a'.repeat(64),work_id:'work_one',attempt_id:'attempt_one',producer_attempt_id:null}
    const record={product_id:'process_attempt_one',thread_id:'thr_work',attempt_id:'attempt_one',instruction:'已完成的原指令',status:'completed',failure_code:null}
    return {ref,title:artifact?.file_name||record.instruction,media_type:artifact?.media_type||null,byte_size:artifact?.size_bytes??null,source_status:'completed',created_at:event.occurred_at,download_url:artifact?.download_url||null,source:artifact||record,dependencies:[],presentation:{kind:ref.origin},capabilities:{read:true,select:true,select_excerpt:false},selection_unavailable_reason:null,historical_only:true}
  })}
  const fetcher = vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
    const parsed = new URL(String(url), 'http://localhost')
    if (parsed.pathname.endsWith('/thread-access')) return response({ schema: 'capstone-thread-access/1', mode: 'open' })
    if(parsed.pathname.endsWith('/resources'))return response({schema:'capstone-resources/1',resources:[]})
    if(parsed.pathname.endsWith('/input-catalog'))return response({schema:'capstone-thread-input-catalog/1',revision:`input_${materials.length}`,context_id:'ctx_native',selection_revision:'sel_native',objects:[],materials,resource_profiles:{},operations:[]})
    if(parsed.pathname.endsWith('/materials')&&init?.method!=='POST')return response({limits:{max_file_bytes:8*1024*1024,supported_extensions:['.md','.csv','.txt']},materials})
    if(parsed.pathname.endsWith('/materials')&&init?.method==='POST'){
      const file=init.body as File
      const material={schema:'capstone-thread-material/1',thread_id:'thr_work',material_id:`material_${'a'.repeat(32)}`,file_name:file.name,display_name:file.name,media_type:'text/markdown',sha256:'b'.repeat(64),size_bytes:file.size,created_at:'2026-10-17T00:00:00Z'}
      materials.push(material);append('material_uploaded',{material});return response(material)
    }
    if(parsed.pathname.includes('/materials/')&&init?.method==='DELETE'){
      const removed=parsed.pathname.split('/').pop();materials=materials.filter(item=>item.material_id!==removed);append('material_removed',{material_id:removed});return response({removed})
    }
    if(parsed.pathname.endsWith('/artifacts'))return response({schema:'capstone-process-artifacts/1',thread_id:'thr_work',attempt_id:'attempt_one',artifacts:files,has_more:false,next_after:events.length})
    if(parsed.pathname.endsWith('/product-index'))return response({schema:'capstone-product-index/1',thread_id:'thr_work',products:indexedProducts(),has_more:false,next_cursor:null})
    if(parsed.pathname.endsWith('/product-index/resolve')){
      const {ref}=JSON.parse(String(init?.body)),entry=indexedProducts().find(item=>item.ref.product_id===ref.product_id)
      return response({schema:'capstone-product-resolution/1',entry,content_base64:entry?.ref.origin==='native_file'?'aGVsbG8=':null,projection:null,record:entry?.ref.origin==='process_record'?entry.source:null})
    }
    if(parsed.pathname.includes('/artifacts/'))return new Response('hello',{headers:{'Content-Type':'text/markdown'}})
    if (parsed.pathname.endsWith('/threads') && init?.method !== 'POST') return response({ schema: 'capstone-thread-list/1', threads: [], has_more: false, next_before_thread_id: null })
    if(parsed.pathname.endsWith('/products'))return response({schema:'capstone-process-products/1',thread_id:'thr_work',has_more:false,next_before_event_seq:1,
      products:events.filter(event=>['attempt_completed','attempt_cancelled'].includes(String(event.event_type))).map(event=>({product_id:'process_attempt_one',scope:'instruction',thread_id:'thr_work',attempt_id:'attempt_one',work_id:'work_one',historical_only:true,instruction:'已完成的原指令',status:'completed',event_seq:event.event_seq,occurred_at:'2026-10-17T00:00:00Z',failure_code:null,model_context:native?null:model}))})
    if (parsed.pathname.endsWith('/history')) {
      const before = Number(parsed.searchParams.get('before') || events.length + 1)
      return response({ schema: 'capstone-thread-history/1', thread_id: 'thr_work', before_event_seq: before,
        next_before_event_seq: 1, has_more: false, events: events.filter(row => Number(row.event_seq) < before) })
    }
    if (parsed.pathname.endsWith('/events/stream')) return new Response(new ReadableStream<Uint8Array>({
      start(controller) { stream = controller; init?.signal?.addEventListener('abort', () => controller.error(new DOMException('Aborted', 'AbortError')), { once: true }) },
    }), { headers: { 'Capstone-Thread-Version': '2' } })
    if (parsed.pathname.endsWith('/events')) {
      const after = Number(parsed.searchParams.get('after') || 0)
      return response({ schema: 'capstone-thread-events/1', thread_id: 'thr_work', after_event_seq: after,
        next_event_seq: events.length, has_more: false, events: events.filter(row => Number(row.event_seq) > after) })
    }
    if (parsed.pathname.endsWith('/commands')) {
      const command = JSON.parse(String(init?.body)) as WorkCommand; commands.push(command)
      const previous = receipts.get(command.idempotency_key)
      if (previous) return response(previous)
      if (command.kind === 'open_model') {
        openedModel = true
        const accepted = append('model_workspace_changed',{kind:command.kind})
        return response({schema:'capstone-command-receipt/1',command_id:command.command_id,idempotency_key:command.idempotency_key,thread_id:'thr_work',status:'accepted',accepted_event_seq:accepted,target:{kind:'model_workspace',id:'thr_work',expected_revision:accepted}})
      }
      if (command.kind === 'send_message' && rejectMessage) return response({schema:'capstone-command-receipt/1',command_id:command.command_id,idempotency_key:command.idempotency_key,thread_id:'thr_work',run_id:'run_work',status:'rejected',rejection:'product_context_unavailable'})
      if (command.kind === 'work_message') { upgraded = true; saved = true }
      if (command.kind === 'send_message') {saved=true;work.messages.push(String(command.payload.text));work.goal=String(command.payload.text)}
      if (command.kind === 'start_work'||command.kind === 'send_message') {
        attemptsCreated += 1; work.status = 'queued'; work.revision += 1; work.latest_attempt_id = 'attempt_one'
        attempt = { attempt_id: 'attempt_one', turn_id: 'turn_one', target_model_context_id: native&&!openedModel?null:model.id, phase: 'accepted', runtime_mode: 'capstone',...(native?{work_id:'work_one'}:{}) }
      }
      if (command.kind === 'cancel_work') { work.cancel_requested = true; work.revision += 1 }
      const accepted = append('command.applied', { command_id: command.command_id, work_id: work.work_id, work: projection() })
      if (command.kind === 'start_work'||command.kind==='send_message') append('command_accepted', { kind: 'send_auto', payload: { text: work.goal }, work_id: work.work_id, work: projection() }, true)
      if (command.kind === 'cancel_work') append('attempt_cancel_requested', { work_id: work.work_id, work: projection() }, true)
      const receipt = { schema: 'capstone-command-receipt/1', command_id: command.command_id, idempotency_key: command.idempotency_key,
        thread_id: 'thr_work', status: 'accepted', accepted_event_seq: accepted, target: { kind: 'work', id: work.work_id,
          expected_revision: work.revision, ...(attempt ? { turn_id: 'turn_one', attempt_id: 'attempt_one' } : {}) } }
      receipts.set(command.idempotency_key, receipt)
      if (command.kind === 'start_work' && lostStart) throw new TypeError('start response lost')
      if (command.kind === 'cancel_work' && lostCancel) throw new TypeError('cancel response lost')
      if(command.kind==='send_message'&&lostMessage)throw new TypeError('message response lost')
      return response(receipt)
    }
    if (parsed.pathname.endsWith('/thr_work')) { snapshots += 1; return response(snapshot()) }
    if (parsed.pathname.endsWith('/models')&&modelControls) return response({schema:'capstone-thread-model-workspace/1',thread_id:'thr_work',run_id:'run_work',event_seq:events.length,current_entry_id:openedModel?'mdl_one':null,models:openedModel?[{entry_id:'mdl_one',model_id:model.model_id,model_revision:model.model_revision,implementation_family:'pandapower',authority_model_ref:'gridctl:ieee39',display_name:'IEEE-39',diagram_provider_id:'gridctl',last_active_seq:events.length}]:[],blocked_reason:null})
    if (parsed.pathname.endsWith('/catalog')) return response({ schema: 'capstone-thread-catalog/1', models: modelControls?[{model_id:'ieee39',implementation_family:'pandapower',authority_model_ref:'gridctl:ieee39',display_name:'IEEE-39',diagram_provider_id:'gridctl'}]:[], profiles: [] })
    throw new Error(`Unexpected test request: ${parsed.pathname}`)
  })
  return { fetcher, commands, started, finish, snapshot, work, publishFile,
    projectPrimary(name:string){const index=files.findIndex(file=>file.file_name===name);files[index]={...files[index],presentation_role:'primary',delivery_status:'limited',delivery_limitations:['图表尚未完成独立核验']}},get upgraded() { return upgraded },
    get attemptsCreated() { return attemptsCreated }, get snapshots() { return snapshots }, get streamReady() { return stream !== undefined },
    disconnect() { stream?.error(new TypeError('stream disconnected')) } }
}

async function saveGoal(server: ReturnType<typeof authority>) {
  vi.stubGlobal('fetch', server.fetcher)
  render(<ThreadLiveEntry threadId="thr_work" mode="work" />)
  fireEvent.change(await screen.findByRole('textbox', { name: '任务目标' }), { target: { value: '测试目标' } })
  expect(server.upgraded).toBe(false)
  expect(server.commands).toHaveLength(0)
  await waitFor(() => expect(server.streamReady).toBe(true))
  fireEvent.click(screen.getByRole('button', { name: '保存任务' }))
  await screen.findByRole('textbox', { name: '补充任务资料' })
  await waitFor(() => expect((screen.getByRole('button', { name: '开始任务' }) as HTMLButtonElement).disabled).toBe(false))
}

it('retains the draft and rejection notice when a selected product cannot be admitted',async()=>{
  const server=authority({native:true,rejectMessage:true})
  vi.stubGlobal('fetch',server.fetcher)
  render(<ThreadWorkAdapter transport={new HttpThreadTransport('','',server.fetcher,'/api/v1/threads','2')} threadId="thr_work" namespace="rejected-product" recoveryOnly />)
  const input=await screen.findByRole('textbox',{name:'Thread 指令'})
  fireEvent.change(input,{target:{value:'请修改报告'}})
  await waitFor(()=>expect((screen.getByRole('button',{name:'发送'}) as HTMLButtonElement).disabled).toBe(false))
  fireEvent.click(screen.getByRole('button',{name:'发送'}))
  await screen.findByText('引用的成果暂时无法加入本轮资料。指令未执行，请检查引用后重试。')
  await waitFor(()=>expect((screen.getByRole('textbox',{name:'Thread 指令'}) as HTMLTextAreaElement).value).toBe('请修改报告'))
})

it('sends a native instruction directly through the shared composer and resumes the same Work after completion',async()=>{
  const server=authority({native:true})
  vi.stubGlobal('fetch',server.fetcher)
  render(<ThreadWorkAdapter transport={new HttpThreadTransport('','',server.fetcher,'/api/v1/threads','2')} threadId="thr_work" namespace="native-chat" recoveryOnly />)
  const input=await screen.findByRole('textbox',{name:'Thread 指令'})
  expect(screen.queryByRole('button',{name:'开始任务'})).toBeNull()
  expect(screen.queryByRole('button',{name:'保存任务'})).toBeNull()
  fireEvent.change(input,{target:{value:'解释这个问题'}})
  await waitFor(()=>expect((screen.getByRole('button',{name:'发送'}) as HTMLButtonElement).disabled).toBe(false))
  fireEvent.click(screen.getByRole('button',{name:'发送'}))
  await waitFor(()=>expect(server.commands[0]?.kind).toBe('send_message'))
  expect(server.commands[0].target.id).toBe('new')
  await act(async()=>server.finish())
  await screen.findByText('来自真实事件的测试结果')
  fireEvent.change(screen.getByRole('textbox',{name:'Thread 指令'}),{target:{value:'继续解释'}})
  await waitFor(()=>expect((screen.getByRole('button',{name:'发送'}) as HTMLButtonElement).disabled).toBe(false))
  fireEvent.click(screen.getByRole('button',{name:'发送'}))
  await waitFor(()=>expect(server.commands).toHaveLength(2))
  expect(server.commands[1].kind).toBe('send_message')
  expect(server.commands[1].target.id).toBe('work_one')
})

it('opens a registered model without replacing the conversation, saved products or normal send path',async()=>{
  const server=authority({native:true,modelControls:true})
  vi.stubGlobal('fetch',server.fetcher)
  const mount=()=>render(<ThreadWorkAdapter transport={new HttpThreadTransport('','',server.fetcher,'/api/v1/threads','2')} threadId="thr_work" namespace="mixed-model" recoveryOnly />)
  mount()
  fireEvent.change(await screen.findByRole('textbox',{name:'Thread 指令'}),{target:{value:'先解释分析方法'}})
  await waitFor(()=>expect((screen.getByRole('button',{name:'发送'}) as HTMLButtonElement).disabled).toBe(false))
  fireEvent.click(screen.getByRole('button',{name:'发送'}))
  await waitFor(()=>expect(server.commands[0]?.kind).toBe('send_message'))
  await act(async()=>{server.publishFile('notes.md');server.finish()})
  await screen.findByText('来自真实事件的测试结果')
  fireEvent.click(await screen.findByRole('button',{name:'模型目录'}))
  fireEvent.change(screen.getByRole('listbox',{name:'目标电网模型'}),{target:{value:'ieee39'}})
  await screen.findByRole('button',{name:'当前模型：IEEE-39'})
  expect(server.commands[1].target).toEqual({kind:'model_workspace',id:'thr_work',expected_revision:4})
  expect(screen.queryByRole('button',{name:'保存任务'})).toBeNull()
  expect(screen.queryByRole('button',{name:'开始任务'})).toBeNull()
  expect(screen.getByText('来自真实事件的测试结果')).toBeTruthy()
  expect(screen.queryByText('当前会话的执行能力暂不可用，可保留草稿并稍后重试。')).toBeNull()
  fireEvent.change(screen.getByRole('textbox',{name:'Thread 指令'}),{target:{value:'对当前模型运行潮流'}})
  await waitFor(()=>expect((screen.getByRole('button',{name:'发送'}) as HTMLButtonElement).disabled).toBe(false))
  fireEvent.click(screen.getByRole('button',{name:'发送'}))
  await waitFor(()=>expect(server.commands).toHaveLength(3))
  expect(server.commands[2].kind).toBe('send_message')
  expect(server.commands[2].target.id).toBe('work_one')
  cleanup();mount()
  await screen.findByRole('textbox',{name:'Thread 指令'})
  expect(screen.queryByRole('button',{name:'保存任务'})).toBeNull()
  expect(await screen.findByText('来自真实事件的测试结果')).toBeTruthy()
})

it('recovers an uncertain native send after a terminal event and refresh with its exact original request',async()=>{
  const server=authority({native:true,lostMessage:true})
  vi.stubGlobal('fetch',server.fetcher)
  const mount=()=>render(<ThreadWorkAdapter transport={new HttpThreadTransport('','',server.fetcher,'/api/v1/threads','2')} threadId="thr_work" namespace="native-recovery" recoveryOnly />)
  mount()
  fireEvent.change(await screen.findByRole('textbox',{name:'Thread 指令'}),{target:{value:'保存这个问题的回答'}})
  await waitFor(()=>expect((screen.getByRole('button',{name:'发送'}) as HTMLButtonElement).disabled).toBe(false))
  fireEvent.click(screen.getByRole('button',{name:'发送'}))
  await screen.findByRole('button',{name:'重试发送请求'})
  await act(async()=>server.finish())
  cleanup();mount()
  const retry=await screen.findByRole('button',{name:'重试发送请求'})
  await waitFor(()=>expect((retry as HTMLButtonElement).disabled).toBe(false))
  fireEvent.click(retry)
  await waitFor(()=>expect(server.commands).toHaveLength(2))
  expect(server.commands[1]).toEqual(server.commands[0])
  await waitFor(()=>expect(screen.queryByRole('button',{name:'重试发送请求'})).toBeNull())
  expect(server.attemptsCreated).toBe(1)
  expect((screen.getByRole('textbox',{name:'Thread 指令'}) as HTMLTextAreaElement).value).toBe('')
  expect(screen.getByText('保存这个问题的回答')).toBeTruthy()
  expect(screen.getByText('来自真实事件的测试结果')).toBeTruthy()
})

it('keeps native stop on the real Attempt and blocks new sends when host execution is unavailable',async()=>{
  const unavailable=authority({native:true,nativeAvailable:false})
  vi.stubGlobal('fetch',unavailable.fetcher)
  render(<ThreadWorkAdapter transport={new HttpThreadTransport('','',unavailable.fetcher,'/api/v1/threads','2')} threadId="thr_work" namespace="native-offline" recoveryOnly />)
  await screen.findByText('当前会话的执行能力暂不可用，可保留草稿并稍后重试。')
  fireEvent.change(screen.getByRole('textbox',{name:'Thread 指令'}),{target:{value:'暂存草稿'}})
  expect((screen.getByRole('button',{name:'发送'}) as HTMLButtonElement).disabled).toBe(true)
  expect(unavailable.commands).toHaveLength(0)
  cleanup()
  const server=authority({native:true})
  vi.stubGlobal('fetch',server.fetcher)
  render(<ThreadWorkAdapter transport={new HttpThreadTransport('','',server.fetcher,'/api/v1/threads','2')} threadId="thr_work" namespace="native-stop" recoveryOnly />)
  fireEvent.change(await screen.findByRole('textbox',{name:'Thread 指令'}),{target:{value:'开始讨论'}})
  await waitFor(()=>expect((screen.getByRole('button',{name:'发送'}) as HTMLButtonElement).disabled).toBe(false))
  fireEvent.click(screen.getByRole('button',{name:'发送'}))
  fireEvent.click(await screen.findByRole('button',{name:'停止任务'}))
  await waitFor(()=>expect(server.commands.at(-1)?.kind).toBe('cancel_work'))
})

it('references an actual process ledger item in the next native submission',async()=>{
  const server=authority({native:true})
  vi.stubGlobal('fetch',server.fetcher)
  render(<ThreadWorkAdapter transport={new HttpThreadTransport('','',server.fetcher,'/api/v1/threads','2')} threadId="thr_work" namespace="native-reference" recoveryOnly />)
  fireEvent.change(await screen.findByRole('textbox',{name:'Thread 指令'}),{target:{value:'先分析这个问题'}})
  await waitFor(()=>expect((screen.getByRole('button',{name:'发送'}) as HTMLButtonElement).disabled).toBe(false))
  fireEvent.click(screen.getByRole('button',{name:'发送'}))
  await waitFor(()=>expect(server.commands).toHaveLength(1))
  await act(async()=>server.finish())
  await screen.findByText('来自真实事件的测试结果')
  fireEvent.click(screen.getByRole('button',{name:'打开展示区'}))
  fireEvent.click(await screen.findByRole('button',{name:'查看：已完成的原指令'}))
  fireEvent.click(await screen.findByRole('button',{name:'引用到下一轮'}))
  fireEvent.change(screen.getByRole('textbox',{name:'Thread 指令'}),{target:{value:'结合此前结果继续'}})
  await waitFor(()=>expect((screen.getByRole('button',{name:'发送'}) as HTMLButtonElement).disabled).toBe(false))
  fireEvent.click(screen.getByRole('button',{name:'发送'}))
  await waitFor(()=>expect(server.commands).toHaveLength(2))
  expect(server.commands[1].payload.context_product_refs).toEqual([{ref:expect.objectContaining({origin:'process_record',attempt_id:'attempt_one',work_id:'work_one',digest:'a'.repeat(64)}),purpose:'historical-context'}])
  expect(server.commands[1].payload.source_attempt_id).toBeUndefined()
})

it('opens the completed primary file and leaves later updates under user control',async()=>{
  vi.stubGlobal('crypto',webcrypto)
  vi.stubGlobal('URL',class extends URL {static createObjectURL=vi.fn(()=> 'blob:native-file');static revokeObjectURL=vi.fn()})
  const server=authority({native:true})
  vi.stubGlobal('fetch',server.fetcher)
  render(<ThreadWorkAdapter transport={new HttpThreadTransport('','',server.fetcher,'/api/v1/threads','2')} threadId="thr_work" namespace="native-files" recoveryOnly />)
  fireEvent.change(await screen.findByRole('textbox',{name:'Thread 指令'}),{target:{value:'请生成说明文件'}})
  await waitFor(()=>expect((screen.getByRole('button',{name:'发送'}) as HTMLButtonElement).disabled).toBe(false))
  fireEvent.click(screen.getByRole('button',{name:'发送'}))
  await waitFor(()=>expect(server.commands).toHaveLength(1))
  await act(async()=>server.publishFile('analysis.py'))
  expect(screen.queryByRole('complementary',{name:'成果'})).toBeNull()
  await act(async()=>server.publishFile('first.md','primary'))
  await act(async()=>server.finish())
  await screen.findByRole('complementary',{name:'成果'})
  expect(screen.getByRole('tab',{name:'成果'}).getAttribute('aria-selected')).toBe('true')
  fireEvent.click(screen.getByRole('button',{name:'关闭成果'}))
  await act(async()=>server.publishFile('second.md'))
  const second=await screen.findByRole('button',{name:'打开指令文件：second.md'})
  expect(screen.queryByRole('complementary',{name:'成果'})).toBeNull()
  fireEvent.click(second)
  await screen.findByRole('heading',{name:'second.md'})
})
it('waits for the terminal index to prefer the report when a primary CSV is published first',async()=>{
  vi.stubGlobal('crypto',webcrypto)
  vi.stubGlobal('URL',class extends URL {static createObjectURL=vi.fn(()=> 'blob:live-report');static revokeObjectURL=vi.fn()})
  const server=authority({native:true})
  vi.stubGlobal('fetch',server.fetcher)
  render(<ThreadWorkAdapter transport={new HttpThreadTransport('','',server.fetcher,'/api/v1/threads','2')} threadId="thr_work" namespace="live-primary-order" recoveryOnly />)
  fireEvent.change(await screen.findByRole('textbox',{name:'Thread 指令'}),{target:{value:'生成报告和指标'}})
  await waitFor(()=>expect((screen.getByRole('button',{name:'发送'}) as HTMLButtonElement).disabled).toBe(false))
  fireEvent.click(screen.getByRole('button',{name:'发送'}))
  await waitFor(()=>expect(server.commands).toHaveLength(1))
  await act(async()=>server.publishFile('key_metrics.csv','primary'))
  await screen.findByRole('button',{name:'打开指令文件：key_metrics.csv'})
  expect(screen.queryByRole('complementary',{name:'成果'})).toBeNull()
  await act(async()=>server.publishFile('report.html','primary'))
  await act(async()=>server.finish())
  await screen.findByRole('complementary',{name:'成果'})
  await screen.findByRole('heading',{name:'report.html'})
  expect(screen.queryByRole('heading',{name:'key_metrics.csv'})).toBeNull()
})
it('preserves an explicit CSV selection when the report arrives and the attempt completes',async()=>{
  vi.stubGlobal('crypto',webcrypto)
  vi.stubGlobal('URL',class extends URL {static createObjectURL=vi.fn(()=> 'blob:manual-csv');static revokeObjectURL=vi.fn()})
  const server=authority({native:true})
  vi.stubGlobal('fetch',server.fetcher)
  render(<ThreadWorkAdapter transport={new HttpThreadTransport('','',server.fetcher,'/api/v1/threads','2')} threadId="thr_work" namespace="manual-primary-order" recoveryOnly />)
  fireEvent.change(await screen.findByRole('textbox',{name:'Thread 指令'}),{target:{value:'生成报告和指标'}})
  await waitFor(()=>expect((screen.getByRole('button',{name:'发送'}) as HTMLButtonElement).disabled).toBe(false))
  fireEvent.click(screen.getByRole('button',{name:'发送'}))
  await waitFor(()=>expect(server.commands).toHaveLength(1))
  await act(async()=>server.publishFile('key_metrics.csv','primary'))
  fireEvent.click(await screen.findByRole('button',{name:'打开指令文件：key_metrics.csv'}))
  await screen.findByRole('heading',{name:'key_metrics.csv'})
  await act(async()=>server.publishFile('report.html','primary'))
  await act(async()=>server.finish())
  await waitFor(()=>expect(screen.queryByRole('button',{name:'停止'})).toBeNull())
  expect(screen.getByRole('heading',{name:'key_metrics.csv'})).toBeTruthy()
  expect(screen.queryByRole('heading',{name:'report.html'})).toBeNull()
})
it('restores the completed current primary report into the existing pane without a new command',async()=>{
  vi.stubGlobal('crypto',webcrypto)
  vi.stubGlobal('URL',class extends URL {static createObjectURL=vi.fn(()=> 'blob:completed-report');static revokeObjectURL=vi.fn()})
  const server=authority({native:true,existingWork:true})
  server.work.latest_attempt_id='attempt_one'
  server.publishFile('analysis.py')
  // Historical public events remain unchanged; the host index supplies role projection.
  server.publishFile('report.html')
  server.publishFile('metrics.csv')
  server.projectPrimary('report.html');server.projectPrimary('metrics.csv')
  server.finish()
  vi.stubGlobal('fetch',server.fetcher)
  render(<ThreadWorkAdapter transport={new HttpThreadTransport('','',server.fetcher,'/api/v1/threads','2')} threadId="thr_work" namespace="completed-report" recoveryOnly />)
  await screen.findByRole('complementary',{name:'成果'})
  await screen.findByRole('heading',{name:'report.html'})
  expect(screen.getByRole('button',{name:'打开指令文件：report.html'})).toBeTruthy()
  expect(screen.getByRole('button',{name:'打开指令文件：metrics.csv'})).toBeTruthy()
  expect(screen.getByText('有限交付 · 保留已知问题与未检查项')).toBeTruthy()
  fireEvent.click(screen.getByText('交付限制 · 1'))
  expect(screen.getByText('图表尚未完成独立核验')).toBeTruthy()
  expect(server.commands).toHaveLength(0)
})

it('preserves an existing legacy material choice through the first Work binding',async()=>{
  const server=authority({native:true})
  await server.fetcher('/api/v1/threads/thr_work/materials',{method:'POST',body:new File(['hello'],'notes.md')})
  vi.stubGlobal('fetch',server.fetcher)
  render(<ThreadWorkAdapter transport={new HttpThreadTransport('','',server.fetcher,'/api/v1/threads','2')} threadId="thr_work" namespace="native-materials" recoveryOnly />)
  await screen.findByRole('textbox',{name:'Thread 指令'})
  await screen.findByRole('button',{name:'资料：notes.md'})
  expect(server.commands).toHaveLength(0)
  fireEvent.click(screen.getByRole('button',{name:'资料：notes.md'}))
  const choice=await screen.findByRole('checkbox',{name:'读取资料 notes.md'})
  expect((choice as HTMLInputElement).checked).toBe(true)
  fireEvent.click(choice)
  fireEvent.click(screen.getByRole('button',{name:'关闭上下文'}))
  fireEvent.change(screen.getByRole('textbox',{name:'Thread 指令'}),{target:{value:'本轮先不读取文件'}})
  await waitFor(()=>expect((screen.getByRole('button',{name:'发送'}) as HTMLButtonElement).disabled).toBe(false))
  fireEvent.click(screen.getByRole('button',{name:'发送'}))
  await waitFor(()=>expect(server.commands).toHaveLength(1))
  expect(server.commands[0].payload.material_refs).toEqual([])
  await act(async()=>server.finish())
  await screen.findByText('来自真实事件的测试结果')
  fireEvent.click(screen.getByRole('button',{name:'本轮上下文'}))
  expect((screen.getByRole('checkbox',{name:'读取资料 notes.md'}) as HTMLInputElement).checked).toBe(false)
  fireEvent.click(screen.getByRole('button',{name:'移除资料 notes.md'}))
  await waitFor(()=>expect(screen.queryByRole('checkbox',{name:'读取资料 notes.md'})).toBeNull())
})

it('retains older saved Work records and their isolated drafts when native conversation becomes available',async()=>{
  const server=authority({native:true,existingWork:true,legacySaved:true})
  vi.stubGlobal('fetch',server.fetcher)
  render(<ThreadWorkAdapter transport={new HttpThreadTransport('','',server.fetcher,'/api/v1/threads','2')} threadId="thr_work" namespace="legacy-native" recoveryOnly />)
  await screen.findByRole('textbox',{name:'Thread 指令'})
  fireEvent.click(screen.getByRole('button',{name:'01 · 测试目标'}))
  const oldDraft=await screen.findByRole('textbox',{name:'历史记录草稿'})
  fireEvent.change(oldDraft,{target:{value:'保留在旧记录中的草稿'}})
  expect((screen.getByRole('button',{name:'确认原保存请求'}) as HTMLButtonElement).disabled).toBe(true)
  expect(screen.queryByRole('button',{name:'开始任务'})).toBeNull()
  expect(screen.getByText('测试目标')).toBeTruthy()
  fireEvent.click(screen.getByRole('button',{name:'返回当前对话'}))
  expect((await screen.findByRole('textbox',{name:'Thread 指令'}) as HTMLTextAreaElement).value).toBe('')
  fireEvent.click(screen.getByRole('button',{name:'01 · 测试目标'}))
  expect((await screen.findByRole('textbox',{name:'历史记录草稿'}) as HTMLTextAreaElement).value).toBe('保留在旧记录中的草稿')
  expect(server.commands).toHaveLength(0)
})

it('keeps an executable legacy Work recovery-only without admitting a new start or cancel', async () => {
  const server = authority({ existingWork: true })
  vi.stubGlobal('fetch', server.fetcher)
  render(<ThreadWorkAdapter transport={new HttpThreadTransport('', '', server.fetcher, '/api/v1/threads', '2')} threadId="thr_work" namespace="recovery" recoveryOnly />)
  fireEvent.click(await screen.findByRole('button', {name:'01 · 测试目标'}))
  await screen.findByRole('textbox', {name:'补充任务资料'})
  expect(screen.queryByRole('button', {name:'开始任务'})).toBeNull()
  expect(screen.queryByRole('button', {name:'停止任务'})).toBeNull()
  expect(server.commands).toHaveLength(0)
})

it('retains stopping the owned active Attempt when reopening through recovery', async () => {
  const server = authority()
  await saveGoal(server)
  fireEvent.click(screen.getByRole('button', {name:'开始任务'}))
  await screen.findByText('修订 1 · 已排队')
  cleanup()
  render(<ThreadWorkAdapter transport={new HttpThreadTransport('', '', server.fetcher, '/api/v1/threads', '2')} threadId="thr_work" namespace="active-recovery" recoveryOnly />)
  fireEvent.click(await screen.findByRole('button', {name:'01 · 测试目标'}))
  expect(screen.queryByRole('button', {name:'开始任务'})).toBeNull()
  const stop=await screen.findByRole('button', {name:'停止任务'})
  await waitFor(()=>expect((stop as HTMLButtonElement).disabled).toBe(false))
  fireEvent.click(stop)
  await waitFor(()=>expect(server.commands.at(-1)?.kind).toBe('cancel_work'))
  expect(server.attemptsCreated).toBe(1)
})

it('retries only the exact saved start request in the recovery entry', async () => {
  const server = authority({ existingWork: true })
  vi.stubGlobal('fetch', server.fetcher)
  const original=buildStartWorkCommand('thr_work','run_work','cmd_original','idem_original','work_one',1)
  writePendingCommands('pending-recovery.thr_work',[original])
  render(<ThreadWorkAdapter transport={new HttpThreadTransport('', '', server.fetcher, '/api/v1/threads', '2')} threadId="thr_work" namespace="pending-recovery" recoveryOnly />)
  const retry=await screen.findByRole('button',{name:'重试执行请求'})
  await waitFor(()=>expect((retry as HTMLButtonElement).disabled).toBe(false))
  fireEvent.click(retry)
  await waitFor(()=>expect(server.commands).toEqual([original]))
  await screen.findByText('修订 1 · 已排队')
  expect(screen.queryByRole('button',{name:'开始任务'})).toBeNull()
})

it('reads a real v1 Thread, upgrades only on Work save, and displays streamed execution and results', async () => {
  const server = authority()
  await saveGoal(server)
  expect(server.upgraded).toBe(true)
  fireEvent.click(screen.getByRole('button', { name: '开始任务' }))
  await screen.findByText('修订 1 · 已排队')
  expect(server.commands[1].kind).toBe('start_work')
  expect(server.commands[1].payload).toEqual({})
  await act(async () => server.started())
  await screen.findByText('修订 1 · 执行中')
  await act(async () => server.finish())
  expect(screen.queryByRole('alert')?.textContent).toBeUndefined()
  await screen.findByText('来自真实事件的测试结果')
  expect(screen.getByText('修订 1 · 已完成')).toBeTruthy()
  expect(document.querySelectorAll('.capstone-chat-message.is-user')).toHaveLength(1)
  fireEvent.click(screen.getByRole('button', { name: '查看计算结果' }))
  expect(await screen.findByRole('region', { name: '结构化计算结果' })).toBeTruthy()
  const reads = server.snapshots
  await act(async () => server.disconnect())
  await waitFor(() => expect(server.snapshots).toBeGreaterThan(reads), { timeout: 3000 })
  expect(server.commands).toHaveLength(2)
  expect(screen.getAllByText('来自真实事件的测试结果')).toHaveLength(1)
})

it('recovers a lost start receipt with the exact key and creates one Attempt', async () => {
  const server = authority({ lostStart: true })
  await saveGoal(server)
  fireEvent.click(screen.getByRole('button', { name: '开始任务' }))
  await waitFor(() => expect((screen.getByRole('button', { name: '重试执行请求' }) as HTMLButtonElement).disabled).toBe(false))
  fireEvent.click(screen.getByRole('button', { name: '重试执行请求' }))
  await screen.findByText('执行请求已接收；排队、执行与结果以实际任务状态为准。')
  const starts = server.commands.filter(command => command.kind === 'start_work')
  expect(starts).toHaveLength(2); expect(starts[1]).toEqual(starts[0]); expect(server.attemptsCreated).toBe(1)
})

it('uses the shared stop action and waits for the real terminal event', async () => {
  const server = authority()
  await saveGoal(server)
  fireEvent.click(screen.getByRole('button', { name: '开始任务' }))
  await screen.findByRole('button', { name: '停止任务' })
  await act(async () => server.started())
  fireEvent.click(screen.getByRole('button', { name: '停止任务' }))
  await screen.findByText('修订 1 · 停止请求中')
  expect(server.commands.at(-1)?.kind).toBe('cancel_work')
  expect(screen.queryByText('修订 1 · 已取消')).toBeNull()
  expect((screen.getByRole('button', { name: '停止请求中' }) as HTMLButtonElement).disabled).toBe(true)
  await act(async () => server.finish(true))
  await screen.findByText('修订 1 · 已取消')
})

it('shows a readable unavailable reason for a model-free Work without starting it', async () => {
  const server = authority({ modelFree: true })
  vi.stubGlobal('fetch', server.fetcher)
  render(<ThreadLiveEntry threadId="thr_work" mode="work" />)
  fireEvent.click(await screen.findByRole('button', { name: '01 · 测试目标' }))
  expect((screen.getByRole('button', { name: '开始任务' }) as HTMLButtonElement).disabled).toBe(true)
  expect(screen.getByText('当前任务的执行能力尚未接通，仍可保存目标和资料。')).toBeTruthy()
  expect(server.commands).toHaveLength(0)
})

it('recovers a lost stop receipt with the same target and key without repeating the state change', async () => {
  const server = authority({ lostCancel: true })
  await saveGoal(server)
  fireEvent.click(screen.getByRole('button', { name: '开始任务' }))
  await screen.findByRole('button', { name: '停止任务' })
  await act(async () => server.started())
  const before = server.work.revision
  fireEvent.click(screen.getByRole('button', { name: '停止任务' }))
  await waitFor(() => expect((screen.getByRole('button', { name: '重试停止请求' }) as HTMLButtonElement).disabled).toBe(false))
  fireEvent.click(screen.getByRole('button', { name: '重试停止请求' }))
  await screen.findByText('停止请求已接收，正在等待实际执行停止。')
  const cancels = server.commands.filter(command => command.kind === 'cancel_work')
  expect(cancels).toHaveLength(2); expect(cancels[1]).toEqual(cancels[0])
  expect(server.work.revision).toBe(before + 1)
  expect(server.work.status).toBe('running')
  await act(async () => server.finish(true))
  await screen.findByText('修订 1 · 已取消')
})

it('can resolve the original lost stop receipt after the real terminal state has arrived', async () => {
  const server = authority({ lostCancel: true })
  await saveGoal(server)
  fireEvent.click(screen.getByRole('button', { name: '开始任务' }))
  await screen.findByRole('button', { name: '停止任务' })
  await act(async () => server.started())
  fireEvent.click(screen.getByRole('button', { name: '停止任务' }))
  await screen.findByRole('button', { name: '重试停止请求' })
  await act(async () => server.finish(true))
  await screen.findByText('修订 1 · 已取消')
  await waitFor(() => expect((screen.getByRole('button', { name: '重试停止请求' }) as HTMLButtonElement).disabled).toBe(false))
  const terminalRevision = server.work.revision
  fireEvent.click(screen.getByRole('button', { name: '重试停止请求' }))
  await screen.findByText('停止请求已确认。')
  expect(screen.queryByRole('button', { name: '重试停止请求' })).toBeNull()
  expect((screen.getByRole('button', { name: '开始任务' }) as HTMLButtonElement).disabled).toBe(false)
  const cancels = server.commands.filter(command => command.kind === 'cancel_work')
  expect(cancels).toHaveLength(2); expect(cancels[1]).toEqual(cancels[0])
  expect(server.work.revision).toBe(terminalRevision)
})
