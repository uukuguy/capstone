import type {ServiceBusCalls} from './serviceBusCalls'
export default function ServiceBusCallDetails({calls}:{calls?:ServiceBusCalls}) {
  if(!calls)return null
  return <section aria-label="服务总线调用记录">
    <p>服务总线 {calls.attempt_count===undefined?'次数未知':`${calls.attempt_count} 次`}{calls.reused?' · 历史复用，不计入本轮':''} · 收到响应 {calls.response_count??'未知'} · 传输错误 {calls.transport_error_count??'未知'} · 总线报错 {calls.bus_declared_error_count??'未知'}</p>
    <p>已返回工具调用范围 · 调用耗时合计 {calls.observed_elapsed_ms==null?'未知':`${calls.observed_elapsed_ms.toFixed(1)} ms`}（含网关等待与网络时间，并发区间可重叠）{calls.history_complete===false?' · 历史记录不完整':''}{calls.details_truncated?' · 仅显示最近 10 条明细，次数使用完整计数':''}</p>
    {calls.details.length>0&&<ul>{calls.details.map((row,index)=><li key={`${row.call_id??index}`}>
      {[row.service,row.method,row.table].filter(Boolean).join(' · ')||'服务调用'} · {row.status??'状态未记录'} · {row.elapsed_ms===undefined?'耗时未知':`${row.elapsed_ms} ms`}
      {row.page_index!==undefined?` · 页 ${row.page_index}`:''}{row.returned_records!==undefined?` · 返回 ${row.returned_records} 条`:''}
      {row.request_id?<small> · 请求 {row.request_id}</small>:null}
    </li>)}</ul>}
  </section>
}
