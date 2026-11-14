import {parseProductRef,productRefKey,parseRowSelection,type ProductRef,type ResultRowSelection} from './threadProducts'
import type {ResultTable} from './threadProtocol'
export type RowPage={table:ResultTable;tableVersion:string;totalRows:number;offset:number;nextOffset:number|null}
export type RowClient={readResultRows:(ref:ProductRef,table:string,offset?:number,signal?:AbortSignal,limit?:number)=>Promise<RowPage>;prepareResultRows:(ref:ProductRef,table:string,rows:string[],columns:string[],signal?:AbortSignal)=>Promise<ResultRowSelection>}
export function parseRowPage(value:unknown,ref:ProductRef,table:string,offset:number):RowPage {
 const fail=()=>{throw new Error('表格分页响应无效')}
 if(!value||typeof value!=='object'||Array.isArray(value))return fail()
 const p=value as Record<string,unknown>,t=p.table as Record<string,unknown>
 if(Object.keys(p).sort().join(',')!=='next_offset,offset,parent_ref,schema,table,table_version,total_rows'||p.schema!=='capstone-result-row-page/1'||productRefKey(parseProductRef(p.parent_ref))!==productRefKey(ref)||p.offset!==offset||typeof p.table_version!=='string'||!/^[a-f0-9]{64}$/.test(p.table_version)||!Number.isSafeInteger(p.total_rows)||(p.total_rows as number)<0||!(p.next_offset===null||Number.isSafeInteger(p.next_offset)&&(p.next_offset as number)>offset&&(p.next_offset as number)<(p.total_rows as number))||!t||t.table_id!==table||typeof t.title!=='string'||!Array.isArray(t.columns)||!t.columns.length||t.columns.length>1000||!Array.isArray(t.rows)||t.rows.length>1000)return fail()
 const columns=t.columns.map((raw:unknown)=>{const c=raw as Record<string,unknown>;if(!c||Object.keys(c).some(k=>!['column_id','label','unit'].includes(k))||typeof c.column_id!=='string'||!c.column_id||typeof c.label!=='string'||c.unit!==undefined&&typeof c.unit!=='string')return fail();return {columnId:c.column_id,label:c.label,...(c.unit===undefined?{}:{unit:c.unit as string})}})
 if(new Set(columns.map(c=>c.columnId)).size!==columns.length)return fail()
 const rows=t.rows.map((raw:unknown)=>{const r=raw as Record<string,unknown>;if(!r||typeof r.row_id!=='string'||!r.row_id||!r.cells||typeof r.cells!=='object'||Array.isArray(r.cells))return fail();const cells=r.cells as Record<string,string|number|boolean|null>;if(Object.entries(cells).some(([k,v])=>!columns.some(c=>c.columnId===k)||!(v===null||typeof v==='string'||typeof v==='boolean'||typeof v==='number'&&Number.isFinite(v))))return fail();let elementRef;if(r.element_ref!==undefined){const e=r.element_ref as Record<string,unknown>;if(!e||typeof e.element_id!=='string'||typeof e.element_kind!=='string')return fail();elementRef={elementId:e.element_id,elementKind:e.element_kind}}return {rowId:r.row_id,cells,...(elementRef?{elementRef}: {})}})
 if(new Set(rows.map(r=>r.rowId)).size!==rows.length||offset+rows.length>(p.total_rows as number))return fail()
 return {table:{tableId:table,title:t.title,columns,rows} as ResultTable,tableVersion:p.table_version,totalRows:p.total_rows as number,offset,nextOffset:p.next_offset as number|null}
}
export {parseRowSelection}
