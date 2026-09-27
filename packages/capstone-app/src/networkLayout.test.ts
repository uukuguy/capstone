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

  it('can generate a schematic projection from a geographic diagram', () => {
    const positioned = layoutNetwork(sampleDiagramView.diagram, true)
    expect(positioned).toHaveLength(sampleDiagramView.diagram.buses.length)
    expect(positioned.every((bus) => bus.x > 20 && bus.x < 980 && bus.y > 20 && bus.y < 580)).toBe(true)
    expect(positioned[0].x).not.toBe(sampleDiagramView.diagram.buses[0].x)
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

  it('keeps dense authority coordinates when schematic glyphs are requested', () => {
    const buses = Array.from({ length: 585 }, (_, index) => ({
      id: `bus-${index}`, label: `Bus ${index}`, x: 6 + index % 39 * 0.1,
      y: 48 + Math.floor(index / 39) * 0.1, vn_kv: 220,
    }))
    const diagram = { ...sampleDiagramView.diagram, buses, branches: [] }
    const geographic = layoutNetwork(diagram)
    const schematic = layoutNetwork(diagram, true)
    expect(schematic).toEqual(geographic)
  })
})
