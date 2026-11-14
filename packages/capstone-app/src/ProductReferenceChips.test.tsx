import {render,screen,fireEvent,cleanup} from '@testing-library/react'
import {afterEach,expect,it,vi} from 'vitest'
import ProductReferenceChips from './ProductReferenceChips'
import {productSelectionKey,type ContextProductRef,type ProductRef} from './threadProducts'

afterEach(cleanup)
it('removes only the selected paragraph from a shared parent',()=>{
  const ref:ProductRef={schema:'capstone-product-ref/1',thread_id:'thr_one',product_id:'file_one',origin:'native_file',scope:'instruction',event_seq:1,revision:null,digest:'a'.repeat(64),work_id:null,attempt_id:null,producer_attempt_id:null}
  const selections:ContextProductRef[]=['opaque_one','opaque_two'].map(block_id=>({ref,purpose:'historical-context',local_selection:{schema:'capstone-local-product-selection/1',parent_ref:ref,index_ref:'b'.repeat(64),content_digest:'c'.repeat(64),block_id,purpose:'historical-context'}}))
  const remove=vi.fn()
  render(<ProductReferenceChips selections={selections} onRemove={remove}/>)
  const buttons=screen.getAllByRole('button')
  expect(buttons).toHaveLength(2)
  expect(buttons[1].getAttribute('aria-label')).toContain('段落引用 2')
  fireEvent.click(buttons[1])
  expect(remove).toHaveBeenCalledWith(productSelectionKey(selections[1]))
  expect(productSelectionKey(selections[0])).not.toBe(productSelectionKey(selections[1]))
})
