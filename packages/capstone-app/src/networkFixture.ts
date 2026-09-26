import type { NetworkView } from './types'

export const sampleView: NetworkView = {
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
