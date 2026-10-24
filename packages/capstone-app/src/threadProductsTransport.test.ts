import {afterEach,expect,it,vi} from 'vitest'
import {webcrypto} from 'node:crypto'
import {HttpThreadTransport} from './threadHttpTransport'
import {parseProductRef} from './threadProducts'

afterEach(()=>vi.unstubAllGlobals())
it('reads a scoped index and resolves an exact ref through authenticated transport with verified bytes',async()=>{
  vi.stubGlobal('crypto',webcrypto)
  const ref=parseProductRef({schema:'capstone-product-ref/1',thread_id:'thr_one',product_id:'file_one',origin:'native_file',scope:'instruction',event_seq:12,revision:null,digest:'2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824',work_id:null,attempt_id:'attempt_one',producer_attempt_id:'child_one'})
  const entry={ref,title:'analysis.txt',media_type:'text/plain',byte_size:5,source_status:'completed',created_at:'2026-10-17T00:00:00Z',download_url:null,source:{},dependencies:[],presentation:{kind:'native_file'},capabilities:{read:true,select:true},selection_unavailable_reason:null,historical_only:true}
  const fetcher=vi.fn<typeof fetch>().mockResolvedValueOnce(Response.json({schema:'capstone-product-index/1',thread_id:'thr_one',products:[entry],has_more:false,next_cursor:null})).mockResolvedValueOnce(Response.json({schema:'capstone-product-resolution/1',entry,content_base64:'aGVsbG8=',projection:null}))
  const transport=new HttpThreadTransport('https://host.example','private-token',fetcher)
  expect((await transport.readProductIndex('thr_one',{workId:null})).products[0].ref).toEqual(ref)
  expect(new URL(String(fetcher.mock.calls[0][0])).searchParams.get('work_id')).toBe('legacy')
  expect(new TextDecoder().decode((await transport.resolveProduct(ref)).bytes!)).toBe('hello')
  expect(JSON.parse(String(fetcher.mock.calls[1][1]?.body))).toEqual({ref})
  expect(new Headers(fetcher.mock.calls[1][1]?.headers).get('Authorization')).toBe('Bearer private-token')
  expect(String(fetcher.mock.calls[1][0])).not.toContain('private-token')
  fetcher.mockResolvedValueOnce(Response.json({schema:'capstone-product-resolution/1',entry,content_base64:'d3Jvbmc=',projection:null}))
  await expect(transport.resolveProduct(ref)).rejects.toThrow(/校验/)
})
