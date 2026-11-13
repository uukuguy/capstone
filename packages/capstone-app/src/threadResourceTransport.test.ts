import {afterEach,expect,it,vi} from 'vitest'
import {webcrypto} from 'node:crypto'
import {HttpThreadTransport} from './threadHttpTransport'
import {initializeApplicationCapacity} from './applicationCapacity'

const id=`resource_${'a'.repeat(32)}`
afterEach(()=>{initializeApplicationCapacity({});vi.unstubAllGlobals()})

async function digest(bytes:Uint8Array){
  return Buffer.from(await webcrypto.subtle.digest('SHA-256',bytes)).toString('hex')
}

it('reads a session resource from the authenticated content route and checks its digest',async()=>{
  vi.stubGlobal('crypto',webcrypto)
  const bytes=new TextEncoder().encode('安装步骤')
  const hash=await digest(bytes)
  const fetcher=vi.fn<typeof fetch>(async function(this:unknown){
    if(this!==globalThis)throw new TypeError('Illegal invocation')
    return new Response(bytes,{headers:{'Capstone-Thread-Version':'2'}})
  })
  const result=await new HttpThreadTransport('http://localhost:8767','test-token',fetcher,'/api/v1/threads','2','enterprise').readThreadResource('thr_one',{resource_id:id,size_bytes:bytes.byteLength,sha256:hash})
  expect(new TextDecoder().decode(result)).toBe('安装步骤')
  expect(fetcher.mock.calls[0][0]).toBe(`http://localhost:8767/api/v1/threads/thr_one/resources/${id}/content`)
  const headers=new Headers(fetcher.mock.calls[0][1]?.headers)
  expect(headers.get('Authorization')).toBe('Bearer test-token')
  expect(headers.get('Capstone-Thread-Version')).toBe('2')
})

it('streams a resource above the in-memory check into the file picker',async()=>{
  vi.stubGlobal('crypto',webcrypto)
  initializeApplicationCapacity({artifact_file_bytes:4})
  const bytes=new Uint8Array([1,2,3,4,5,6,7,8])
  const hash=await digest(bytes)
  const writes:number[]=[]
  const writable={write:async(chunk:Uint8Array)=>{writes.push(chunk.byteLength)},close:vi.fn(async()=>undefined),abort:vi.fn(async()=>undefined)}
  vi.stubGlobal('showSaveFilePicker',vi.fn(async()=> ({createWritable:async()=>writable})))
  const fetcher=vi.fn<typeof fetch>(async()=>new Response(new ReadableStream({start(controller){controller.enqueue(bytes.slice(0,4));controller.enqueue(bytes.slice(4));controller.close()}})))
  await new HttpThreadTransport('','',fetcher,'/api/v1/threads','1','enterprise').saveThreadResource('thr_one',{resource_id:id,file_name:'01-安装部署手册.pdf',size_bytes:bytes.byteLength,sha256:hash})
  expect(writes.reduce((sum,size)=>sum+size,0)).toBe(bytes.byteLength)
  expect(Math.max(...writes)).toBeLessThanOrEqual(4)
  expect(writable.close).toHaveBeenCalledOnce()
  expect(writable.abort).not.toHaveBeenCalled()
  expect((globalThis as unknown as {showSaveFilePicker:ReturnType<typeof vi.fn>}).showSaveFilePicker.mock.calls[0][0].suggestedName).toBe('01-安装部署手册.pdf')
})

it('discards a large download when the streamed digest does not match',async()=>{
  vi.stubGlobal('crypto',webcrypto)
  initializeApplicationCapacity({artifact_file_bytes:4})
  const writable={write:async()=>undefined,close:vi.fn(async()=>undefined),abort:vi.fn(async()=>undefined)}
  vi.stubGlobal('showSaveFilePicker',vi.fn(async()=> ({createWritable:async()=>writable})))
  const fetcher=vi.fn<typeof fetch>(async()=>new Response(new Uint8Array([1,2,3,4,5,6,7,8])))
  await expect(new HttpThreadTransport('','',fetcher,'/api/v1/threads','1','enterprise').saveThreadResource('thr_one',{resource_id:id,file_name:'large.bin',size_bytes:8,sha256:'ab'.repeat(32)})).rejects.toThrow('文件校验失败')
  expect(writable.close).not.toHaveBeenCalled()
  expect(writable.abort).toHaveBeenCalledOnce()
})
