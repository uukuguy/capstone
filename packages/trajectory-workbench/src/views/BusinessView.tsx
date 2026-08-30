import type {
  BindingMetadata,
  BusinessProblem,
  CoreTimelineItem,
  DomainPayloadView,
  JsonValue,
  LifecycleStatus,
  NodeSource,
} from '../api/types';
import { domainPayloadView } from '../api/business';
import { TrajectoryRow, type BusinessTrajectoryRow } from '../components/trajectory/TrajectoryRow';
import { VirtualTrajectory, type PrependAnchor } from '../components/trajectory/VirtualTrajectory';
import type { WorkbenchAction, WorkbenchState } from '../state/workbench';

interface BusinessViewProps {
  problems: BusinessProblem[];
  state: WorkbenchState;
  dispatch: React.Dispatch<WorkbenchAction>;
  hasOlder?: boolean;
  onRequestOlder?: (anchor: PrependAnchor) => void;
  olderState?: 'idle' | 'loading' | 'failed';
  olderError?: string | null;
  onRetryOlder?: () => void;
  /** Framework lifecycle is rendered independently from domain rows. */
  coreTimeline?: CoreTimelineItem[];
  /** Available application bindings; selection is by binding identity only. */
  bindings?: BindingMetadata[];
  selectedBindingId?: string | null;
  onBindingChange?: (bindingId: string) => void;
  /** Domain-owned presentation hints; no semantic interpretation happens here. */
  domainPayload?: DomainPayloadView | null;
}

type BusinessViewItem = ({ type: 'node' } & BusinessTrajectoryRow) | { id: string; source_sequence: number; type: 'problem'; problem: BusinessProblem };

function filteredRows(problems: BusinessProblem[], state: WorkbenchState): BusinessViewItem[] {
  const query = state.search.trim().toLowerCase();
  return problems.flatMap((problem) => [
    { id: `problem:${problem.id}`, source_sequence: problem.source_sequence, type: 'problem' as const, problem },
    ...(state.foldedNodeIds.includes(problem.id) ? [] : problem.nodes
      .filter((node) => !query || [node.title, node.detail, node.kind, node.status, node.source].some((value) => value?.toLowerCase().includes(query)))
      .filter((node) => state.sourceFilter === 'all' || node.source === state.sourceFilter)
      .filter((node) => state.statusFilter === 'all' || node.status === state.statusFilter)
      .filter((node) => !state.timelineRange || (node.source_sequence >= state.timelineRange.startSequence && node.source_sequence <= state.timelineRange.endSequence))
      .map((node) => ({ ...node, type: 'node' as const, problemId: problem.id, problemTitle: problem.title }))),
  ]);
}

function presentationText(binding: BindingMetadata | null, key: string): string | null {
  const value = binding?.presentation?.[key];
  return typeof value === 'string' && value.trim() ? value : null;
}

function inferredBinding(problems: BusinessProblem[]): BindingMetadata | null {
  const problem = problems.find((item) => item.binding_id || item.domain_payload?.binding_id);
  if (!problem) return null;
  const payload = problem.domain_payload;
  const bindingId = problem.binding_id ?? payload?.binding_id;
  const domainId = problem.domain_id ?? payload?.domain_id;
  const authorityId = problem.authority_id ?? payload?.authority_id;
  const schema = problem.schema ?? payload?.schema;
  if (!bindingId || !domainId || !authorityId || !schema) return null;
  return {
    binding_id: bindingId,
    domain_id: domainId,
    domain_version: 'unknown',
    authority_id: authorityId,
    schema,
    ...(payload?.presentation ? { presentation: payload.presentation } : {}),
  };
}

function ReadonlyPayloadValue({ name, value, depth = 1 }: { name: string; value: JsonValue; depth?: number }) {
  if (value === null || typeof value !== 'object') {
    return <div role="treeitem" aria-level={depth} className="domain-payload-leaf"><span>{name}</span><code>{String(value)}</code></div>;
  }
  const entries = Array.isArray(value)
    ? value.map((entry, index) => [`[${index}]`, entry] as const)
    : Object.entries(value);
  return <details role="treeitem" aria-level={depth} className="domain-payload-branch" open>
    <summary>{name}<small>{Array.isArray(value) ? `${entries.length} items` : `${entries.length} keys`}</small></summary>
    <div role="group">
      {entries.length > 0
        ? entries.map(([key, entry]) => <ReadonlyPayloadValue key={key} name={key} value={entry} depth={depth + 1} />)
        : <span className="domain-payload-empty">Empty {Array.isArray(value) ? 'array' : 'object'}</span>}
    </div>
  </details>;
}

function DomainPayloadPanel({ payload }: { payload: DomainPayloadView }) {
  const view = domainPayloadView(payload);
  return <section className="domain-payload" aria-label="Domain payload" aria-readonly="true">
    <header><h2>Domain output</h2><p>{view.domain_id} · {view.schema} · authority {view.authority_id}</p></header>
    <div role="tree" aria-label="Opaque domain payload" className="domain-payload-tree">
      <ReadonlyPayloadValue name="Payload" value={view.payload} />
    </div>
    <p className="domain-payload-note">Validated domain output · interpretation: {view.interpretation}</p>
  </section>;
}

