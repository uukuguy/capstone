import { describe, expect, it } from 'vitest'
import { layoutNetwork, usesModelCoordinates } from './networkLayout'
import type { LegacyNetworkView } from './types'
import { sampleDiagramView, sampleView } from './networkFixture'

describe('network layout', () => {
  it('places all buses deterministically within a bounded schematic canvas', () => {
    const first = layoutNetwork(sampleView)
    expect(layoutNetwork(sampleView)).toEqual(first)
    expect(first).toHaveLength(3)
    expect(first.every((bus) => Number.isFinite(bus.x) && Number.isFinite(bus.y))).toBe(true)
    expect(first.every((bus) => bus.x > 20 && bus.x < 980 && bus.y > 20 && bus.y < 580)).toBe(true)
    expect(new Set(first.map((bus) => `${Math.round(bus.x)},${Math.round(bus.y)}`)).size).toBe(3)
  })

  it('preserves relative positions from authority coordinates without claiming geographic accuracy', () => {
    const geographic: LegacyNetworkView = {
      ...sampleView, coordinate_status: 'provided-unverified',
      buses: [
        { id: 'west', label: 'West', x: 10, y: 20 },
        { id: 'east', label: 'East', x: 20, y: 20 },
        { id: 'north', label: 'North', x: 15, y: 30 },
      ], branches: [], focus_ids: [],
    }
    const positioned = layoutNetwork(geographic)
    expect(positioned.find((bus) => bus.id === 'west')!.x)
      .toBeLessThan(positioned.find((bus) => bus.id === 'east')!.x)
    expect(positioned.find((bus) => bus.id === 'north')!.y)
      .toBeLessThan(positioned.find((bus) => bus.id === 'west')!.y)
  })

  it('uses a labelled schematic when provided positions would collapse a large preview', () => {
    const crowded: LegacyNetworkView = {
      ...sampleView, coordinate_status: 'provided-unverified',
      buses: [...Array.from({ length: 49 }, (_, index) => ({
        id: String(index), label: String(index), x: index / 100, y: index / 100,
      })), { id: 'outlier', label: 'Outlier', x: 100, y: 100 }],
      branches: [], focus_ids: [], next_focus_ids: [],
    }
    expect(usesModelCoordinates(crowded)).toBe(false)
    const positioned = layoutNetwork(crowded)
    const close = positioned.filter((bus) => Math.hypot(bus.x - positioned[0].x,
      bus.y - positioned[0].y) < 40)
    expect(close.length).toBeLessThan(10)
  })

  it('keeps authority geographic coordinates for complete diagrams', () => {
    const positioned = layoutNetwork(sampleDiagramView.diagram)
    expect(positioned).toHaveLength(sampleDiagramView.diagram.buses.length)
    expect(usesModelCoordinates(sampleDiagramView.diagram)).toBe(true)
    expect(positioned[0].x).toBeLessThan(positioned[1].x)
    expect(positioned[0].y).toBeLessThan(positioned[1].y)
  })

  it('keeps all 585 geographic buses even at dense overview scale', () => {
    const buses = Array.from({ length: 585 }, (_, index) => ({
      id: `bus-${index}`, label: `Bus ${index}`, x: 6 + index % 39 * 0.1,
      y: 48 + Math.floor(index / 39) * 0.1, vn_kv: 220,
    }))
    const diagram = { ...sampleDiagramView.diagram, buses, branches: [] }
    const positioned = layoutNetwork(diagram)
    expect(positioned).toHaveLength(585)
    expect(usesModelCoordinates(diagram)).toBe(true)
    expect(positioned[0].x).toBeLessThan(positioned[38].x)
    expect(positioned[0].y).toBeGreaterThan(positioned[546].y)
  })

  it('separates co-located voltage-level buses for transformer stations', () => {
    const diagram = {
      ...sampleDiagramView.diagram,
      buses: [
        { id: 'hv', label: 'HV', x: 10, y: 20, vn_kv: 380 },
        { id: 'lv', label: 'LV', x: 10, y: 20, vn_kv: 110 },
        { id: 'remote', label: 'Remote', x: 20, y: 20, vn_kv: 380 },
      ],
      branches: [{ id: 'transformer:1', kind: 'transformer' as const,
        label: 'Transformer 1', from_bus: 'hv', to_bus: 'lv' }],
    }
    const positioned = layoutNetwork(diagram)
    const hv = positioned.find((bus) => bus.id === 'hv')!
    const lv = positioned.find((bus) => bus.id === 'lv')!
    expect(hv.x).toBe(lv.x)
    expect(hv.y).not.toBe(lv.y)
    expect((hv.y + lv.y) / 2).toBe(300)
  })

})
