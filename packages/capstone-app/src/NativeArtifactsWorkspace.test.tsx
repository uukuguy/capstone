import {afterEach,expect,it,vi} from 'vitest'
import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import NativeArtifactsWorkspace,{htmlPreviewDocument} from './NativeArtifactsWorkspace'
import type {NativeArtifact} from './nativeArtifacts'
import {initializeApplicationCapacity} from './applicationCapacity'

afterEach(()=>{cleanup();vi.unstubAllGlobals();initializeApplicationCapacity()})
const bytes=(text:string)=>new TextEncoder().encode(text)
function file(name:string,text:string,attempt='attempt_one',thread='thr_one'):NativeArtifact {
  const sha=(name==='one.md'?'a':'b').repeat(64)
  const artifact_id=`file-${'c'.repeat(16)}-${sha}`
  return {schema:'capstone-process-artifact/1',scope:'instruction',thread_id:thread,run_id:'run_one',turn_id:'turn_one',attempt_id:attempt,work_id:'work_one',task_snapshot_id:'snapshot_one',goal_revision:1,task_id:'native_one',artifact_id,executor_identity_sha256:'d'.repeat(64),source_status:'completed',file_name:name,media_type:'text/markdown',sha256:sha,size_bytes:bytes(text).byteLength,download_url:`/api/v1/threads/${thread}/attempts/${attempt}/artifacts/${artifact_id}`}
}
function blobUrls(){
  let index=0
  const revoke=vi.fn()
  vi.stubGlobal('URL',class extends URL {static createObjectURL=vi.fn(()=>`blob:file-${++index}`);static revokeObjectURL=revoke})
  return revoke
}
it('hard-stops debug preview loading with the exact diagnostic and no fallback or retry',async()=>{
  initializeApplicationCapacity({schema:'capstone-capacity-profile/1',mode:'debug',limits:{preview_bytes:1}})
  blobUrls()
  const artifact=file('one.md','ab')
  const client={nativeArtifacts:vi.fn().mockResolvedValue({artifacts:[artifact],hasMore:false,nextAfter:1}),nativeArtifact:vi.fn().mockResolvedValue(bytes('ab'))}
  render(<NativeArtifactsWorkspace client={client} threadId="thr_one" attemptIds={['attempt_one']} revision={1}/>)
  const alert=await screen.findByRole('alert')
  expect(alert.textContent).toContain('preview_bytes')
  expect(alert.textContent).toContain('actual=2')
  expect(alert.textContent).toContain('effective=1')
  expect(alert.textContent).toContain('artifact.preview')
  expect(screen.queryByRole('link',{name:'下载文件'})).toBeNull()
  expect(screen.queryByRole('button',{name:/重试/})).toBeNull()
  expect(client.nativeArtifact).toHaveBeenCalledTimes(1)
})
it('reads past empty record pages and previews only actual verified bytes with a download',async()=>{
  blobUrls()
  const artifact=file('one.md','# 已保存的文件\n\n内容来自读取接口。')
  const client={nativeArtifacts:vi.fn().mockResolvedValueOnce({artifacts:[],hasMore:true,nextAfter:128}).mockResolvedValue({artifacts:[artifact],hasMore:false,nextAfter:129}),nativeArtifact:vi.fn().mockResolvedValue(bytes('# 已保存的文件\n\n内容来自读取接口。'))}
  const adopt=vi.fn()
  render(<NativeArtifactsWorkspace client={client} threadId="thr_one" attemptIds={['attempt_one']} revision={1} onAdopt={adopt} />)
  await screen.findByRole('heading',{name:'已保存的文件'})
  expect(client.nativeArtifacts.mock.calls[1][2]).toBe(128)
  expect(screen.getByRole('link',{name:'下载文件'}).getAttribute('download')).toBe('one.md')
  expect(screen.queryByText('任务交付')).toBeNull()
  expect(adopt).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button',{name:'作为任务交付'}))
  expect(adopt).toHaveBeenCalledWith(artifact)
})
it('does not replace a selected file when a later file appears, and discards a stale content response',async()=>{
  const revoke=blobUrls()
  const one=file('one.md','第一个文件'),two=file('two.md','第二个文件')
  let resolveFirst!:(value:Uint8Array)=>void
  const client={nativeArtifacts:vi.fn().mockResolvedValue({artifacts:[one],hasMore:false,nextAfter:1}),nativeArtifact:vi.fn((artifact:NativeArtifact)=>artifact.file_name==='one.md'?new Promise<Uint8Array>(resolve=>{resolveFirst=resolve}):Promise.resolve(bytes('第二个文件')))}
  const view=render(<NativeArtifactsWorkspace client={client} threadId="thr_one" attemptIds={['attempt_one']} revision={1} />)
  await waitFor(()=>expect(resolveFirst).toBeDefined())
  client.nativeArtifacts.mockResolvedValue({artifacts:[one,two],hasMore:false,nextAfter:2})
  view.rerender(<NativeArtifactsWorkspace client={client} threadId="thr_one" attemptIds={['attempt_one']} revision={2} />)
  await screen.findByRole('button',{name:'two.md'})
  expect((screen.getByRole('button',{name:'one.md'})).getAttribute('aria-pressed')).toBe('true')
  fireEvent.click(screen.getByRole('button',{name:'two.md'}))
  await screen.findByText('第二个文件')
  await act(async()=>resolveFirst(bytes('第一个文件')))
  expect(screen.queryByText('第一个文件')).toBeNull()
  view.unmount()
  expect(revoke).toHaveBeenCalled()
})
it('retains file identity and offers recovery when content is unavailable',async()=>{
  blobUrls()
  const artifact=file('one.md','内容')
  const client={nativeArtifacts:vi.fn().mockResolvedValue({artifacts:[artifact],hasMore:false,nextAfter:1}),nativeArtifact:vi.fn().mockRejectedValue(new Error('410'))}
  render(<NativeArtifactsWorkspace client={client} threadId="thr_one" attemptIds={['attempt_one']} revision={1} />)
  await screen.findByRole('alert')
  expect(screen.getByRole('button',{name:'one.md'})).toBeTruthy()
  expect(screen.queryByRole('link',{name:'下载文件'})).toBeNull()
  client.nativeArtifact.mockResolvedValue(bytes('内容'))
  fireEvent.click(screen.getByRole('button',{name:'重新读取文件'}))
  await screen.findByText('内容')
})
it('does not display bytes from a previous Thread after navigation',async()=>{
  blobUrls()
  const first=file('one.md','旧会话内容'),second=file('two.md','新会话内容','attempt_two','thr_two')
  let late!:(data:Uint8Array)=>void
  const client={nativeArtifacts:vi.fn(async(thread:string)=>({artifacts:thread==='thr_one'?[first]:[second],hasMore:false,nextAfter:1})),nativeArtifact:vi.fn((artifact:NativeArtifact)=>artifact.thread_id==='thr_one'?new Promise<Uint8Array>(resolve=>{late=resolve}):Promise.resolve(bytes('新会话内容')))}
  const view=render(<NativeArtifactsWorkspace client={client} threadId="thr_one" attemptIds={['attempt_one']} revision={1}/>)
  await waitFor(()=>expect(late).toBeDefined())
  view.rerender(<NativeArtifactsWorkspace client={client} threadId="thr_two" attemptIds={['attempt_two']} revision={1}/>)
  await screen.findByText('新会话内容')
  await act(async()=>late(bytes('旧会话内容')))
  expect(screen.queryByText('旧会话内容')).toBeNull()
  expect(screen.queryByRole('button',{name:'one.md'})).toBeNull()
})
it('keeps verified bytes downloadable when a text file cannot be decoded as UTF-8',async()=>{
  blobUrls()
  const artifact={...file('one.md','x'),size_bytes:1}
  const client={nativeArtifacts:vi.fn().mockResolvedValue({artifacts:[artifact],hasMore:false,nextAfter:1}),nativeArtifact:vi.fn().mockResolvedValue(new Uint8Array([255]))}
  render(<NativeArtifactsWorkspace client={client} threadId="thr_one" attemptIds={['attempt_one']} revision={1}/>)
  await screen.findByText('此文件无法按 UTF-8 文本预览，可下载后查看。')
  expect(screen.getByRole('link',{name:'下载文件'})).toBeTruthy()
})
it.each([['report.HTML','<script>parent.alert(1)</script><h1>真实报告</h1>','text/html'],['chart.svg','<svg xmlns="http://www.w3.org/2000/svg"/>','image/svg+xml']])('previews generic-media %s in an isolated viewer',async(name,content,media)=>{
  blobUrls()
  const artifact={...file(name,content),media_type:'application/octet-stream'}
  const client={nativeArtifacts:vi.fn().mockResolvedValue({artifacts:[artifact],hasMore:false,nextAfter:1}),nativeArtifact:vi.fn().mockResolvedValue(bytes(content))}
  const {container}=render(<NativeArtifactsWorkspace client={client} threadId="thr_one" attemptIds={['attempt_one']} revision={1}/>)
  await screen.findByRole('link',{name:'下载文件'})
  if(media==='text/html'){
    const frame=screen.getByTitle(`HTML 预览：${name}`)
    expect(frame.getAttribute('sandbox')).toBe('')
    expect(frame.getAttribute('srcdoc')).toContain("default-src 'none'")
    const previewDocument=new DOMParser().parseFromString(frame.getAttribute('srcdoc')||'','text/html')
    expect(previewDocument.querySelector('h1')?.textContent).toBe('真实报告')
    expect(container.querySelector('script')).toBeNull()
    expect(container.querySelector('h1')).toBeNull()
  }else{
    expect(screen.getByRole('img',{name}).getAttribute('src')).toBe('blob:file-1')
    expect(container.querySelector('svg')).toBeNull()
  }
  expect((URL.createObjectURL as ReturnType<typeof vi.fn>).mock.calls[0][0].type).toBe(media)
})
it('keeps report chapter links inside the isolated preview and preserves original download text',()=>{
  const original='<a href="#section" target="_blank">章节</a><h2 id="section">正文</h2><a href="https://example.com">来源</a>'
  const parsed=new DOMParser().parseFromString(htmlPreviewDocument(original),'text/html')
  expect(parsed.querySelector('a')?.getAttribute('href')).toBe('about:srcdoc#section')
  expect(parsed.querySelector('a')?.hasAttribute('target')).toBe(false)
  expect(parsed.querySelector('h2')?.id).toBe('section')
  expect(parsed.querySelectorAll('a')[1].getAttribute('href')).toBe('https://example.com')
  expect(parsed.querySelector('style')?.textContent).toContain('prefers-reduced-motion')
  expect(original).toContain('href="#section" target="_blank"')
})
