import {expect,it,vi} from 'vitest'
import {HttpThreadTransport} from './threadHttpTransport'
import {parseProductRef} from './threadProducts'
it('reads exact series discovery and two paragraph sources using the existing auth path',async()=>{
 const ref=parseProductRef({schema:'capstone-product-ref/1',thread_id:'t',product_id:'a',origin:'native_file',scope:'instruction',event_seq:1,revision:null,digest:'a'.repeat(64),work_id:null,attempt_id:null,producer_attempt_id:null})
 const local={schema:'capstone-local-product-selection/1',parent_ref:ref,index_ref:'b'.repeat(64),block_id:'one',content_digest:'c'.repeat(64),purpose:'historical-context'}
 const source={ref,purpose:'historical-context',local_selection:local}
 const fetcher=vi.fn<typeof fetch>().mockResolvedValueOnce(Response.json({series:null})).mockResolvedValueOnce(Response.json({sources:[source,{...source,local_selection:{...local,block_id:'two'}}]}))
 const transport=new HttpThreadTransport('https://host.example','private-token',fetcher)
 expect(await transport.discoverProductSeries(ref)).toBeNull()
 expect(await transport.productSources(ref)).toHaveLength(2)
 expect(JSON.parse(String(fetcher.mock.calls[0][1]?.body))).toEqual({product:ref})
 expect(new Headers(fetcher.mock.calls[0][1]?.headers).get('Authorization')).toBe('Bearer private-token')
})
