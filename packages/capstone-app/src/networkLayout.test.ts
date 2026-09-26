import { describe, expect, it } from 'vitest'
import { layoutNetwork, usesModelCoordinates } from './networkLayout'
import type { NetworkView } from './types'
import { sampleView } from './networkFixture'

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
    const geographic: NetworkView = {
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
    const crowded: NetworkView = {
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
})
