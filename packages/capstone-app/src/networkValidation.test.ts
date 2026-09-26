import { describe, expect, it } from 'vitest'
import { parseNetworkView } from './networkValidation'
import { sampleDiagramView, sampleView } from './networkFixture'

describe('network projection at the browser boundary', () => {
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
