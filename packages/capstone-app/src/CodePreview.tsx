import {useMemo,useState,type ReactNode} from 'react'
import {all,createLowlight} from 'lowlight'
import type {RootContent} from 'hast'
import {Copy,Check} from 'lucide-react'
import {codeLanguage} from './codeLanguage'
import './codePreview.css'

const highlighter=createLowlight(all)
const languages=highlighter.listLanguages().sort()
function renderNode(node:RootContent,key:number):ReactNode{
  if(node.type==='text')return node.value
  if(node.type==='element')return <span key={key} className={Array.isArray(node.properties.className)?node.properties.className.join(' '):undefined}>{node.children.map((child,index)=>renderNode(child,index))}</span>
  return null
}
/** Highlight inert AST nodes. Code is never executed or inserted as raw HTML. */
export default function CodePreview({name,text}:{name:string;text:string}){
  const inferred=codeLanguage(name)??'plaintext'
  const [choice,setChoice]=useState<{name:string;language:string}>(),[copied,setCopied]=useState(false),[copyError,setCopyError]=useState(false)
  const language=choice?.name===name?choice.language:inferred
  const visible=useMemo(()=>text.slice(0,200000).split('\n').slice(0,4000).join('\n'),[text])
  const lineCount=visible.split('\n').length
  const nodes=useMemo(()=>{
    if(language==='plaintext'||!highlighter.registered(language))return visible
    try{return highlighter.highlight(language,visible).children.map(renderNode)}catch{return visible}
  },[visible,language])
  async function copy(){try{if(!navigator.clipboard)throw new Error('unavailable');await navigator.clipboard.writeText(text);setCopied(true);setCopyError(false)}catch{setCopyError(true)}}
  return <section className="code-preview" aria-label={`代码预览：${name}`}>
    <header><select aria-label="代码语言" value={language} onChange={event=>setChoice({name,language:event.target.value})}><option value="plaintext">Plain text</option>{languages.map(item=><option key={item} value={item}>{item}</option>)}</select><span>{lineCount} 行</span><button type="button" aria-label="复制代码" title="复制代码" onClick={()=>void copy()}>{copied?<Check size={14}/>:<Copy size={14}/>}</button></header>
    {copyError&&<p role="status">复制失败，可选择代码复制。</p>}
    {visible.length<text.length&&<p>代码预览显示前 {lineCount} 行，下载可查看完整文件。</p>}
    <div className="code-preview-body"><pre className="code-preview-lines" aria-hidden="true">{Array.from({length:lineCount},(_,index)=>index+1).join('\n')}</pre><pre className="code-preview-source"><code>{nodes}</code></pre></div>
  </section>
}
