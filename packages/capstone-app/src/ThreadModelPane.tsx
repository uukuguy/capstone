import { NetworkView } from './NetworkView'
import type { ThreadSnapshot } from './threadProtocol'
import type { NetworkDiagram } from './types'

function modelLabel(modelId: string | undefined): string {
  return { ieee39: 'IEEE-39', pypsa39: 'PyPSA-39' }[modelId || ''] || modelId || '当前模型'
}

function PageButton({ active, historical, label, onClick }: { active: boolean; historical: boolean; label: string; onClick: () => void }) {
  return <button type="button" className={`thread-page-button${active ? ' is-active' : ''}${historical ? ' is-history' : ''}`} onClick={onClick}>
    <span className="thread-page-index">{active ? '●' : '○'}</span><span>{label}</span>{historical && <small>历史</small>}
  </button>
}

export type ThreadModelPaneProps = {
  snapshot: ThreadSnapshot
  viewedPage: string
  activePage: string
  isHistorical: boolean
  projectionEventSeq: number
  modelTarget: string
  contextChangePending: boolean
  controlsDisabled: boolean
  previewDiagram: NetworkDiagram | null
  elementReference?: { model_id: string; model_revision: string; element_kind: string; element_id: string }
  onModelTargetChange: (value: string) => void
  onSwitchModel: () => void
  onSelectPage: (pageId: string) => void
}

/** Thread's copied center-column model surface. Legacy RunPanel remains untouched. */
export default function ThreadModelPane({ snapshot, viewedPage, activePage, isHistorical,
  projectionEventSeq, modelTarget, contextChangePending, controlsDisabled, previewDiagram,
  elementReference, onModelTargetChange, onSwitchModel, onSelectPage }: ThreadModelPaneProps) {
  const pages = isHistorical ? Array.from(new Set([activePage, viewedPage])) : [activePage]
  const modelDiagram = snapshot.activeModelContext.modelId === 'ieee39' ? previewDiagram : null
  return <section className="thread-model-pane" aria-label="电网模型区">
    <div className="thread-model-heading"><div><span className="eyebrow">MODEL / OVERVIEW</span><h2>电网模型</h2></div><span className="thread-context-state">{isHistorical ? '历史查看' : '当前'}</span></div>
    <section className="thread-model-intro" aria-label="CAPSTONE 框架介绍">
      <div className="capstone-intro-art notranslate" translate="no">
        <img src="/capstone-science-hero.png" alt="工业专业框架与 AI 智能体应用的连接示意" />
        <div className="capstone-intro-overlay">
          <div className="capstone-intro-main">
            <span className="capstone-intro-kicker">电网科学AI <span> / SCIENTIFIC AI FOR THE GRID</span></span>
            <strong>从专业仿真<br />到智能推演</strong>
            <div className="capstone-intro-frameworks"><span>pandapower</span><span>PyPSA</span></div>
            <div className="capstone-intro-disciplines" aria-label="电网科学AI模型方向">
              <span><b>神经算子</b>DeepONet · FNO</span>
              <span><b>动力学模型</b>Neural-DAE · Koopman</span>
              <span><b>物理图网络</b>GraphGPS · PI-GNN</span>
            </div>
          </div>
          <span className="capstone-intro-principles">CAPABILITY / EVIDENCE / CONTROL</span>
        </div>
      </div>
      <p>当前 Thread 围绕一个电网模型工作。模型由已注册 authority 提供，工具调用和结果证据随 Run 保留。</p>
    </section>
    <div className="thread-model-card"><div><strong>{modelLabel(snapshot.activeModelContext.modelId)}</strong><span>{snapshot.activeModelContext.implementationFamily} · revision {snapshot.activeModelContext.modelRevision}</span></div><span className="thread-model-badge">{isHistorical ? 'READ ONLY' : 'ACTIVE'}</span></div>
    <div className="thread-model-controls" aria-label="模型上下文控制">
      <label>切换模型<select aria-label="目标电网模型" value={modelTarget} onChange={(event) => onModelTargetChange(event.target.value)} disabled={controlsDisabled}>
        <option value="ieee39">IEEE-39 · pandapower</option><option value="pypsa39">PyPSA-39 · PyPSA</option>
      </select></label>
      <button type="button" className="thread-control-button" disabled={controlsDisabled || modelTarget === snapshot.activeModelContext.modelId} onClick={onSwitchModel}>切换模型</button>
      {contextChangePending && <small>切换将在下一 Turn 激活</small>}
    </div>
    <div className="thread-page-tabs" aria-label="电网模型分页">
      {pages.map((pageId) => <PageButton key={pageId} active={viewedPage === pageId} historical={pageId !== activePage}
        label={pageId === activePage ? `${modelLabel(snapshot.activeModelContext.modelId)} · 当前模型` : `${pageId} · 事件历史`} onClick={() => onSelectPage(pageId)} />)}
    </div>
    <div className="thread-network-card">
      <NetworkView view={null} previewDiagram={modelDiagram} modelName={modelLabel(snapshot.activeModelContext.modelId)} focusKey={viewedPage}
        unavailable={!modelDiagram} previewUnavailable={!modelDiagram} historyFocusIds={[]} />
    </div>
    <div className="thread-grid-meta"><div><span>MODEL CONTEXT</span><strong>{snapshot.activeModelContext.id}</strong></div><div><span>SELECTION</span><strong>{snapshot.activeModelContext.selectionRevision}</strong></div><div><span>EVENT CURSOR</span><strong>#{projectionEventSeq}</strong></div></div>
    {isHistorical && <div className="thread-history-bar"><span>历史页 · 只读视图</span><button type="button" onClick={() => onSelectPage(activePage)}>返回当前模型</button></div>}
    {elementReference && <div className="thread-element-reference"><span>ELEMENT REFERENCE</span><strong>{elementReference.element_kind} / {elementReference.element_id}</strong><small>{elementReference.model_id} · revision {elementReference.model_revision}</small></div>}
  </section>
}
