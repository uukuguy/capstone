import { NetworkView } from './NetworkView'
import type { ResultProjection, ThreadSnapshot } from './threadProtocol'
import type { ThreadCatalogModel } from './threadCatalog'
import type { DiagramNetworkView, NetworkDiagram } from './types'
import type { ThreadGridPage, ThreadModelWorkingPage } from './threadProjectionStore'

function modelLabel(modelId: string | undefined, family?: string): string {
  const known = { ieee39: 'IEEE-39', pypsa39: 'PyPSA-39', 'regional-six-bus': 'Regional Six Bus' }
  return known[modelId as keyof typeof known] || (family === 'pypsa' && modelId ? `PyPSA · ${modelId}` : modelId) || '当前模型'
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
  gridPages: readonly ThreadGridPage[]
  workingPages?: readonly ThreadModelWorkingPage[]
  cameraStorageKey?: string
  isHistorical: boolean
  projectionEventSeq: number
  previewDiagram: NetworkDiagram | null
  networkView?: DiagramNetworkView | null
  networkTaskId?: string
  networkFailureCode?: string
  instructionLabel?: string
  viewingInstruction?: boolean
  onLatestInstruction?: () => void
  elementReference?: { model_id: string; model_revision: string; element_kind: string; element_id: string }
  modelOptions: ThreadCatalogModel[]
  onSelectPage: (pageId: string) => void
  onOpenHistoricalModel?: (modelId: string, revision: string) => void
  modelBusy?: boolean
  resultProjection?: ResultProjection
  focusedElementId?: string
  feedback?: string | null
}

function projectionNetworkView(diagram: NetworkDiagram, projection: ResultProjection | undefined, focusedElementId: string | undefined) {
  if (!projection || projection.modelId !== diagram.model.id || projection.modelRevision !== diagram.model.revision) return null
  const overlay = projection?.overlay
  const supportedOverlay = overlay?.metric === 'loading_percent' || overlay?.metric === 'voltage_pu'
    ? { metric: overlay.metric as 'loading_percent' | 'voltage_pu', unit: overlay.unit as '%' | 'p.u.', source_ref: overlay.sourceRef, values: overlay.values
      .map((value) => ({ id: value.elementId, value: value.value })) }
    : null
  const diagramIds = new Set([...diagram.branches.map((branch) => branch.id), ...diagram.buses.map((bus) => bus.id)])
  if ((supportedOverlay && supportedOverlay.values.some((value) => !diagramIds.has(value.id))) || (focusedElementId && !diagramIds.has(focusedElementId))) return null
  return projection ? {
    schema: 'capstone-network-view/2.0' as const, ordinal: 1, diagram,
    layer: {
      schema: 'capstone-network-layer/1.0' as const, ordinal: 1,
      diagram_ref: diagram.ref, model_revision: diagram.model.revision,
      focus_ids: focusedElementId && (diagram.branches.some((branch) => branch.id === focusedElementId) || diagram.buses.some((bus) => bus.id === focusedElementId)) ? [focusedElementId] : [],
      next_focus_ids: [], overlay: supportedOverlay && supportedOverlay.values.length > 0 ? supportedOverlay : null,
    },
  } : null
}

export function projectActiveNetworkView(view: DiagramNetworkView, projection: ResultProjection | undefined,
                                         focusedElementId: string | undefined): DiagramNetworkView {
  const diagramIds = new Set([...view.diagram.branches.map((branch) => branch.id), ...view.diagram.buses.map((bus) => bus.id)])
  const focusIds = focusedElementId && diagramIds.has(focusedElementId)
    ? [focusedElementId] : view.layer.focus_ids.filter((id) => diagramIds.has(id))
  const overlay = projection?.modelId === view.diagram.model.id && projection.modelRevision === view.diagram.model.revision
    ? projection.overlay : undefined
  const supportedOverlay = overlay && (overlay.metric === 'loading_percent' || overlay.metric === 'voltage_pu') &&
    overlay.values.every((value) => diagramIds.has(value.elementId))
    ? { metric: overlay.metric as 'loading_percent' | 'voltage_pu', unit: overlay.unit as '%' | 'p.u.', source_ref: overlay.sourceRef,
        values: overlay.values.map((value) => ({ id: value.elementId, value: value.value })) }
    : undefined
  const displayedOverlay = focusedElementId
    ? supportedOverlay || view.layer.overlay
    : view.layer.overlay || (view.layer.focus_ids.length === 0 ? supportedOverlay : undefined)
  return { ...view, layer: { ...view.layer, focus_ids: focusIds, overlay: displayedOverlay || null } }
}

