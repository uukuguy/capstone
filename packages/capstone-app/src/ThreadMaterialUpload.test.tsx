import {afterEach,expect,it,vi} from 'vitest'
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import ThreadMaterialUpload from './ThreadMaterialUpload'
import type {ResourceTransferOptions} from './resourceUploads'

afterEach(()=>{cleanup();localStorage.clear()})
function file(name:string,content:Uint8Array=new TextEncoder().encode('hello')) {
  const value=new File([new Uint8Array(content)],name)
  Object.defineProperty(value,'arrayBuffer',{value:async()=>content.buffer})
  return value
}
const material={schema:'capstone-thread-material/1',thread_id:'thr_one',material_id:`material_${'a'.repeat(32)}`,file_name:'notes.md',display_name:'notes.md',media_type:'text/markdown',sha256:'b'.repeat(64),size_bytes:5,created_at:'2026-10-17T00:00:00Z'}
it('accepts multiple dropped files through the same uploader in order',async()=>{
  const selected=vi.fn(),upload=vi.fn(async(value:File)=>({...material,file_name:value.name,display_name:value.name}))
  render(<main className="workspace-shell"><ThreadMaterialUpload threadId="thr_one" upload={upload} onUploaded={selected}/></main>)
  const zone=screen.getByRole('main'),files=[file('one.md'),file('two.md')]
  fireEvent.dragEnter(zone,{dataTransfer:{types:['Files'],files}})
  expect(screen.getByText('松开文件，上传到当前会话')).toBeTruthy()
  fireEvent.drop(zone,{dataTransfer:{types:['Files'],files}})
  await waitFor(()=>expect(selected).toHaveBeenCalledTimes(2))
  expect(upload.mock.calls.map(call=>call[0].name)).toEqual(['one.md','two.md'])
  expect(screen.queryByText('松开文件，上传到当前会话')).toBeNull()
})
it('ignores text drags and blocks file navigation while uploading is disabled',()=>{
  const upload=vi.fn()
  render(<main className="workspace-shell"><ThreadMaterialUpload threadId="thr_one" upload={upload} onUploaded={vi.fn()} disabled/></main>)
  const zone=screen.getByRole('main')
  expect(fireEvent.drop(zone,{dataTransfer:{types:['text/plain'],files:[]}})).toBe(true)
  expect(screen.queryByRole('alert')).toBeNull()
  expect(fireEvent.drop(zone,{dataTransfer:{types:['Files'],files:[file('notes.md')]}})).toBe(false)
  expect(upload).not.toHaveBeenCalled()
  expect(screen.getByRole('alert').textContent).toContain('当前操作尚未完成')
})
it('uploads a real UTF-8 file and reports the persisted session object without sending a message',async()=>{
  const upload=vi.fn().mockResolvedValue(material),selected=vi.fn()
  render(<ThreadMaterialUpload threadId="thr_one" upload={upload} onUploaded={selected}/>)
  const value=file('notes.md')
  fireEvent.change(screen.getByLabelText('上传资料文件'),{target:{files:[value]}})
  await waitFor(()=>expect(selected).toHaveBeenCalledWith(material))
  expect(upload).toHaveBeenCalledWith(value,expect.any(AbortSignal))
  expect(screen.getByRole('status').textContent).toContain('notes.md')
})
it.each([file('scan.pdf'),file('large.txt',new Uint8Array(8*1024*1024+1)),file('broken.txt',new Uint8Array([255]))])('rejects unsupported, oversized or non-UTF-8 input before writing',async value=>{
  const upload=vi.fn()
  render(<ThreadMaterialUpload threadId="thr_one" upload={upload} onUploaded={vi.fn()}/>)
  fireEvent.change(screen.getByLabelText('上传资料文件'),{target:{files:[value]}})
  await screen.findByRole('alert')
  expect(upload).not.toHaveBeenCalled()
})
it('sends large files through bounded resource transfer without reading the whole file or claiming context readiness',async()=>{
  const value=new File(['small test allocation'],'large.csv');Object.defineProperty(value,'size',{value:1024**3+1})
  const read=vi.fn(()=>{throw new Error('whole-file read forbidden')});Object.defineProperty(value,'arrayBuffer',{value:read,configurable:true})
  const upload=vi.fn(),selected=vi.fn(),stored=vi.fn(),resourceUpload=vi.fn().mockResolvedValue({})
  render(<ThreadMaterialUpload threadId="thr_one" upload={upload} onUploaded={selected} resourceUpload={resourceUpload} onResourceUploaded={stored}/>)
  fireEvent.change(screen.getByLabelText('上传资料文件'),{target:{files:[value]}})
  await waitFor(()=>expect(stored).toHaveBeenCalledOnce())
  expect(read).not.toHaveBeenCalled();expect(upload).not.toHaveBeenCalled();expect(selected).not.toHaveBeenCalled()
  expect(resourceUpload).toHaveBeenCalledWith(value,expect.objectContaining({requestId:expect.any(String),draft:true}))
})
it('keeps a receipt after interruption and resumes after remount with the same local file',async()=>{
  const value=new File(['binary'],'source.bin',{lastModified:123})
  const id='upload_'+'c'.repeat(32)
  const transfer=vi.fn(async(_file:File,options:ResourceTransferOptions):Promise<unknown>=>{
    options.onSession?.(id)
    throw new Error('network interrupted')
  })
  const first=render(<ThreadMaterialUpload threadId="thr_one" upload={vi.fn()} onUploaded={vi.fn()} resourceUpload={transfer}/>)
  fireEvent.change(screen.getByLabelText('上传资料文件'),{target:{files:[value]}})
  await screen.findByRole('alert');first.unmount()
  transfer.mockImplementation(async()=>({}))
  render(<ThreadMaterialUpload threadId="thr_one" upload={vi.fn()} onUploaded={vi.fn()} resourceUpload={transfer}/>)
  expect(screen.getByRole('button',{name:'上传资料'}).textContent).toContain('继续上传')
  fireEvent.change(screen.getByLabelText('上传资料文件'),{target:{files:[value]}})
  await waitFor(()=>expect(screen.getByRole('button',{name:'上传资料'}).textContent).toBe('上传资料'))
  expect(transfer.mock.calls[1][1].uploadId).toBe(id)
  expect(transfer.mock.calls[1][1].requestId).toBe(transfer.mock.calls[0][1].requestId)
})

it('keeps completed attachments visible with individual remove controls',async()=>{
  const remove=vi.fn().mockResolvedValue(undefined)
  const files=['one.csv','two.csv'].map((name,i)=>({schema:'capstone-resource/1' as const,resource_id:`resource_${String(i).repeat(32)}`,thread_id:'thr_one',version:1,file_name:name,size_bytes:100,sha256:'a'.repeat(64),processing_state:'unprocessed'}))
  render(<ThreadMaterialUpload threadId="thr_one" upload={vi.fn()} onUploaded={vi.fn()} attachments={files} onRemoveAttachment={remove}/>)
  expect(screen.getAllByText(/待发送/)).toHaveLength(2)
  fireEvent.click(screen.getByRole('button',{name:'移除附件 one.csv'}))
  await waitFor(()=>expect(remove).toHaveBeenCalledWith(files[0].resource_id))
  expect(screen.getByText('two.csv')).toBeTruthy()
})
