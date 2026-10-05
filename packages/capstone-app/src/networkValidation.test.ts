import { describe, expect, it } from 'vitest'
import { parseNetworkDiagram, parseNetworkView } from './networkValidation'
import { sampleDiagramView, sampleView } from './networkFixture'

describe('network projection at the browser boundary', () => {
  it('accepts a complete large model and still rejects over-limit or foreign endpoints', () => {
    const buses = Array.from({ length: 9241 }, (_, i) => ({
      id: String(i), label: `Bus ${i}`, x: null, y: null, vn_kv: 220,
    }))
    const diagram = { ...sampleDiagramView.diagram, coordinate_system: 'schematic', buses, branches: [{
      id: 'line:1', kind: 'line', label: 'Line 1', from_bus: '0', to_bus: '9240',
    }] }
    expect(parseNetworkDiagram(diagram)?.buses).toHaveLength(9241)
    expect(parseNetworkDiagram({ ...diagram, buses: [...buses, ...buses] })).toBeNull()
    expect(parseNetworkDiagram({ ...diagram, branches: [{ ...diagram.branches[0], to_bus: 'foreign' }] })).toBeNull()
  })
  it('accepts only a bounded standalone case diagram', () => {
    expect(parseNetworkDiagram(sampleDiagramView.diagram)).toEqual(sampleDiagramView.diagram)
    expect(parseNetworkDiagram({ ...sampleDiagramView.diagram, branches: [
      { ...sampleDiagramView.diagram.branches[0], to_bus: 'foreign' },
    ] })).toBeNull()
  })
  it('accepts a bounded view of the committed step', () => {
    expect(parseNetworkView(sampleView, 1, [])).toEqual(sampleView)
  })

  it('accepts the complete authority diagram and its current-turn layer', () => {
    expect(parseNetworkView(sampleDiagramView, 1, [])).toEqual(sampleDiagramView)
    const foreign = { ...sampleDiagramView, layer: { ...sampleDiagramView.layer,
      diagram_ref: `diagram:sha256:${'c'.repeat(64)}` } }
    expect(parseNetworkView(foreign, 1, [])).toBeNull()
  })

  it('rejects a foreign endpoint and nonfinite coordinates', () => {
    expect(parseNetworkView({ ...sampleView, branches: [{ ...sampleView.branches[0], to_bus: 'foreign' }] }, 1, [])).toBeNull()
    expect(parseNetworkView({ ...sampleView, buses: [{ ...sampleView.buses[0], x: Infinity }] }, 1, [])).toBeNull()
  })

  it('rejects an overlay without an admitted current-turn result', () => {
    const view = { ...sampleView, overlay: {
      metric: 'loading_percent', unit: '%', source_ref: 'result:foreign',
      values: [{ id: 'line:11', value: 80 }],
    } }
    expect(parseNetworkView(view, 1, ['result:current'])).toBeNull()
    expect(parseNetworkView({ ...view, overlay: { ...view.overlay, source_ref: 'result:current' } },
      1, ['result:current'])).not.toBeNull()
    expect(parseNetworkView({ ...view, branches: [{ ...sampleView.branches[0], kind: 'link' }],
      overlay: { ...view.overlay, source_ref: 'result:current' } }, 1, ['result:current'])).toBeNull()
  })
})
