import {useEffect,useState} from 'react'
import {unzipSync} from 'fflate'
import {applicationCapacity} from './applicationCapacity'

import {docxMedia,openDocumentMedia} from './officeDocumentMedia'

const wordNamespaces=new Set([
  'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
  'http://purl.oclc.org/ooxml/wordprocessingml/main',
])
const office='urn:oasis:names:tc:opendocument:xmlns:office:1.0'
const table='urn:oasis:names:tc:opendocument:xmlns:table:1.0'
const drawing='urn:oasis:names:tc:opendocument:xmlns:drawing:1.0'
const textNs='urn:oasis:names:tc:opendocument:xmlns:text:1.0'
const blockLimit=600,rowLimit=200,columnLimit=50
type Block={kind:'paragraph'|'heading';text:string}|{kind:'table';rows:string[][]}

function readDocument(bytes:Uint8Array,media:string){
  const limit=applicationCapacity('preview_bytes')
  const word=media===docxMedia
  const part=word?'word/document.xml':'content.xml'
  if(bytes.length>limit)throw new Error('File exceeds preview capacity')
  let entries=0,found=false
  const files=unzipSync(bytes,{filter:entry=>{
    if(++entries>4096)throw new Error('Too many document parts')
    if(entry.name!==part)return false
    if(found||entry.originalSize<=0||entry.originalSize>limit||entry.size>bytes.length
      ||(!entry.compression&&entry.size!==entry.originalSize))throw new Error('Invalid document part size')
    found=true
    return true
  }})
  if(!files[part])throw new Error('Document content is missing')
  const source=new TextDecoder('utf-8',{fatal:true}).decode(files[part])
  if(/<!DOCTYPE/i.test(source))throw new Error('Document type declarations are unsupported')
  const doc=new DOMParser().parseFromString(source,'application/xml')
  if(doc.getElementsByTagNameNS('*','parsererror').length)throw new Error('Document XML is invalid')
  const namespace=doc.documentElement.namespaceURI??''
  if(word?!wordNamespaces.has(namespace):namespace!==office)throw new Error('Unexpected document namespace')
  const body=doc.getElementsByTagNameNS(namespace,'body')[0]
  if(!body)throw new Error('Document body is missing')

  let truncated=false,remaining=120_000,cellsLeft=10_000
  const bounded=<T,>(items:ArrayLike<T>,count:number)=>{
    if(items.length>count)truncated=true
    return Array.from({length:Math.min(items.length,count)},(_,index)=>items[index])
  }
  const blocks:Block[]=[]
  const paragraphs=(node:Element)=>{
    if(!word)return node.textContent??''
    return Array.from(node.getElementsByTagNameNS(namespace,'t'),item=>item.textContent??'').join('')
  }
  const clip=(value:string,limit:number)=>{
    const text=value.slice(0,Math.min(limit,remaining))
    if(text.length<value.length)truncated=true
    remaining-=text.length
    return text
  }
  const add=(block:Block)=>{
    if(blocks.length<blockLimit)blocks.push(block)
    else truncated=true
  }
  const addTable=(node:Element)=>{
    const ns=word?namespace:table
    const rowName=word?'tr':'table-row',cellName=word?'tc':'table-cell'
    const rows:string[][]=[]
    for(const row of bounded(node.getElementsByTagNameNS(ns,rowName),rowLimit)){
      if(cellsLeft===0){truncated=true;break}
      const cells:string[]=[]
      for(const cell of row.children){
        if(cell.namespaceURI!==ns||(cell.localName!==cellName&&(word||cell.localName!=='covered-table-cell')))continue
        const repeat=word?1:Number(cell.getAttributeNS(ns,'number-columns-repeated')??1)
        const requested=Number.isSafeInteger(repeat)&&repeat>0?repeat:1
        const count=Math.min(requested,columnLimit-cells.length,cellsLeft)
        if(count<requested)truncated=true
        if(!count)break
        const value=paragraphs(cell)||(word?'':cell.getAttributeNS(office,'value')??cell.getAttributeNS(office,'string-value')??'')
        for(let index=0;index<count;index++)cells.push(clip(value,512))
        cellsLeft-=count
      }
      const repeat=word?1:Number(row.getAttributeNS(ns,'number-rows-repeated')??1)
      const requested=Number.isSafeInteger(repeat)&&repeat>0?repeat:1
      const extra=cells.length?Math.min(requested-1,rowLimit-rows.length-1,Math.floor(cellsLeft/cells.length)):0
      rows.push(cells)
      for(let index=0;index<extra;index++)rows.push(cells.map(cell=>clip(cell,512)))
      cellsLeft-=extra*cells.length
      if(extra<requested-1&&cells.length)truncated=true
      if(rows.length>=rowLimit){truncated=true;break}
    }
    if(rows.some(row=>row.length))add({kind:'table',rows})
  }
  if(word){
    for(const block of bounded(body.children,blockLimit)){
      if(block.namespaceURI!==namespace)continue
      if(block.localName==='tbl')addTable(block)
      if(block.localName==='p'){
        const style=block.getElementsByTagNameNS(namespace,'pStyle')[0]?.getAttributeNS(namespace,'val')
        add({kind:style&&/^(heading|title)/i.test(style)?'heading':'paragraph',text:clip(paragraphs(block),8000)})
      }
    }
  }else if(media===openDocumentMedia.ods){
    for(const sheet of bounded(body.getElementsByTagNameNS(table,'table'),32)){
      add({kind:'heading',text:clip(sheet.getAttributeNS(table,'name')||'工作表',160)})
      addTable(sheet)
    }
  }else if(media===openDocumentMedia.odp){
    for(const [index,page] of bounded(body.getElementsByTagNameNS(drawing,'page'),32).entries()){
      add({kind:'heading',text:clip(page.getAttributeNS(drawing,'name')||`幻灯片 ${index+1}`,160)})
      for(const p of bounded(page.getElementsByTagNameNS(textNs,'p'),64))add({kind:'paragraph',text:clip(paragraphs(p),8000)})
    }
  }else{
    const content=body.getElementsByTagNameNS(office,'text')[0]
    if(!content)throw new Error('Text document body is missing')
    for(const block of bounded(content.children,blockLimit)){
      if(block.namespaceURI===table&&block.localName==='table')addTable(block)
      if(block.namespaceURI===textNs&&['p','h','list'].includes(block.localName))
        add({kind:block.localName==='h'?'heading':'paragraph',text:clip(paragraphs(block),8000)})
    }
  }
  return {blocks,truncated}
}

