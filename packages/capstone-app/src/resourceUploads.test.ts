import {expect,it,vi} from 'vitest'
import {File} from 'node:buffer'
import {webcrypto,createHash} from 'node:crypto'
import {transferResource} from './resourceUploads'

it('resumes verified parts and never reads the full file into memory',async()=>{
  vi.stubGlobal('crypto',webcrypto)
  const file=new File(['abcdefghij'],'data.csv')
  const full=vi.spyOn(file,'arrayBuffer').mockRejectedValue(new Error('whole file read'))
  const uid='upload_'+'a'.repeat(32)
  const saved={schema:'capstone-resource/1',resource_id:'resource_'+'a'.repeat(32),version:1,file_name:file.name,size_bytes:10,sha256:createHash('sha256').update('abcdefghij').digest('hex')}
  const request=vi.fn(async(path:string,init?:RequestInit):Promise<unknown>=>{
    if(init?.method==='PUT'){
      const bytes=Buffer.from(await (init.body as Blob).arrayBuffer())
      expect(bytes.length).toBeLessThanOrEqual(4)
      return {size_bytes:bytes.length,sha256:createHash('sha256').update(bytes).digest('hex')}
    }
    if(path.endsWith('/complete'))return saved
    return {schema:'capstone-resource-upload/1',upload_id:uid,file_name:file.name,size_bytes:10,chunk_bytes:4,state:'uploading',received_parts:[0],part_sha256:{'0':createHash('sha256').update('abcd').digest('hex')}}
  })
  await expect(transferResource(request,'/uploads',file as unknown as globalThis.File,{uploadId:uid,requestId:'retry'})).resolves.toEqual(saved)
  expect(request.mock.calls.filter(([,init])=>init?.method==='PUT')).toHaveLength(2)
  expect(full).not.toHaveBeenCalled()
  vi.unstubAllGlobals()
})

it('rejects a different local file with the same name and size on resume',async()=>{
  vi.stubGlobal('crypto',webcrypto)
  const file=new File(['xxxx'],'data.csv')
  const request=vi.fn(async()=>({schema:'capstone-resource-upload/1',upload_id:'upload_'+'a'.repeat(32),file_name:'data.csv',size_bytes:4,chunk_bytes:4,state:'uploading',received_parts:[0],part_sha256:{'0':'0'.repeat(64)}}))
  await expect(transferResource(request,'/uploads',file as unknown as globalThis.File,{requestId:'retry'})).rejects.toThrow('不一致')
  expect(request).toHaveBeenCalledTimes(1)
  vi.unstubAllGlobals()
})