export function BusinessView({
  problems,
  state,
  dispatch,
  hasOlder = false,
  onRequestOlder = () => undefined,
  olderState = 'idle',
  olderError = null,
  onRetryOlder = () => undefined,
  coreTimeline = [],
  bindings = [],
  selectedBindingId = null,
  onBindingChange = () => undefined,
  domainPayload = null,
}: BusinessViewProps) {
  const rows = filteredRows(problems, state);
  const availableBindings = bindings.length > 0 ? bindings : (inferredBinding(problems) ? [inferredBinding(problems)!] : []);
  const selectedBinding = availableBindings.find((binding) => binding.binding_id === selectedBindingId)
    ?? availableBindings[0]
    ?? null;
  const effectiveDomainPayload = domainPayload
    ?? problems.find((problem) => problem.domain_payload)?.domain_payload
    ?? null;
  const businessTitle = presentationText(selectedBinding, 'business_title');
  const sources: NodeSource[] = ['observed', 'derived', 'agent-declared'];
  const statuses: LifecycleStatus[] = ['running', 'completed', 'failed', 'interrupted', 'unavailable'];
  const focusedProblemRowId = state.focusedProblemId ? `problem:${state.focusedProblemId}` : null;
  const focusedProblemHeadingId = state.focusedProblemId ? problemHeadingId(state.focusedProblemId) : null;

  return <section className="business-view" aria-label="Business trajectory view">
    {coreTimeline.length > 0 ? <section className="kernel-core-timeline" aria-label="Kernel core timeline">
      <h2>Kernel lifecycle</h2>
      <ol>{coreTimeline.map((item) => <li key={item.id}><strong>{item.label}</strong><small>{item.status}</small>{item.detail ? <span>{item.detail}</span> : null}</li>)}</ol>
    </section> : null}
    {availableBindings.length > 0 ? <section className="domain-binding" aria-label="Selected domain binding">
      <label>Domain binding<select value={selectedBinding?.binding_id ?? ''} onChange={(event) => onBindingChange(event.target.value)}>
        {availableBindings.map((binding) => <option key={binding.binding_id} value={binding.binding_id}>{binding.binding_id}</option>)}
      </select></label>
      {selectedBinding ? <p>
        <span>{selectedBinding.domain_id}</span> · <span>{selectedBinding.domain_version}</span> · authority <span>{selectedBinding.authority_id}</span> · <span>{selectedBinding.schema}</span>
      </p> : null}
    </section> : null}
    <header className="business-view-header"><div><h1>Business trajectory</h1><p>Chronological problem-solving evidence</p></div>
      <div className="business-controls"><label>Search business trajectory<input aria-label="Search business trajectory" value={state.search} onChange={(event) => dispatch({ type: 'search/changed', search: event.target.value })} placeholder="Search decisions, tools, claims" /></label>
      <label>Source filter<select aria-label="Source filter" value={state.sourceFilter} onChange={(event) => dispatch({ type: 'sourceFilter/changed', source: event.target.value as NodeSource | 'all' })}><option value="all">All sources</option>{sources.map((source) => <option value={source} key={source}>{source}</option>)}</select></label>
      <label>Status filter<select aria-label="Status filter" value={state.statusFilter} onChange={(event) => dispatch({ type: 'statusFilter/changed', status: event.target.value as LifecycleStatus | 'all' })}><option value="all">All states</option>{statuses.map((status) => <option value={status} key={status}>{status}</option>)}</select></label></div>
    </header>
    {businessTitle ? <p className="domain-presentation-title">{businessTitle}</p> : null}
    {effectiveDomainPayload ? <DomainPayloadPanel payload={effectiveDomainPayload} /> : null}
    <div className="business-filter-summary" aria-label="Business trajectory filters">{sources.length + statuses.length} available filters · {rows.length} matching events</div>
    <VirtualTrajectory
      items={rows}
      label="Business trajectory"
      hasOlder={hasOlder}
      onRequestOlder={onRequestOlder}
      olderState={olderState}
      olderError={olderError}
      onRetryOlder={onRetryOlder}
      estimateSize={(item) => item.type === 'problem' ? 52 : 44}
      focusItemId={focusedProblemRowId}
      focusElementId={focusedProblemHeadingId}
      renderRow={(item) => item.type === 'problem'
      ? <div className="problem-group-header" data-testid={`problem-header-${item.problem.id}`}>
        <h2 id={problemHeadingId(item.problem.id)} tabIndex={-1}>{item.problem.title}</h2>
        <button type="button" className="problem-fold" aria-expanded={!state.foldedNodeIds.includes(item.problem.id)} onClick={() => dispatch({ type: 'node/foldToggled', nodeId: item.problem.id })} aria-label={`${state.foldedNodeIds.includes(item.problem.id) ? 'Expand' : 'Fold'} ${item.problem.title}`}>
          <span>{state.foldedNodeIds.includes(item.problem.id) ? '▸' : '▾'}</span><small>{item.problem.status} · {item.problem.node_count ?? item.problem.nodes.length} events</small>
        </button>
      </div>
      : <TrajectoryRow item={item} selected={state.selectedNodeId === item.id} onSelect={() => dispatch({ type: 'node/selected', nodeId: item.id })} />}
    />
  </section>;
}

function problemHeadingId(problemId: string) {
  return `business-problem-heading-${problemId}`;
}
