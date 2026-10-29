import {useEffect,useState} from 'react'
import type {PresentationData,SlideData} from '@office-kit/pptx'

/** Verified private file bytes only. SVG is displayed as an image, never active DOM. */
export default function PptxPreview({name,url}:{name:string;url?:string}) {
  const [deck,setDeck]=useState<{url:string;presentation:PresentationData;slides:readonly SlideData[]}>()
  const [page,setPage]=useState(0),[error,setError]=useState(''),[image,setImage]=useState<{url:string;page:number;src:string}>()
  useEffect(()=>{
    const controller=new AbortController();setError('');setPage(0);setDeck(undefined)
    if(!url?.startsWith('blob:')){setError('演示文稿暂不可预览，请下载原文件查看。');return}
    void (async()=>{
      const [{loadPresentation,getSlides},response]=await Promise.all([import('@office-kit/pptx'),fetch(url,{signal:controller.signal})])
      if(!response.ok)throw new Error('read_failed')
      const presentation=await loadPresentation(await response.arrayBuffer())
      const slides=getSlides(presentation)
      if(!slides.length)throw new Error('empty_deck')
      if(!controller.signal.aborted)setDeck({url,presentation,slides})
    })().catch(()=>{if(!controller.signal.aborted)setError('演示文稿预览失败，可下载原文件查看。')})
    return()=>controller.abort()
  },[url])
  useEffect(()=>{
    if(!deck||deck.url!==url)return
    let cancelled=false,objectUrl:string|undefined
    void import('@office-kit/pptx-preview').then(({renderSlideToSvg})=>{
      if(cancelled)return
      const svg=renderSlideToSvg(deck.presentation,deck.slides[page],{textLayout:'svg'})
      objectUrl=URL.createObjectURL(new Blob([svg],{type:'image/svg+xml'}))
      setImage({url:deck.url,page,src:objectUrl})
    }).catch(()=>{if(!cancelled)setError('此页暂不可预览，可下载原文件查看。')})
    return()=>{cancelled=true;if(objectUrl)URL.revokeObjectURL(objectUrl)}
  },[deck,page,url])
  if(error)return <p role="alert">{error}</p>
  const current=deck?.url===url?deck:undefined
  return <section className="pptx-preview" aria-label={`演示文稿预览：${name}`}>
    {current?<><nav aria-label="幻灯片翻页"><button disabled={page===0} onClick={()=>setPage(value=>value-1)}>上一页</button><span>{page+1} / {current.slides.length}</span><button disabled={page===current.slides.length-1} onClick={()=>setPage(value=>value+1)}>下一页</button></nav>
      {image&&image.url===url&&image.page===page?<img src={image.src} alt={`${name} · 第 ${page+1} 页`}/>:<p role="status">正在绘制幻灯片…</p>}</>:<p role="status">正在读取演示文稿…</p>}
  </section>
}
