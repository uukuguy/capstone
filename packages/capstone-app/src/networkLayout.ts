import type { LegacyNetworkView, NetworkDiagram } from './types'

type Geometry = LegacyNetworkView | NetworkDiagram
export type PositionedBus = Geometry['buses'][number] & { x: number; y: number }

const WIDTH = 1000
const HEIGHT = 600

function providedLayout(view: Geometry): PositionedBus[] | null {
  const buses = view.buses
  const coordinated = (view.schema === 'capstone-network-diagram/1.0' ||
    view.coordinate_status === 'provided-unverified') &&
    buses.every((bus) => bus.x !== null && bus.y !== null &&
      Number.isFinite(bus.x) && Number.isFinite(bus.y))
  if (!coordinated) return null
  const xValues = buses.map((bus) => bus.x as number)
  const yValues = buses.map((bus) => bus.y as number)
  const minX = Math.min(...xValues), maxX = Math.max(...xValues)
  const minY = Math.min(...yValues), maxY = Math.max(...yValues)
  if (minX === maxX && minY === maxY) return null
  const scale = Math.min(800 / Math.max(1, maxX - minX),
    440 / Math.max(1, maxY - minY))
  const positioned = buses.map((bus) => ({ ...bus,
    x: WIDTH / 2 + ((bus.x as number) - (minX + maxX) / 2) * scale,
    y: HEIGHT / 2 - ((bus.y as number) - (minY + maxY) / 2) * scale,
  }))
  // PyPSA represents transformer voltage levels as co-located buses. Expand
  // those station points slightly so the transformer can sit between the
  // two electrical busbars without changing the surrounding geography.
  const coincident = new Map<string, number[]>()
  positioned.forEach((bus, index) => {
    const key = `${bus.x.toFixed(6)}:${bus.y.toFixed(6)}`
    const group = coincident.get(key) || []
    group.push(index)
    coincident.set(key, group)
  })
  for (const group of coincident.values()) {
    if (group.length < 2) continue
    const gap = Math.min(14, 70 / (group.length - 1))
    const center = (group.length - 1) / 2
    for (const [rank, index] of group.entries()) {
      positioned[index].y += (rank - center) * gap
    }
  }
  if (view.schema === 'capstone-network-view/1.0' && buses.length > 12) {
    const crowded = positioned.filter((bus, index) => positioned.some((other, otherIndex) =>
      index !== otherIndex && Math.hypot(bus.x - other.x, bus.y - other.y) < 20)).length
    if (crowded > buses.length / 4) return null
  }
  return positioned
}

export function usesModelCoordinates(view: Geometry): boolean {
  return providedLayout(view) !== null
}

export function layoutNetwork(view: Geometry): PositionedBus[] {
  const buses = view.buses
  const provided = providedLayout(view)
  if (provided) return provided
  const positions = buses.map((bus, index) => {
    const angle = (Math.PI * 2 * index) / Math.max(1, buses.length) - Math.PI / 2
    return { x: WIDTH / 2 + Math.cos(angle) * 290,
      y: HEIGHT / 2 + Math.sin(angle) * 185 }
  })

  const indexById = new Map(buses.map((bus, index) => [bus.id, index]))
  const edges = view.branches.flatMap((branch) => {
    const from = indexById.get(branch.from_bus)
    const to = indexById.get(branch.to_bus)
    return from === undefined || to === undefined ? [] : [[from, to] as const]
  })
  for (let iteration = 0; iteration < 100; iteration += 1) {
    const forces = positions.map(() => ({ x: 0, y: 0 }))
    for (let first = 0; first < positions.length; first += 1) {
      for (let second = first + 1; second < positions.length; second += 1) {
        const dx = positions[first].x - positions[second].x
        const dy = positions[first].y - positions[second].y
        const distance = Math.max(10, Math.hypot(dx, dy))
        const force = 28000 / (distance * distance)
        forces[first].x += force * dx / distance
        forces[first].y += force * dy / distance
        forces[second].x -= force * dx / distance
        forces[second].y -= force * dy / distance
      }
    }
    for (const [from, to] of edges) {
      const dx = positions[to].x - positions[from].x
      const dy = positions[to].y - positions[from].y
      const distance = Math.max(1, Math.hypot(dx, dy))
      const force = (distance - 132) * 0.025
      forces[from].x += force * dx / distance
      forces[from].y += force * dy / distance
      forces[to].x -= force * dx / distance
      forces[to].y -= force * dy / distance
    }
    const cooling = 1 - iteration / 100
    for (let index = 0; index < positions.length; index += 1) {
      positions[index].x = Math.min(955, Math.max(45,
        positions[index].x + Math.max(-12, Math.min(12, forces[index].x)) * cooling))
      positions[index].y = Math.min(555, Math.max(45,
        positions[index].y + Math.max(-12, Math.min(12, forces[index].y)) * cooling))
    }
  }
  return buses.map((bus, index) => ({ ...bus, ...positions[index] }))
}
