import {useEffect,useState} from 'react'
import {Package,X} from 'lucide-react'
import './ManagedResourcesPanel.css'

type Resource={resource_id:string;version:string;kind:string;installed:boolean;enabled:boolean;available:boolean;diagnostics:string[];source:{locator:string;revision:string};installation?:{subdirectory?:string;runtime?:{entrypoint?:string}};runtime?:{entrypoint?:string};preinstall?:{drafts:string[];published:string[]}}
type Catalog={resources:Resource[];allowed_actions:string[];revision:string}
type Transport={listManagedResources:()=>Promise<unknown>;manageResource:(operation:string,document:Record<string,unknown>)=>Promise<unknown>}
export default function ManagedResourcesPanel({transport}:{transport:Transport}){
  const [open,setOpen]=useState(false),[catalog,setCatalog]=useState<Catalog>(),[error,setError]=useState(''),[busy,setBusy]=useState(false)
  const [kind,setKind]=useState('skill'),[source,setSource]=useState(''),[revision,setRevision]=useState(''),[name,setName]=useState(''),[directory,setDirectory]=useState(''),[entry,setEntry]=useState('')
  const [receipt,setReceipt]=useState<Record<string,unknown>>()
  const [loaded,setLoaded]=useState(false)
  const [updating,setUpdating]=useState<Resource>()
  const allowed=(action:string)=>catalog?.allowed_actions.includes(`resources.${action}`)===true
  async function refresh(){try{setCatalog(await transport.listManagedResources() as Catalog)}finally{setLoaded(true)}}
  useEffect(()=>{if(open)void refresh().catch(e=>setError(e instanceof Error?e.message:'资源列表读取失败'))},[open,transport])
  async function perform(operation:string,document:Record<string,unknown>){
    if(busy)return
    setBusy(true);setError('');setReceipt(undefined)
    try{const result=await transport.manageResource(operation,document) as Record<string,unknown>;setReceipt(result);await refresh();if(operation==='install'&&result.status==='succeeded')setUpdating(undefined)}
    catch(e){setError(e instanceof Error?e.message:'资源操作失败')}
    finally{setBusy(false)}
  }
  return <><button type="button" className="thread-settings-item" onClick={()=>setOpen(true)}><Package aria-hidden="true"/>Skills / MCP 管理</button>
    {open&&<section className="managed-resources-panel" role="dialog" aria-modal="true" aria-label="Skills 与 MCP 管理">
      <header><div><h2>Skills 与 MCP</h2><p>安装后持久保存，在当前工作空间使用。</p></div><button type="button" aria-label="关闭资源管理" onClick={()=>setOpen(false)}><X aria-hidden="true"/></button></header>
      {error&&<p role="alert">{error}</p>}
      {!catalog?<p>{loaded?'资源尚未读取。':'正在读取资源…'}{loaded&&<button type="button" onClick={()=>{setError('');void refresh().catch(e=>setError(e instanceof Error?e.message:'资源列表读取失败'))}}>重试读取</button>}</p>:<>
        {!allowed('install')&&<p>当前未开放安装权限；其他操作以各自权限为准。</p>}
        {catalog.resources.filter(r=>r.installed).length===0&&<p>尚未安装资源。</p>}
        <div className="managed-resource-list">{catalog.resources.filter(r=>r.installed).map(r=><article key={r.resource_id}>
          <strong>{r.resource_id}</strong><span>{r.kind} · {r.enabled?'已启用':'已停用'} · {r.available?'安装校验通过':'不可用'}</span>
          <small>{r.source.locator} · {r.source.revision}</small><small>版本 {r.version}</small>
          {r.preinstall?.drafts.length!==undefined&&r.preinstall.drafts.length>0&&<small>已加入预装草稿：{r.preinstall.drafts.join('、')}</small>}
          {r.preinstall?.published.length!==undefined&&r.preinstall.published.length>0&&<small>已发布预装清单：{r.preinstall.published.join('、')}（不代表已部署）</small>}
          {r.diagnostics?.length>0&&<p>{r.diagnostics.join('；')}</p>}
          <div>{allowed('update')&&<button disabled={busy} onClick={()=>{setUpdating(r);setName(r.resource_id);setKind(r.kind);setSource(r.source.locator);setRevision('');setDirectory(r.installation?.subdirectory||'');setEntry(r.installation?.runtime?.entrypoint||r.runtime?.entrypoint||'')}}>更新</button>}{allowed(r.enabled?'disable':'enable')&&<button disabled={busy} onClick={()=>void perform('state',{resource_id:r.resource_id,expected_version:r.version,enabled:!r.enabled})}>{r.enabled?'停用':'启用'}</button>}
          {allowed('uninstall')&&<button disabled={busy} onClick={()=>void perform('uninstall',{resource_id:r.resource_id,expected_version:r.version})}>卸载</button>}
          {allowed('preinstall.manage')&&<button disabled={busy} onClick={()=>void perform('preinstall_draft',{profile:'default',resource_id:r.resource_id,include:true})}>加入预安装草稿</button>}</div>
        </article>)}</div>
        {(allowed('install')||Boolean(updating&&allowed('update')))&&<form onSubmit={e=>{e.preventDefault();void perform('install',{request_id:crypto.randomUUID(),resource_id:name,...(updating?{expected_version:updating.version}:{}),request:{kind,source:{locator:source,revision:revision||(kind==='mcp_remote'?'discover':'')},...(kind==='mcp_remote'?{}:{subdirectory:directory,runtime:{entrypoint:entry}})}})}}>
          <h3>{updating?`更新 ${updating.resource_id}`:'安装资源'}</h3>{updating&&<button type="button" onClick={()=>setUpdating(undefined)}>取消更新</button>}
          <label>类型<select value={kind} onChange={e=>setKind(e.target.value)}><option value="skill">Skill</option><option value="mcp_remote">远程 MCP</option><option value="mcp_local">本机 MCP</option></select></label>
          <label>资源标识<input required disabled={Boolean(updating)} value={name} onChange={e=>setName(e.target.value)} placeholder="例如 research-tools"/></label>
          <label>{kind==='mcp_remote'?'MCP 服务地址':'Git 仓库地址'}<input required type="url" value={source} onChange={e=>setSource(e.target.value)} placeholder="https://…"/></label>
          <label>{kind==='mcp_remote'?'契约版本（留空时发现并固定）':'Git 完整提交哈希'}<input required={kind!=='mcp_remote'} value={revision} onChange={e=>setRevision(e.target.value)}/></label>
          {kind!=='mcp_remote'&&<label>仓库内目录<input value={directory} onChange={e=>setDirectory(e.target.value)} placeholder="留空表示仓库根目录"/></label>}
          {kind==='mcp_local'&&<label>启动文件<input required value={entry} onChange={e=>setEntry(e.target.value)} placeholder="例如 server.mjs"/></label>}
          <p>获取远程资源受当前网络开关约束。安装失败保留原版本。</p><button disabled={busy} type="submit">{busy?'正在处理…':updating?'更新并校验':'安装并校验'}</button>
        </form>}
        {allowed('preinstall.manage')&&<footer><button disabled={busy} onClick={()=>void perform('preinstall_export',{profile:'default'})}>查看预安装草稿</button><button disabled={busy} onClick={()=>void perform('preinstall_publish',{profile:'default'})}>发布预安装清单</button><small>发布清单不代表已更新其他服务器。</small></footer>}
      </>}
      {receipt&&<section aria-label="资源操作结果"><h3>操作结果</h3>{receipt.status==='failed'&&<p role="alert">安装未完成：{String(receipt.diagnostic||'原因见回执')}</p>}{receipt.status==='pending'&&<p>操作尚未确认完成；请保留请求编号，查询原操作，不要重新安装。</p>}{typeof receipt.request_id==='string'&&<p>请求编号：{receipt.request_id}</p>}<details><summary>查看完整回执</summary><pre>{JSON.stringify(receipt,null,2)}</pre></details></section>}
    </section>}
  </>
}
