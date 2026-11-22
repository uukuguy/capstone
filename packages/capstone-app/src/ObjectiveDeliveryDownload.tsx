type Criterion = {label:string; status:string; explanation?:string; references?:string[]}
type Delivery = {title:string; objective:string; revision:number; status:string; summary:string; criteria:Criterion[]}

export function objectiveDeliveryDocument(delivery:Delivery):string {
  const lines = [
    `# ${delivery.title}`, '',
    `修订 ${delivery.revision} · ${delivery.status}`, '',
    '## 目标', '', delivery.objective, '',
    '## 整体答复', '', delivery.summary,
  ]
  if(delivery.criteria.length){
    lines.push('', '## 完成条件')
    for(const criterion of delivery.criteria){
      lines.push('', `- ${criterion.label} · ${criterion.status}`)
      if(criterion.explanation)lines.push('', criterion.explanation)
      if(criterion.references?.length)lines.push('', '核验依据', ...criterion.references.map(reference=>`- ${reference}`))
    }
  }
  return lines.join('\n')+'\n'
}

export default function ObjectiveDeliveryDownload({delivery,fileName}:{delivery:Delivery;fileName:string}){
  function download(){
    const url=URL.createObjectURL(new Blob([objectiveDeliveryDocument(delivery)],{type:'text/markdown;charset=utf-8'}))
    const link=document.createElement('a')
    link.href=url
    link.download=fileName
    link.click()
    setTimeout(()=>URL.revokeObjectURL(url),1000)
  }
  return <button type="button" className="thread-control-button" onClick={download}>下载整体交付</button>
}
