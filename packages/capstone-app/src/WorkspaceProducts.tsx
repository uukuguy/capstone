import {useId,type ReactNode} from 'react'

export type WorkspaceProductView = { id: string; label: string; content: ReactNode; description?: string }

/** Trusted, already-admitted views. This container owns presentation only. */
export default function WorkspaceProducts({ views, selectedId, onSelect, actions }: {
  views: readonly WorkspaceProductView[]; selectedId?: string; onSelect?: (id: string) => void; actions: ReactNode
}) {
  const selected=views.find(view=>view.id===selectedId) || views[0]
  const id=useId()
  return <>
    <header className="workspace-artifactbar">
      <div role="tablist" aria-label="成果视图" className="workspace-product-tabs">
        {views.map(view=><button key={view.id} id={`${id}-workspace-tab-${view.id}`} type="button" role="tab" aria-selected={view.id===selected?.id}
          aria-controls={`${id}-workspace-view-${view.id}`} tabIndex={view.id===selected?.id ? 0 : -1}
          onClick={()=>onSelect?.(view.id)} onKeyDown={event=>{
            const step=event.key==='ArrowRight' ? 1 : event.key==='ArrowLeft' ? -1 : 0
            if(!step)return
            event.preventDefault()
            const next=views[(views.findIndex(item=>item.id===view.id)+step+views.length)%views.length]
            onSelect?.(next.id);Array.from(event.currentTarget.parentElement?.querySelectorAll<HTMLButtonElement>('button')??[]).find(button=>button.id===`${id}-workspace-tab-${next.id}`)?.focus()
          }}>{view.label}</button>)}
      </div>
      <div className="workspace-product-tools">{actions}</div>
    </header>
    <div className="workspace-product-stage">
      {views.map(view=><div key={view.id} id={`${id}-workspace-view-${view.id}`} data-reading-key={`resource:${view.id}`} role="tabpanel" aria-labelledby={`${id}-workspace-tab-${view.id}`}
        hidden={view.id!==selected?.id} className="workspace-product-paper">{view.content}</div>)}
    </div>
    <footer className="workspace-product-footer">{selected?.description || '内容来自当前会话的资源与已保存结果。'}</footer>
  </>
}