export default function OfficeDocumentPreview({url,name,media}:{url?:string;name:string;media:string}){
  const [view,setView]=useState<ReturnType<typeof readDocument>|null>()
  useEffect(()=>{
    if(!url?.startsWith('blob:')){setView(null);return}
    const request=new AbortController()
    void fetch(url,{signal:request.signal}).then(response=>{
      if(!response.ok)throw new Error('Document is unavailable')
      return response.arrayBuffer()
    }).then(bytes=>{
      if(!request.signal.aborted)setView(readDocument(new Uint8Array(bytes),media))
    }).catch(()=>{if(!request.signal.aborted)setView(null)})
    return ()=>request.abort()
  },[url,media])
  if(view===undefined)return <p role="status">正在读取文档…</p>
  if(!view)return <p role="alert">此文档无法预览，可下载原件查看。</p>
  return <section aria-label={`内容预览：${name}`} className="native-office-preview">
    <p className="native-office-preview-note">内容预览 · 完整版式请下载原件查看</p>
    {view.blocks.length===0&&<p>此文档没有可预览的正文。</p>}
    {view.blocks.map((block,index)=>block.kind==='table'
      ?<div className="capstone-chat-markdown capstone-chat-table-scroll" key={index}><table><tbody>
        {block.rows.map((row,i)=><tr key={i}>{row.map((cell,j)=><td key={j}>{cell}</td>)}</tr>)}
      </tbody></table></div>
      :block.kind==='heading'?<h5 key={index}>{block.text}</h5>:<p key={index}>{block.text}</p>)}
    {view.truncated&&<p className="native-office-preview-note">内容超过预览范围，可下载查看完整文档。</p>}
  </section>
}
