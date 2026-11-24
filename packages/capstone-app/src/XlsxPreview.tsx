import {useEffect,useMemo,useState} from 'react'
import {unzipSync} from 'fflate'
import {applicationCapacity} from './applicationCapacity'

const maxRows=200,maxColumns=50,maxSheets=64,maxCellLength=512
const relationshipNs='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
const parts=new Set(['xl/workbook.xml','xl/_rels/workbook.xml.rels','xl/sharedStrings.xml'])
const worksheetPath=/^xl\/worksheets\/[^/\\]+\.xml$/
function elements(parent:Document|Element,name:string){
  return parent.getElementsByTagNameNS('*',name)
}
function xml(bytes:Uint8Array|undefined){
  if(!bytes)throw new Error('Workbook part missing')
  const text=new TextDecoder('utf-8',{fatal:true}).decode(bytes)
  if(/<!DOCTYPE/i.test(text))throw new Error('Workbook XML declarations are not supported')
  const document=new DOMParser().parseFromString(text,'application/xml')
  if(elements(document,'parsererror').length)throw new Error('Workbook XML is invalid')
  return document
}
function richText(node:Element){
  return Array.from(node.children).map(child=>child.localName==='t'?child.textContent:
    child.localName==='r'?elements(child,'t')[0]?.textContent:'').join('')
}
function decodeWorkbook(bytes:Uint8Array){
  const limit=applicationCapacity('preview_bytes')
  if(bytes.byteLength>limit)throw new Error('Workbook exceeds preview capacity')
  let total=0,entries=0
  const files=unzipSync(bytes,{filter:entry=>{
    if(++entries>4096)throw new Error('Workbook has too many parts')
    if(!parts.has(entry.name)&&!worksheetPath.test(entry.name))return false
    if(entry.originalSize<=0||entry.size>bytes.byteLength||(!entry.compression&&entry.size!==entry.originalSize))
      throw new Error('Workbook part size is invalid')
    total+=entry.originalSize
    if(total>limit)throw new Error('Workbook exceeds expanded preview capacity')
    return true
  }})
  const relations=new Map(Array.from(elements(xml(files['xl/_rels/workbook.xml.rels']),'Relationship')).flatMap(item=>{
    const id=item.getAttribute('Id'),target=item.getAttribute('Target')
    if(!id||!target||item.getAttribute('TargetMode')==='External'||!item.getAttribute('Type')?.endsWith('/worksheet'))return []
    const path=target.startsWith('/')?target.slice(1):'xl/'+target
    return worksheetPath.test(path)&&Object.hasOwn(files,path)?[[id,path] as const]:[]
  }))
  const sheetEntries=elements(xml(files['xl/workbook.xml']),'sheet')
  const sheets=Array.from(sheetEntries).slice(0,maxSheets).flatMap(sheet=>{
    const path=relations.get(sheet.getAttributeNS(relationshipNs,'id')??sheet.getAttribute('r:id')??'')
    return path?[{name:sheet.getAttribute('name')||'工作表',bytes:files[path]}]:[]
  })
  if(!sheets.length)throw new Error('Workbook has no readable worksheet')
  const strings=files['xl/sharedStrings.xml']?elements(xml(files['xl/sharedStrings.xml']),'si'):undefined
  return {sheets,strings,truncated:sheetEntries.length>maxSheets}
}

function columnIndex(address:string,fallback:number){
  const letters=/^([A-Z]+)[1-9][0-9]*$/.exec(address)?.[1]
  return letters?Array.from(letters).reduce((number,letter)=>number*26+letter.charCodeAt(0)-64,0)-1:fallback
}
function columnLabel(index:number){
  return (index>=26?String.fromCharCode(64+Math.floor(index/26)):'')+String.fromCharCode(65+index%26)
}
function decodeSheet(workbook:ReturnType<typeof decodeWorkbook>,index:number){
  const records=elements(xml(workbook.sheets[index].bytes),'row')
  let truncated=records.length>maxRows,width=0
  const rows=Array.from(records).slice(0,maxRows).map((row,rowIndex)=>{
    const cells:string[]=[]
    let next=0
    for(const cell of row.children){
      if(cell.localName!=='c')continue
      const column=columnIndex(cell.getAttribute('r')||'',next)
      next=column+1
      if(column>=maxColumns){truncated=true;continue}
      const value=elements(cell,'v')[0]?.textContent??''
      const type=cell.getAttribute('t')
      let display=value
      if(type==='s'){
        const shared=/^[0-9]+$/.test(value)?workbook.strings?.[Number(value)]:undefined
        display=shared?richText(shared):''
      }else if(type==='inlineStr'){
        const inline=elements(cell,'is')[0]
        display=inline?richText(inline):''
      }else if(type==='b')display=value==='1'?'TRUE':value==='0'?'FALSE':''
      if(display.length>maxCellLength)truncated=true
      cells[column]=display.slice(0,maxCellLength)
      width=Math.max(width,column+1)
    }
    return {number:row.getAttribute('r')||String(rowIndex+1),cells}
  })
  return {rows,width,truncated}
}

export default function XlsxPreview({url,name}:{url?:string;name:string}){
  const [workbook,setWorkbook]=useState<ReturnType<typeof decodeWorkbook>|null>()
  const [index,setIndex]=useState(0)
  useEffect(()=>{
    const request=new AbortController()
    if(!url?.startsWith('blob:')){setWorkbook(null);return}
    void fetch(url,{signal:request.signal}).then(response=>{
      if(!response.ok)throw new Error('Workbook is unavailable')
      return response.arrayBuffer()
    }).then(data=>{
      if(!request.signal.aborted)setWorkbook(decodeWorkbook(new Uint8Array(data)))
    }).catch(()=>{if(!request.signal.aborted)setWorkbook(null)})
    return()=>request.abort()
  },[url])
  const view=useMemo(()=>{
    if(!workbook)return undefined
    try{return decodeSheet(workbook,index)}catch{return null}
  },[workbook,index])
  if(workbook===undefined)return <p role="status">正在读取工作簿…</p>
  if(!workbook)return <p role="alert">工作簿无法预览，可下载原件查看。</p>
  return <div className="native-xlsx-preview">
    <label>工作表 <select value={index} onChange={event=>setIndex(Number(event.target.value))}>
      {workbook.sheets.map((sheet,number)=><option key={number} value={number}>{sheet.name}</option>)}
    </select></label>
    {view===null?<p role="alert">此工作表无法预览，可下载原件查看。</p>:!view?.width?<p>此工作表没有可预览的数据。</p>:
      <div className="capstone-chat-markdown capstone-chat-table-scroll native-csv-preview">
        <table aria-label={`${name} · ${workbook.sheets[index].name}`}>
          <thead><tr><th scope="col">行</th>{Array.from({length:view.width},(_,column)=><th key={column} scope="col">{columnLabel(column)}</th>)}</tr></thead>
          <tbody>{view.rows.map((row,position)=><tr key={position}><th scope="row">{row.number}</th>
            {Array.from({length:view.width},(_,column)=><td key={column}>{row.cells[column]}</td>)}</tr>)}</tbody>
        </table>
      </div>}
    {(workbook.truncated||view?.truncated)&&<p>预览只显示部分内容。下载原件可查看完整工作簿。</p>}
  </div>
}
