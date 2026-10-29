import {applicationCapacity} from './applicationCapacity'
import {afterEach,expect,it,vi} from 'vitest'
import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import ThreadProductsWorkspace from './ThreadProductsWorkspace'
import {parseProductRef,type ProductEntry} from './threadProducts'

afterEach(()=>{cleanup();vi.unstubAllGlobals()})
it('opens a running primary once and retains its version through incremental updates',async()=>{
 const first:ProductEntry={...entry,ref:{...ref,origin:'native_file',product_id:'report'},title:'草稿.md',media_type:'text/markdown',source_status:'running',source:{file_name:'草稿.md',presentation_role:'primary'}}
 const next={...first,source_status:'completed',ref:{...first.ref,digest:'b'.repeat(64)}}
 const ready=vi.fn(),client={productIndex:vi.fn().mockResolvedValue({products:[first],hasMore:false,nextCursor:null}),resolveProduct:vi.fn(async(ref)=>({entry:ref.digest===first.ref.digest?first:next,bytes:null,projection:null,record:null}))}
 const props={client,threadId:'thr_one',workId:'work_current',primaryAttemptId:'attempt_one',onPrimaryReady:ready}
 const rendered=render(<ThreadProductsWorkspace {...props} revision={1}/>)
 await waitFor(()=>expect(ready).toHaveBeenCalledTimes(1))
 expect((await screen.findAllByText('交付候选')).length).toBeGreaterThan(0)
 client.productIndex.mockResolvedValue({products:[next],hasMore:false,nextCursor:null})
 rendered.rerender(<ThreadProductsWorkspace {...props} revision={2}/>)
 await waitFor(()=>expect(client.productIndex).toHaveBeenCalledTimes(2))
 expect(ready).toHaveBeenCalledTimes(1)
 expect(client.resolveProduct.mock.calls.some(([ref])=>ref.digest===next.ref.digest)).toBe(false)
 expect(screen.queryByText(/生成中/)).toBeNull()
})
const ref=parseProductRef({schema:'capstone-product-ref/1',thread_id:'thr_one',product_id:'record_one',origin:'process_record',scope:'instruction',event_seq:8,revision:null,digest:'a'.repeat(64),work_id:'work_current',attempt_id:'attempt_one',producer_attempt_id:null})
const entry:ProductEntry={ref,title:'原分析未完成',media_type:null,byte_size:null,source_status:'failed',created_at:'2026-10-17T00:00:00Z',download_url:null,source:{instruction:'原分析未完成',attempt_id:'attempt_one',status:'failed',failure_code:'data_missing'},dependencies:[],presentation:{kind:'process_record'},capabilities:{read:true,select:false},selection_unavailable_reason:'record_only',historical_only:true}
it('follows new usable running files without a manifest and ignores same-byte terminal recapture',async()=>{
 const file:ProductEntry={...entry,ref:{...ref,origin:'native_file',product_id:'table'},title:'table.csv',media_type:'text/csv',byte_size:12,source_status:'running',source:{file_name:'table.csv'}}
 const report:ProductEntry={...file,ref:{...file.ref,product_id:'report',digest:'b'.repeat(64)},title:'report.pptx',media_type:'application/vnd.openxmlformats-officedocument.presentationml.presentation',source_status:'running',source:{file_name:'report.pptx',host_artifact_id:`file-${'1'.repeat(16)}-${'b'.repeat(64)}`}}
 const ready=vi.fn(),client={productIndex:vi.fn().mockResolvedValue({products:[file],hasMore:false,nextCursor:null}),resolveProduct:vi.fn(async(ref)=>({entry:ref.product_id==='table'?file:report,bytes:null,projection:null,record:null}))}
 const props={client,threadId:'thr_one',workId:'work_current',primaryAttemptId:'attempt_one',onPrimaryReady:ready}
 const rendered=render(<ThreadProductsWorkspace {...props} runningAttemptId="attempt_one" revision={1}/>)
 await waitFor(()=>expect(ready).toHaveBeenCalledWith(file))
 expect(await screen.findByRole('heading',{name:'table.csv'})).toBeTruthy()
 expect(ready.mock.calls[0][0].source.presentation_role).toBeUndefined()
 client.productIndex.mockResolvedValue({products:[report,file],hasMore:false,nextCursor:null})
 rendered.rerender(<ThreadProductsWorkspace {...props} runningAttemptId="attempt_one" revision={2}/>)
 await waitFor(()=>expect(client.productIndex).toHaveBeenCalledTimes(2))
 await waitFor(()=>expect(ready).toHaveBeenCalledTimes(2));expect(await screen.findByRole('heading',{name:'report.pptx'})).toBeTruthy()
 const terminal={...report,ref:{...report.ref,product_id:'terminal-public-id'},source_status:'completed',source:{...report.source,presentation_role:'primary'}}
 client.productIndex.mockResolvedValue({products:[terminal,file],hasMore:false,nextCursor:null})
 rendered.rerender(<ThreadProductsWorkspace {...props} revision={3}/>)
 await waitFor(()=>expect(client.productIndex).toHaveBeenCalledTimes(3));expect(ready).toHaveBeenCalledTimes(2)
 expect(client.resolveProduct.mock.calls.some(([ref])=>ref.product_id==='terminal-public-id')).toBe(false)
 fireEvent.click(screen.getByText(/浏览产物/));fireEvent.click(screen.getByRole('button',{name:'查看：table.csv'}))
 expect(await screen.findByRole('heading',{name:'table.csv'})).toBeTruthy()
})
it.each(['data.json','analysis.py','settings.yaml','run.log','notes.txt','book.xlsx','report.docx'])('does not automatically promote unsupported or non-reader file %s',async name=>{
 const file:ProductEntry={...entry,ref:{...ref,origin:'native_file'},title:name,media_type:'text/plain',byte_size:12,source_status:'running',source:{file_name:name}}
 const ready=vi.fn(),client={productIndex:vi.fn().mockResolvedValue({products:[file],hasMore:false,nextCursor:null}),resolveProduct:vi.fn().mockResolvedValue({entry:file,bytes:null,projection:null,record:null})}
 render(<ThreadProductsWorkspace client={client} threadId="thr_one" workId="work_current" revision={1} primaryAttemptId="attempt_one" runningAttemptId="attempt_one" onPrimaryReady={ready}/>)
 await waitFor(()=>expect(client.productIndex).toHaveBeenCalledTimes(1));expect(ready).not.toHaveBeenCalled()
})
it('preserves an explicit history selection until the next running instruction resets follow scope',async()=>{
 const file:ProductEntry={...entry,ref:{...ref,origin:'native_file',product_id:'table'},title:'table.csv',media_type:'text/csv',byte_size:12,source_status:'running',source:{file_name:'table.csv'}}
 const report:ProductEntry={...file,ref:{...file.ref,product_id:'report'},title:'report.html',media_type:'text/html',source:{file_name:'report.html'}}
 const next:ProductEntry={...report,ref:{...report.ref,attempt_id:'attempt_two',product_id:'next'},title:'next.html',source:{file_name:'next.html'}}
 const history={...file,ref:{...file.ref,attempt_id:'attempt_old',product_id:'history'},title:'history.csv',source:{file_name:'history.csv'}}
 const ready=vi.fn(),client={productIndex:vi.fn().mockResolvedValue({products:[file,history],hasMore:false,nextCursor:null}),resolveProduct:vi.fn(async(ref)=>({entry:ref.product_id==='history'?history:ref.product_id==='table'?file:ref.product_id==='next'?next:report,bytes:null,projection:null,record:null}))}
 const props={client,threadId:'thr_one',workId:'work_current',onPrimaryReady:ready}
 const rendered=render(<ThreadProductsWorkspace {...props} primaryAttemptId="attempt_one" runningAttemptId="attempt_one" revision={1}/>)
 await screen.findByRole('heading',{name:'table.csv'})
 fireEvent.click(screen.getByText(/浏览产物/));fireEvent.click(screen.getByRole('button',{name:'查看：history.csv'}))
 await screen.findByRole('heading',{name:'history.csv'})
 client.productIndex.mockResolvedValue({products:[report,file],hasMore:false,nextCursor:null})
 rendered.rerender(<ThreadProductsWorkspace {...props} primaryAttemptId="attempt_one" runningAttemptId="attempt_one" revision={2}/>)
 await waitFor(()=>expect(client.productIndex).toHaveBeenCalledTimes(2));expect(ready).toHaveBeenCalledTimes(1)
 expect(screen.getByRole('heading',{name:'history.csv'})).toBeTruthy()
 client.productIndex.mockResolvedValue({products:[next,report,file],hasMore:false,nextCursor:null})
 rendered.rerender(<ThreadProductsWorkspace {...props} primaryAttemptId="attempt_two" runningAttemptId="attempt_two" revision={3}/>)
 await screen.findByRole('heading',{name:'next.html'});expect(ready).toHaveBeenCalledTimes(2)
})
it('keeps following current-instruction clicks and consumed current requests through a PPT and new digest',async()=>{
 const file:ProductEntry={...entry,ref:{...ref,origin:'native_file',product_id:'table'},title:'table.csv',media_type:'text/csv',byte_size:12,source_status:'running',source:{file_name:'table.csv'}}
 const report:ProductEntry={...file,ref:{...file.ref,product_id:'report',digest:'b'.repeat(64)},title:'report.pptx',media_type:'application/vnd.openxmlformats-officedocument.presentationml.presentation',source:{file_name:'report.pptx'}}
 const next={...report,ref:{...report.ref,digest:'c'.repeat(64)}}
 const ready=vi.fn(),client={productIndex:vi.fn().mockResolvedValue({products:[file],hasMore:false,nextCursor:null}),resolveProduct:vi.fn(async(ref)=>({entry:ref.digest===next.ref.digest?next:ref.product_id==='table'?file:report,bytes:null,projection:null,record:null}))}
 const props={client,threadId:'thr_one',workId:'work_current',primaryAttemptId:'attempt_one',runningAttemptId:'attempt_one',onPrimaryReady:ready}
 const rendered=render(<ThreadProductsWorkspace {...props} revision={1}/>)
 await screen.findByRole('heading',{name:'table.csv'});fireEvent.click(screen.getByText(/浏览产物/));fireEvent.click(screen.getByRole('button',{name:'查看：table.csv'}))
 rendered.rerender(<ThreadProductsWorkspace {...props} requested={{ref:file.ref,nonce:1}} revision={2}/>)
 await waitFor(()=>expect(client.productIndex).toHaveBeenCalledTimes(2))
 client.productIndex.mockResolvedValue({products:[report,file],hasMore:false,nextCursor:null})
 rendered.rerender(<ThreadProductsWorkspace {...props} requested={{ref:file.ref,nonce:1}} revision={3}/>)
 await screen.findByRole('heading',{name:'report.pptx'})
 client.productIndex.mockResolvedValue({products:[next,file],hasMore:false,nextCursor:null})
 rendered.rerender(<ThreadProductsWorkspace {...props} requested={{ref:file.ref,nonce:1}} revision={4}/>)
 await waitFor(()=>expect(client.resolveProduct.mock.calls.some(([ref])=>ref.digest===next.ref.digest)).toBe(true))
 expect(ready).toHaveBeenCalledTimes(3)
})
it('does not take over an explicit manual graph view when a new current report arrives',async()=>{
 const file:ProductEntry={...entry,ref:{...ref,origin:'native_file',product_id:'table'},title:'table.csv',media_type:'text/csv',byte_size:12,source_status:'running',source:{file_name:'table.csv'}}
 const report={...file,ref:{...file.ref,product_id:'report'},title:'report.html',media_type:'text/html',source:{file_name:'report.html'}}
 const ready=vi.fn(),client={productIndex:vi.fn().mockResolvedValue({products:[file],hasMore:false,nextCursor:null}),resolveProduct:vi.fn().mockResolvedValue({entry:file,bytes:null,projection:null,record:null})}
 const props={client,threadId:'thr_one',workId:'work_current',primaryAttemptId:'attempt_one',runningAttemptId:'attempt_one',onPrimaryReady:ready}
 const rendered=render(<ThreadProductsWorkspace {...props} revision={1}/>)
 await screen.findByRole('heading',{name:'table.csv'})
 client.productIndex.mockResolvedValue({products:[report,file],hasMore:false,nextCursor:null})
 rendered.rerender(<ThreadProductsWorkspace {...props} followAvailable={false} revision={2}/>)
 await waitFor(()=>expect(client.productIndex).toHaveBeenCalledTimes(2));expect(ready).toHaveBeenCalledTimes(1)
 expect(screen.getByRole('heading',{name:'table.csv'})).toBeTruthy()
})
it.each(['past-attempt','past-work','not-running','unknown-size','over-limit'])('requires exact active identity and bounded size for fallback: %s',async kind=>{
 const file:ProductEntry={...entry,ref:{...ref,origin:'native_file',...(kind==='past-attempt'?{attempt_id:'past'}:{}),...(kind==='past-work'?{work_id:'past'}:{})},title:'table.csv',media_type:'text/csv',byte_size:kind==='unknown-size'?null:kind==='over-limit'?applicationCapacity('preview_bytes')+1:12,source_status:'running',source:{file_name:'table.csv'}}
 const ready=vi.fn(),client={productIndex:vi.fn().mockResolvedValue({products:[file],hasMore:false,nextCursor:null}),resolveProduct:vi.fn().mockResolvedValue({entry:file,bytes:null,projection:null,record:null})}
 render(<ThreadProductsWorkspace client={client} threadId="thr_one" workId="work_current" revision={1} primaryAttemptId="attempt_one" runningAttemptId={kind==='not-running'?undefined:'attempt_one'} onPrimaryReady={ready}/>)
 await waitFor(()=>expect(client.productIndex).toHaveBeenCalledTimes(1));expect(ready).not.toHaveBeenCalled()
})
it('finds the current completed primary report beyond process pages and exposes its real files',async()=>{
  const report={...entry,ref:{...ref,origin:'native_file' as const,attempt_id:'attempt_current',product_id:'report'},title:'报告.html',media_type:'text/html',byte_size:10,source_status:'completed',source:{file_name:'报告.html',presentation_role:'primary'}}
  const metrics={...report,ref:{...report.ref,product_id:'metrics'},title:'指标.csv',media_type:'text/csv',source:{file_name:'指标.csv',presentation_role:'primary'}}
  const old={...report,ref:{...report.ref,attempt_id:'attempt_old',product_id:'old'},title:'旧报告.html'}
  const ready=vi.fn(),client={productIndex:vi.fn().mockResolvedValueOnce({products:[old,entry],hasMore:true,nextCursor:'next'}).mockResolvedValue({products:[metrics,report],hasMore:false,nextCursor:null}),resolveProduct:vi.fn().mockResolvedValue({entry:report,bytes:null,projection:null,record:null})}
  render(<ThreadProductsWorkspace client={client} threadId="thr_one" workId="work_current" revision={99} primaryAttemptId="attempt_current" onPrimaryReady={ready}/>)
  await waitFor(()=>expect(ready).toHaveBeenCalledWith(report))
  expect(client.productIndex).toHaveBeenCalledWith('thr_one',{cursor:'next'},expect.any(AbortSignal))
  expect(await screen.findByRole('heading',{name:'报告.html'})).toBeTruthy()
  fireEvent.click(screen.getByText(/浏览产物/))
  expect(screen.getByRole('button',{name:'查看：指标.csv'})).toBeTruthy()
})
it('keeps the manually opened directory visible while selecting successive products',async()=>{
  const first={...entry,title:'报告一',source:{...entry.source,presentation_role:'primary'}}
  const second={...first,title:'报告二',ref:{...first.ref,product_id:'second'}}
  const client={productIndex:vi.fn().mockResolvedValue({products:[first,second],hasMore:false,nextCursor:null}),resolveProduct:vi.fn(async(ref)=>({entry:ref.product_id===second.ref.product_id?second:first,bytes:null,projection:null,record:{}}))}
  render(<ThreadProductsWorkspace client={client} threadId="thr_one" workId="work_current" revision={1}/>)
  await screen.findByRole('heading',{name:'报告一'})
  fireEvent.click(screen.getByText(/浏览产物/))
  const directory=document.querySelector<HTMLDetailsElement>('.thread-products-directory')!
  expect(directory.open).toBe(true)
  fireEvent.click(screen.getByRole('button',{name:'查看：报告二'}))
  await screen.findByRole('heading',{name:'报告二'})
  expect(directory.open).toBe(true)
  fireEvent.click(screen.getByRole('button',{name:'查看：报告一'}))
  await screen.findByRole('heading',{name:'报告一'})
  expect(directory.open).toBe(true)
})
it('does not replace a user-selected artifact when another primary completes',async()=>{
  const report={...entry,ref:{...ref,origin:'native_file' as const,attempt_id:'attempt_current',product_id:'report'},title:'报告.html',media_type:'text/html',byte_size:10,source_status:'completed',source:{file_name:'报告.html',presentation_role:'primary'}}
  const ready=vi.fn(),client={productIndex:vi.fn().mockResolvedValue({products:[entry],hasMore:false,nextCursor:null}),resolveProduct:vi.fn().mockResolvedValue({entry,bytes:null,projection:null,record:entry.source})}
  const view=render(<ThreadProductsWorkspace client={client} threadId="thr_one" workId="work_current" revision={1} onPrimaryReady={ready}/>)
  fireEvent.click(await screen.findByRole('button',{name:'查看：原分析未完成'}))
  await screen.findByRole('heading',{name:'原分析未完成'})
  client.productIndex.mockResolvedValue({products:[report,entry],hasMore:false,nextCursor:null})
  view.rerender(<ThreadProductsWorkspace client={client} threadId="thr_one" workId="work_current" revision={2} primaryAttemptId="attempt_current" onPrimaryReady={ready}/>)
  await waitFor(()=>expect(client.productIndex).toHaveBeenCalledTimes(2))
  expect(ready).not.toHaveBeenCalled()
  expect(screen.getByRole('heading',{name:'原分析未完成'})).toBeTruthy()
})
it('removes the previous download immediately while locating a newly requested version',async()=>{
  let serial=0
  vi.stubGlobal('URL',class extends URL{static createObjectURL=()=>`blob:version-${++serial}`;static revokeObjectURL=vi.fn()})
  const old={...entry,ref:{...ref,origin:'native_file' as const},title:'report.html',media_type:'text/html',source:{artifact_id:'old',file_name:'report.html',presentation_role:'primary'}}
  const next={...old,ref:{...old.ref,product_id:'file_two',attempt_id:'attempt_two',event_seq:9,digest:'b'.repeat(64)},source:{...old.source,artifact_id:'new'}}
  const client={productIndex:vi.fn().mockResolvedValue({products:[old],hasMore:false,nextCursor:null}),resolveProduct:vi.fn(async(ref)=>({entry:ref.product_id===next.ref.product_id?next:old,bytes:new TextEncoder().encode(ref.product_id),projection:null,record:null}))}
  const props={client,threadId:'thr_one',workId:'work_current',revision:8}
  const view=render(<ThreadProductsWorkspace {...props}/>)
  expect((await screen.findByRole('link',{name:'下载文件'})).getAttribute('href')).toBe('blob:version-1')
  let finish!:(value:unknown)=>void
  client.productIndex.mockImplementationOnce(()=>new Promise(resolve=>{finish=resolve}) as never)
  view.rerender(<ThreadProductsWorkspace {...props} requested={{origin:'native_file',attemptId:'attempt_two',artifactId:'new'}}/>)
  expect(screen.queryByRole('link',{name:'下载文件'})).toBeNull()
  await act(async()=>finish({products:[next,old],hasMore:false,nextCursor:null}))
  expect((await screen.findByRole('link',{name:'下载文件'})).getAttribute('href')).toBe('blob:version-2')
})
it.each([['report.html','text/html'],['chart.svg','image/svg+xml']])('uses the real source filename to preview generic-media product %s',async(fileName,media)=>{
  const create=vi.fn((_blob:Blob)=>`blob:product`),revoke=vi.fn()
  vi.stubGlobal('URL',class extends URL{static createObjectURL=create;static revokeObjectURL=revoke})
  const file={...entry,ref:{...ref,origin:'task_delivery' as const,scope:'task' as const,revision:1},title:'正式报告',media_type:'application/octet-stream',source:{file_name:fileName},source_status:'completed'}
  const client={productIndex:vi.fn().mockResolvedValue({products:[file],hasMore:false,nextCursor:null}),resolveProduct:vi.fn().mockResolvedValue({entry:file,bytes:new TextEncoder().encode('<h1>报告</h1>'),projection:null,record:null})}
  const view=render(<ThreadProductsWorkspace client={client} threadId="thr_one" workId="work_current" revision={8}/>)
  fireEvent.click(await screen.findByRole('button',{name:'查看：正式报告'}))
  await screen.findByRole('link',{name:'下载文件'})
  expect(screen.queryByText('当前执行链尚不能读取此文件格式。')).toBeNull()
  if(media==='text/html')expect(screen.getByTitle(`HTML 预览：${fileName}`).getAttribute('sandbox')).toBe('')
  else expect(screen.getByRole('img',{name:fileName}).getAttribute('src')).toBe('blob:product')
  expect(create.mock.calls[0][0].type).toBe(media)
  view.unmount()
  expect(revoke).toHaveBeenCalledWith('blob:product')
})
it('browses the conversation without a work-scope selector and keeps failed records visible',async()=>{
  const client={productIndex:vi.fn().mockResolvedValue({products:[entry],hasMore:false,nextCursor:null}),resolveProduct:vi.fn().mockResolvedValue({entry,bytes:null,projection:null,record:entry.source})}
  render(<ThreadProductsWorkspace client={client} threadId="thr_one" workId="work_current" revision={8} onReference={vi.fn()}/>)
  fireEvent.click(await screen.findByRole('button',{name:'查看：原分析未完成'}))
  await screen.findByText('此项是执行记录，没有文件内容。')
  expect(client.productIndex.mock.calls[0][1]).toEqual({})
  expect(screen.queryByRole('link',{name:'下载文件'})).toBeNull()
  expect(screen.queryByRole('button',{name:'引用到下一轮'})).toBeNull()
  expect(screen.queryByRole('combobox',{name:'产物范围'})).toBeNull()
})
it('references the exact version and does not replace the selected reading view on a directory refresh',async()=>{
  const file={...entry,ref:{...ref,product_id:'result_one',origin:'domain_result' as const},title:'电网校核',media_type:'application/json',byte_size:20,source_status:'partial',capabilities:{read:true as const,select:true},selection_unavailable_reason:null,presentation:{kind:'domain_result' as const}}
  const referenced=vi.fn(),client={productIndex:vi.fn().mockResolvedValue({products:[file],hasMore:false,nextCursor:null}),resolveProduct:vi.fn().mockResolvedValue({entry:file,bytes:null,projection:null,record:null})}
  const view=render(<ThreadProductsWorkspace client={client} threadId="thr_one" workId="work_current" revision={8} onReference={referenced}/>)
  fireEvent.click(await screen.findByRole('button',{name:'查看：电网校核'}))
  fireEvent.click(await screen.findByRole('button',{name:'引用到下一轮'}))
  expect(referenced).toHaveBeenCalledWith(file)
  view.rerender(<ThreadProductsWorkspace client={client} threadId="thr_one" workId="work_current" revision={9} onReference={referenced}/>)
  expect(screen.getByRole('heading',{name:'电网校核'})).toBeTruthy()
  expect(client.resolveProduct).toHaveBeenCalledTimes(1)
})
it('offers an excerpt only when the host permits it and makes the chosen bound explicit',async()=>{
  const large={...entry,title:'大文件.csv',capabilities:{read:true as const,select:false,select_excerpt:true},selection_unavailable_reason:'input_capacity'}
  const reference=vi.fn(),client={productIndex:vi.fn().mockResolvedValue({products:[large],hasMore:false,nextCursor:null}),resolveProduct:vi.fn().mockResolvedValue({entry:large,bytes:null,projection:null,record:null})}
  render(<ThreadProductsWorkspace client={client} threadId="thr_one" workId="work_current" revision={8} onReference={reference}/>)
  fireEvent.click(await screen.findByRole('button',{name:'查看：大文件.csv'}))
  fireEvent.click(await screen.findByRole('button',{name:`引用开头摘录（最多${Math.ceil(applicationCapacity('product_excerpt_bytes')/1024)}KiB）`}))
  expect(reference).toHaveBeenCalledWith(large,{max_bytes:applicationCapacity('product_excerpt_bytes')})
})
it('ignores an old Thread resolution that finishes after navigation',async()=>{
  let finish!:(value:unknown)=>void
  const read=vi.fn().mockImplementation(()=>new Promise(resolve=>{finish=resolve}))
  const client={productIndex:vi.fn().mockResolvedValue({products:[entry],hasMore:false,nextCursor:null}),resolveProduct:read}
  const view=render(<ThreadProductsWorkspace client={client as never} threadId="thr_one" workId="work_current" revision={8}/>)
  fireEvent.click(await screen.findByRole('button',{name:'查看：原分析未完成'}))
  await waitFor(()=>expect(finish).toBeDefined())
  view.rerender(<ThreadProductsWorkspace client={client as never} threadId="thr_two" workId="work_new" revision={0}/>)
  await act(async()=>finish({entry,bytes:null,projection:null,record:entry.source}))
  expect(screen.queryByRole('heading',{name:'原分析未完成'})).toBeNull()
})
