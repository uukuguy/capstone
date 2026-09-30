import type { NetworkDiagram } from './types'

/**
 * A bounded local preview used while a live Thread is loading its authority
 * diagram. The live route replaces this with the diagram returned by the
 * registered case API; fixture mode still needs a useful topology surface.
 */
export const threadPreviewDiagram: NetworkDiagram = {
  schema: 'capstone-network-diagram/1.0',
  model: { id: 'ieee39', revision: '7', source: 'gridctl' },
  coordinate_system: 'schematic',
  buses: [
    { id: 'B01', label: 'B01', x: 0, y: 0, vn_kv: 345 },
    { id: 'B07', label: 'B07', x: 1, y: 1, vn_kv: 345 },
    { id: 'B12', label: 'B12', x: 2, y: 0.65, vn_kv: 345 },
    { id: 'B19', label: 'B19', x: 3, y: 1.2, vn_kv: 345 },
    { id: 'B24', label: 'B24', x: 4, y: 0.25, vn_kv: 345 },
    { id: 'B31', label: 'B31', x: 3.45, y: -0.85, vn_kv: 345 },
    { id: 'B27', label: 'B27', x: 2.15, y: -0.55, vn_kv: 345 },
    { id: 'B34', label: 'B34', x: 1, y: -1.05, vn_kv: 345 },
  ],
  branches: [
    { id: 'line:B01-B07', kind: 'line', label: 'Line B01-B07', from_bus: 'B01', to_bus: 'B07' },
    { id: 'line:B07-B12', kind: 'line', label: 'Line B07-B12', from_bus: 'B07', to_bus: 'B12' },
    { id: 'line:B12-B19', kind: 'line', label: 'Line B12-B19', from_bus: 'B12', to_bus: 'B19' },
    { id: 'line:B19-B24', kind: 'line', label: 'Line B19-B24', from_bus: 'B19', to_bus: 'B24' },
    { id: 'line:B24-B31', kind: 'line', label: 'Line B24-B31', from_bus: 'B24', to_bus: 'B31' },
    { id: 'line:B31-B27', kind: 'line', label: 'Line B31-B27', from_bus: 'B31', to_bus: 'B27' },
    { id: 'line:B27-B34', kind: 'line', label: 'Line B27-B34', from_bus: 'B27', to_bus: 'B34' },
    { id: 'line:B34-B01', kind: 'line', label: 'Line B34-B01', from_bus: 'B34', to_bus: 'B01' },
    { id: 'line:B01-B27', kind: 'line', label: 'Line B01-B27', from_bus: 'B01', to_bus: 'B27' },
    { id: 'line:B12-B27', kind: 'line', label: 'Line B12-B27', from_bus: 'B12', to_bus: 'B27' },
    { id: 'transformer:B19-B31', kind: 'transformer', label: 'Transformer B19-B31', from_bus: 'B19', to_bus: 'B31' },
  ],
  fingerprint: `topology:sha256:${'c'.repeat(64)}`,
  ref: `diagram:sha256:${'d'.repeat(64)}`,
}