/** Thread's copied center-column model surface. Legacy RunPanel remains untouched. */
export default function ThreadModelPane({ snapshot, viewedPage, activePage, gridPages, workingPages, cameraStorageKey, isHistorical,
  projectionEventSeq, previewDiagram,
  networkView, networkTaskId, networkFailureCode, instructionLabel, viewingInstruction, onLatestInstruction, elementReference, modelOptions, onSelectPage, onOpenHistoricalModel, modelBusy, resultProjection, focusedElementId, feedback }: ThreadModelPaneProps) {
  const pages = Array.from(new Set([...gridPages.map((page) => page.pageId), activePage, viewedPage]))
  const historicalPage = isHistorical ? gridPages.find((page) => page.pageId === viewedPage) : undefined
  const viewedContext = isHistorical ? historicalPage?.context : snapshot.activeModelContext
  const pageView = isHistorical ? historicalPage?.networkView : networkView
  const dynamicModelView = viewedContext && pageView?.diagram.model.id === viewedContext.modelId &&
    pageView.diagram.model.revision === viewedContext.modelRevision ? pageView : null
  const modelDiagram = dynamicModelView?.diagram || (!isHistorical && previewDiagram?.model.id === snapshot.activeModelContext.modelId && previewDiagram.model.revision === snapshot.activeModelContext.modelRevision ? previewDiagram : null)
  const activeModelName = modelOptions.find((model) => model.modelId === snapshot.activeModelContext.modelId)?.displayName
    || modelLabel(snapshot.activeModelContext.modelId, snapshot.activeModelContext.implementationFamily)
  const pageModelName = (pageId: string) => {
    const context = gridPages.find((page) => page.pageId === pageId)?.context
    return context ? modelOptions.find((model) => model.modelId === context.modelId)?.displayName || modelLabel(context.modelId, context.implementationFamily) : pageId
  }
  const viewedModelName = isHistorical ? pageModelName(viewedPage) : activeModelName
  const displayedView = dynamicModelView
    ? projectActiveNetworkView(dynamicModelView, !isHistorical || viewingInstruction ? resultProjection : undefined,
        isHistorical ? undefined : focusedElementId)
    : modelDiagram ? projectionNetworkView(modelDiagram, resultProjection, focusedElementId) : null
  const viewKey = `${viewedContext?.implementationFamily}:${viewedContext?.modelId}:${viewedContext?.modelRevision}:${viewedContext?.id}:${networkTaskId || 'base'}`
  const historicalIsOpen = workingPages?.some(page => page.model.modelId === viewedContext?.modelId &&
    page.model.modelRevision === viewedContext?.modelRevision && page.model.implementationFamily === viewedContext?.implementationFamily)
  return <section className="thread-model-pane" aria-label="电网模型区">
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
      <div className="thread-intro-copy">
        <p>CAPSTONE 为电网科学AI提供应用底座：把 pandapower、PyPSA 等科学计算工具封装为统一的领域能力，由智能体组织任务、权威系统完成计算。每一步的结果与证据随运行留存，形成可复用、可核查的分析过程。智能体对话围绕当前电网模型连续开展工作：用自然语言打开模型、提出问题和组织分析，通过回答下方的操作查看对应电网图、运行过程和证据。</p>
      </div>
    </section>
      {!workingPages && pages.length > 1 && <details className="thread-model-history"><summary>模型历史 · {pages.length - 1}</summary>
        <div className="thread-page-tabs" aria-label="电网模型分页">
          {pages.map((pageId) => <PageButton key={pageId} active={viewedPage === pageId} historical={pageId !== activePage}
            label={pageId === activePage ? `${activeModelName} · 当前模型` : `${pageModelName(pageId)} · 事件历史`} onClick={() => onSelectPage(pageId)} />)}
        </div>
      </details>}
    <div className="thread-network-card">
      {viewingInstruction && <div className="thread-history-bar" role="status"><span>正在查看此回答对应的电网图</span><button type="button" onClick={onLatestInstruction}>回到最新指令图</button></div>}
      {isHistorical && !modelDiagram ? <div className="network-empty" role="status"><strong>历史电网视图暂不可用</strong><p>该历史模型上下文没有可验证的电网投影。</p></div> :
        <NetworkView key={viewKey} cameraStorageKey={cameraStorageKey} cameraViewKey={viewKey} compact view={displayedView} previewDiagram={modelDiagram} modelName={viewedModelName} focusKey={`${viewedContext?.id}:${networkTaskId || ''}:${focusedElementId || ''}`}
          instructionLabel={instructionLabel}
          failureCode={networkFailureCode}
          unavailable={!modelDiagram} previewUnavailable={!modelDiagram} historyFocusIds={[]} />}
    </div>
    {feedback && <div className="thread-model-feedback" role="status">{feedback}</div>}
    <details className="thread-view-details"><summary>电网视图详情{isHistorical ? ' · 历史只读' : ''}</summary>
      <div className="thread-grid-meta"><div><span>MODEL CONTEXT</span><strong>{viewedContext?.id || '不可用'}</strong></div><div><span>SELECTION</span><strong>{viewedContext?.selectionRevision || '不可用'}</strong></div><div><span>EVENT CURSOR</span><strong>#{projectionEventSeq}</strong></div></div>
      <p>{viewedContext?.implementationFamily} · revision {viewedContext?.modelRevision}</p>
    </details>
    {isHistorical && <div className="thread-history-bar"><span>历史页 · 只读视图</span>{viewedContext && onOpenHistoricalModel && <button type="button" disabled={modelBusy} onClick={() => onOpenHistoricalModel(viewedContext.modelId, viewedContext.modelRevision)}>{historicalIsOpen ? '设为当前模型' : '重新打开'}</button>}<button type="button" onClick={() => onSelectPage(activePage)}>返回当前模型</button></div>}
    {elementReference && !isHistorical && <div className="thread-element-reference"><span>ELEMENT REFERENCE</span><strong>{elementReference.element_kind} / {elementReference.element_id}</strong><small>{elementReference.model_id} · revision {elementReference.model_revision}</small></div>}
  </section>
}
