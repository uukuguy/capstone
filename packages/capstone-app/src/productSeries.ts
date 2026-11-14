import {parseProductRef,productRefKey,type ProductRef,type ContextProductRef} from './threadProducts'
export type ProductSeries={schema:'capstone-product-series/1';thread_id:string;series_id:string;revision:number;members:ProductRef[];adopted_ref:ProductRef|null}
export type SeriesCommand={schema:'capstone-product-series-command/1';series_id:string;expected_revision:number;operation:'register'|'adopt'|'clear';product:ProductRef|null;command_id:string;idempotency_key:string}
export type Comparison={schema:'capstone-product-comparison/1';original_ref:ProductRef;revised_ref:ProductRef;original_text:string;revised_text:string;changes:{kind:'equal'|'replace'|'delete'|'insert';original:[number,number];revised:[number,number]}[];interpretation:'literal-text-difference'}
export type SeriesClient={discoverProductSeries:(ref:ProductRef,signal?:AbortSignal)=>Promise<ProductSeries|null>;commandProductSeries:(thread:string,command:SeriesCommand)=>Promise<ProductSeries>;compareProducts:(original:ProductRef,revised:ProductRef,signal?:AbortSignal)=>Promise<Comparison>;productSources:(ref:ProductRef,signal?:AbortSignal)=>Promise<ContextProductRef[]>;seriesMembers:(thread:string,series:string,after?:string,signal?:AbortSignal)=>Promise<{members:ProductRef[];next_cursor:string|null}>}
export function object(value:unknown,keys:string[]):Record<string,unknown>{
 if(!value||typeof value!=='object'||Array.isArray(value)||Object.keys(value).sort().join()!==keys.sort().join())throw new Error('成果版本响应无效。')
 return value as Record<string,unknown>
}
export function parseSeries(value:unknown,thread:string):ProductSeries{
 const v=object(value,['schema','thread_id','series_id','revision','members','adopted_ref'])
 if(v.schema!=='capstone-product-series/1'||v.thread_id!==thread||typeof v.series_id!=='string'||!v.series_id||!Number.isSafeInteger(v.revision)||(v.revision as number)<1||!Array.isArray(v.members))throw new Error('成果版本响应无效。')
 const members=v.members.map(ref=>parseProductRef(ref,thread));if(new Set(members.map(productRefKey)).size!==members.length)throw new Error('版本重复。')
 return {...v,members,adopted_ref:v.adopted_ref===null?null:parseProductRef(v.adopted_ref,thread)} as ProductSeries
}
export function parseComparison(value:unknown,original:ProductRef,revised:ProductRef):Comparison{
 const v=object(value,['schema','original_ref','revised_ref','original_text','revised_text','changes','interpretation'])
 if(v.schema!=='capstone-product-comparison/1'||v.interpretation!=='literal-text-difference'||typeof v.original_text!=='string'||typeof v.revised_text!=='string'||!Array.isArray(v.changes)||productRefKey(parseProductRef(v.original_ref))!==productRefKey(original)||productRefKey(parseProductRef(v.revised_ref))!==productRefKey(revised))throw new Error('成果对照响应无效。')
 const lengths=[comparisonLines(v.original_text).length,comparisonLines(v.revised_text).length]
 let ends=[0,0]
 for(const item of v.changes){const c=object(item,['kind','original','revised']);if(!['equal','replace','delete','insert'].includes(String(c.kind)))throw new Error('差异类型无效。');[c.original,c.revised].forEach((range,i)=>{if(!Array.isArray(range)||range.length!==2||!range.every(Number.isSafeInteger)||range[0]!==ends[i]||range[0]>range[1]||range[1]>lengths[i])throw new Error('差异范围无效。');ends[i]=range[1]})}
 if(ends.some((end,i)=>end!==lengths[i]))throw new Error('对照不完整。')
 return v as Comparison
}
/** Python str.splitlines(keepends=True), as used by the comparison contract. */
export function comparisonLines(text:string):string[]{return text.match(/[^\r\n\v\f\x1c-\x1e\x85\u2028\u2029]*(?:\r\n|[\r\n\v\f\x1c-\x1e\x85\u2028\u2029])|[^\r\n\v\f\x1c-\x1e\x85\u2028\u2029]+$/g)??[]}
