import {cleanup,render,screen,fireEvent} from '@testing-library/react'
import {afterEach,expect,it,vi} from 'vitest'
import {webcrypto} from 'node:crypto'
import ProductParagraphPicker from './ProductParagraphPicker'
import {parseProductRef} from './threadProducts'
import type {BlockReader} from './productBlocks'

afterEach(()=>{cleanup();vi.unstubAllGlobals()})
it('prepares a job and emits only the verified paragraph identity',async()=>{
  vi.stubGlobal('crypto',webcrypto)
  const digest='2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824'
  const ref=parseProductRef({schema:'capstone-product-ref/1',thread_id:'thr_one',product_id:'file_one',origin:'native_file',scope:'instruction',event_seq:1,revision:null,digest,work_id:null,attempt_id:null,producer_attempt_id:null})
  const job={job_id:'job_one',state:'queued' as const,parent_ref:ref}
  const read=vi.fn<BlockReader>().mockResolvedValueOnce({job}).mockResolvedValueOnce({job:{...job,state:'ready'},page:{index_ref:'b'.repeat(64),blocks:[{block_id:'opaque',byte_start:0,byte_end:5,content_digest:digest}],next_offset:null}})
  const select=vi.fn()
  render(<ProductParagraphPicker source={ref} bytes={new TextEncoder().encode('hello')} read={read} onSelect={select}/>)
  fireEvent.click(screen.getByText('选择段落引用'))
  fireEvent.click(screen.getByRole('button',{name:'准备段落'}))
  fireEvent.click(await screen.findByRole('button',{name:'刷新段落状态'}))
  fireEvent.click(await screen.findByRole('button',{name:'引用段落 1'}))
  expect(select.mock.calls[0][0]).toEqual({schema:'capstone-local-product-selection/1',parent_ref:ref,index_ref:'b'.repeat(64),block_id:'opaque',content_digest:digest,purpose:'historical-context'})
})
