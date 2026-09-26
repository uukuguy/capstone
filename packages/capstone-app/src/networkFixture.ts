import type { DiagramNetworkView, LegacyNetworkView } from './types'

export const sampleView: LegacyNetworkView = {
  schema: 'capstone-network-view/1.0', ordinal: 1,
  model: { id: 'ieee39', revision: 'revision:one', source: 'gridctl' },
  coordinate_status: 'schematic-required',
  buses: [
    { id: '0', label: 'Bus 0', x: null, y: null },
    { id: '1', label: 'Bus 1', x: null, y: null },
    { id: '2', label: 'Bus 2', x: null, y: null },
  ],
  branches: [
    { id: 'line:11', kind: 'line', label: 'Line 11', from_bus: '0', to_bus: '1' },
    { id: 'line:12', kind: 'line', label: 'Line 12', from_bus: '1', to_bus: '2' },
  ],
  omitted: { buses: 0, branches: 0 }, focus_ids: ['line:11'], next_focus_ids: [], overlay: null,
}

export const sampleDiagramView: DiagramNetworkView = {
  schema: 'capstone-network-view/2.0', ordinal: 1,
  diagram: {
    schema: 'capstone-network-diagram/1.0',
    model: { id: 'scigrid_de', revision: 'revision:one', source: 'pypsamodelctl' },
    coordinate_system: 'geographic',
    buses: [
      { id: 'DE0', label: 'DE0', x: 7.1, y: 52.1, vn_kv: 380 },
      { id: 'DE1', label: 'DE1', x: 9.1, y: 51.1, vn_kv: 380 },
      { id: 'DE2', label: 'DE2', x: 11.1, y: 50.1, vn_kv: 220 },
    ],
    branches: [
      { id: 'line:1', kind: 'line', label: 'Line 1', from_bus: 'DE0', to_bus: 'DE1' },
      { id: 'transformer:2', kind: 'transformer', label: 'Transformer 2', from_bus: 'DE1', to_bus: 'DE2' },
    ],
    fingerprint: `topology:sha256:${'a'.repeat(64)}`,
    ref: `diagram:sha256:${'b'.repeat(64)}`,
  },
  layer: {
    schema: 'capstone-network-layer/1.0', ordinal: 1,
    diagram_ref: `diagram:sha256:${'b'.repeat(64)}`, model_revision: 'revision:one',
    focus_ids: ['line:1'], next_focus_ids: [], overlay: null,
  },
}
