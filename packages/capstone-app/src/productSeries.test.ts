import {expect,it} from 'vitest'
import {parseSeries,parseComparison,comparisonLines} from './productSeries'
const ref={schema:'capstone-product-ref/1',thread_id:'t',product_id:'a',origin:'native_file',scope:'instruction',event_seq:1,revision:null,digest:'a'.repeat(64),work_id:null,attempt_id:'a',producer_attempt_id:null} as const
it('checks series version, ownership and exact adopted membership',()=>{
 const state={schema:'capstone-product-series/1',thread_id:'t',series_id:'s',revision:1,members:[ref],adopted_ref:null}
 expect(parseSeries(state,'t').members).toHaveLength(1)
 expect(()=>parseSeries({...state,schema:'next'},'t')).toThrow()
 expect(()=>parseSeries(state,'other')).toThrow()
 expect(()=>parseSeries({...state,extra:true},'t')).toThrow()
})
it('uses complete line offsets with Unicode and CRLF for insertions and deletions',()=>{
 const original='共同🙂\r\n删除\u2028末尾',revised='共同🙂\r\n末尾\n新增'
 expect(comparisonLines(original)).toEqual(['共同🙂\r\n','删除\u2028','末尾'])
 const changes=[{kind:'equal',original:[0,1],revised:[0,1]},{kind:'delete',original:[1,2],revised:[1,1]},{kind:'replace',original:[2,3],revised:[1,3]}]
 expect(parseComparison({schema:'capstone-product-comparison/1',original_ref:ref,revised_ref:ref,original_text:original,revised_text:revised,changes,interpretation:'literal-text-difference'},ref,ref).changes).toHaveLength(3)
})
it('rejects invalid diff ranges rather than showing a partial comparison',()=>{
 const data={schema:'capstone-product-comparison/1',original_ref:ref,revised_ref:ref,original_text:'old',revised_text:'new',changes:[{kind:'replace',original:[0,1],revised:[0,1]}],interpretation:'literal-text-difference'}
 expect(parseComparison(data,ref,ref).changes).toHaveLength(1)
 expect(()=>parseComparison({...data,changes:[{kind:'replace',original:[0,8],revised:[0,3]}]},ref,ref)).toThrow()
})
