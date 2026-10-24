import {useEffect,useRef,useState} from 'react'
import {productRefKey,type ContextProductRef,type ProductEntry,type ProductRef,type ProductResolution} from './threadProducts'
import './threadProducts.css'

export type ProductReferenceReader=(ref:ProductRef,signal?:AbortSignal)=>Promise<ProductResolution>
export default function ProductReferenceChips({selections,read,onRemove,disabled}:{selections:readonly ContextProductRef[];read?:ProductReferenceReader;onRemove:(key:string)=>void;disabled?:boolean}) {
  const [entries,setEntries]=useState<Record<string,ProductEntry>>({})
  const [errors,setErrors]=useState<Set<string>>(new Set())
  const reader=useRef(read);reader.current=read
  const keys=JSON.stringify(selections.map(item=>productRefKey(item.ref)))
  useEffect(()=>{
    if(!reader.current)return
    const controller=new AbortController();setErrors(new Set())
    for(const item of selections){const key=productRefKey(item.ref)
      void reader.current(item.ref,controller.signal).then(value=>{if(!controller.signal.aborted&&productRefKey(value.entry.ref)===key)setEntries(current=>({...current,[key]:value.entry}))}).catch(()=>{if(!controller.signal.aborted)setErrors(current=>new Set([...current,key]))})
    }
    return()=>controller.abort()
  },[keys])
  if(!selections.length)return null
  return <div className="thread-product-references" aria-label="本轮成果引用">{selections.map(item=>{
    const key=productRefKey(item.ref),entry=entries[key],name=entry?.title||(errors.has(key)?'成果信息暂不可读取':'正在读取成果名称…')
    return <span key={key} title="历史上下文；不自动成为当前运行证据"><span>{name}{item.ref.revision?` · v${item.ref.revision}`:''}{item.excerpt?<small> · 开头摘录，最多{Math.ceil(item.excerpt.max_bytes/1024)}KiB</small>:null}</span><button type="button" disabled={disabled} aria-label={`移除成果引用：${name}`} onClick={()=>onRemove(key)}>×</button></span>
  })}</div>
}
