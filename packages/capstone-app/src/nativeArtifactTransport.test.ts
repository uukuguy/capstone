import {expect,it,vi} from 'vitest'
import {webcrypto} from 'node:crypto'
import {HttpThreadTransport} from './threadHttpTransport'
import type {NativeArtifact} from './nativeArtifacts'

async function artifact():Promise<NativeArtifact>{
  const bytes=new TextEncoder().encode('saved report')
  const hash=Buffer.from(await webcrypto.subtle.digest('SHA-256',bytes)).toString('hex')
  const id=`file-${'a'.repeat(16)}-${hash}`
  return {schema:'capstone-process-artifact/1',scope:'instruction',thread_id:'thr_one',run_id:'run_one',turn_id:'turn_one',attempt_id:'attempt_one',work_id:null,task_snapshot_id:null,goal_revision:null,task_id:'native_one',artifact_id:id,executor_identity_sha256:'b'.repeat(64),source_status:'completed',file_name:'report.md',media_type:'text/markdown',sha256:hash,size_bytes:bytes.length,download_url:`/api/v1/threads/thr_one/attempts/attempt_one/artifacts/${id}`}
}
it('reads only the admitted protected route and verifies original bytes',async()=>{
  vi.stubGlobal('crypto',webcrypto)
  try {
    const item=await artifact(),fetcher=vi.fn<typeof fetch>(async function(this:unknown){
      if(this!==globalThis)throw new TypeError('Illegal invocation')
      return new Response('saved report')
    })
    const result=await new HttpThreadTransport('http://localhost:8767','test-token',fetcher).readNativeArtifact(item)
    expect(new TextDecoder().decode(result)).toBe('saved report')
    expect(fetcher.mock.calls[0][0]).toBe(`http://localhost:8767${item.download_url}`)
    expect(new Headers(fetcher.mock.calls[0][1]?.headers).get('Authorization')).toBe('Bearer test-token')
  }finally{vi.unstubAllGlobals()}
})
it.each(['saved reporT','short','saved report too large'])('rejects changed or incomplete stored file bytes: %s',async content=>{
  vi.stubGlobal('crypto',webcrypto)
  try {
    const fetcher=vi.fn<typeof fetch>().mockResolvedValue(new Response(content))
    await expect(new HttpThreadTransport('','',fetcher).readNativeArtifact(await artifact())).rejects.toThrow()
  }finally{vi.unstubAllGlobals()}
})
it('rejects caller supplied external download URLs without sending credentials',async()=>{
  const fetcher=vi.fn<typeof fetch>(),item=await artifact()
  await expect(new HttpThreadTransport('','test-token',fetcher).readNativeArtifact({...item,download_url:'https://other.test/file'})).rejects.toThrow()
  expect(fetcher).not.toHaveBeenCalled()
})
