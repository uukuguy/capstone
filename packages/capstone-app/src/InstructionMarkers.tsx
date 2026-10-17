import { useEffect, useState, type RefObject } from 'react'

type Marker = { node: HTMLElement; top: number; label: string; current: boolean }

export default function InstructionMarkers({ viewportRef }: { viewportRef: RefObject<HTMLDivElement | null> }) {
  const [markers, setMarkers] = useState<Marker[]>([])
  const [height, setHeight] = useState(0)
  const [scrolling, setScrolling] = useState(false)
  const [nearEdge, setNearEdge] = useState(false)
  const [hovered, setHovered] = useState<number | null>(null)
  useEffect(() => {
    const viewport = viewportRef.current
    if (!viewport) return undefined
    let frame = 0
    let hideTimer: ReturnType<typeof setTimeout> | undefined
    const update = () => {
      frame = 0
      const rect = viewport.getBoundingClientRect()
      const nodes = [...viewport.querySelectorAll<HTMLElement>('.capstone-chat-message.is-user')]
      const positions = nodes.map(node => node.getBoundingClientRect().top - rect.top + viewport.scrollTop)
      const visible = positions.reduce((found, top, index) => top <= viewport.scrollTop + viewport.clientHeight / 3 ? index : found, -1)
      setHeight(viewport.clientHeight)
      setMarkers(nodes.map((node, index) => ({ node, top: Math.max(0, Math.min(100, positions[index] / Math.max(1, viewport.scrollHeight) * 100)),
        label: `指令 ${index + 1}：${node.querySelector('.capstone-chat-body p')?.textContent?.trim() || node.textContent?.trim() || ''}`,
        current: index === Math.max(0, visible) })))
    }
    const schedule = () => { if (!frame) frame = requestAnimationFrame(update) }
    const onScroll = () => {
      if (viewport.scrollHeight <= viewport.clientHeight) return
      setScrolling(true)
      clearTimeout(hideTimer)
      hideTimer = setTimeout(() => setScrolling(false), 1000)
      schedule()
    }
    const resize = new ResizeObserver(schedule)
    const observe = () => {
      resize.disconnect()
      resize.observe(viewport)
      for (const child of viewport.children) resize.observe(child)
      schedule()
    }
    const mutations = new MutationObserver(observe)
    mutations.observe(viewport, { childList: true, subtree: true, characterData: true })
    viewport.addEventListener('scroll', onScroll, { passive: true })
    viewport.addEventListener('wheel', onScroll, { passive: true })
    const onPointerMove = (event: PointerEvent) => { setNearEdge(event.clientX >= viewport.getBoundingClientRect().right - 48) }
    const onPointerLeave = () => setNearEdge(false)
    viewport.addEventListener('pointermove', onPointerMove)
    viewport.addEventListener('pointerleave', onPointerLeave)
    window.addEventListener('resize', schedule)
    observe()
    return () => { clearTimeout(hideTimer); cancelAnimationFrame(frame); resize.disconnect(); mutations.disconnect(); viewport.removeEventListener('scroll', onScroll); viewport.removeEventListener('wheel', onScroll); viewport.removeEventListener('pointermove', onPointerMove); viewport.removeEventListener('pointerleave', onPointerLeave); window.removeEventListener('resize', schedule) }
  }, [viewportRef])
  const position = (index: number) => Math.max(4, Math.min(height - 44, markers[index].top * height / 100))
  const chosen: number[] = []
  const current = markers.findIndex(marker => marker.current)
  // Current first, then recent instructions. Older crowded markers yield space.
  for (const index of [current, ...markers.map((_, index) => index).reverse()]) {
    if (index >= 0 && !chosen.includes(index) && chosen.every(other => Math.abs(position(other) - position(index)) >= 48)) chosen.push(index)
  }
  return <nav className={`capstone-instruction-markers${scrolling ? ' is-scrolling' : ''}${nearEdge || hovered !== null ? ' is-near-edge' : ''}`} aria-label="用户指令位置" style={{ height }}
    onPointerEnter={() => setNearEdge(true)} onPointerLeave={() => { setNearEdge(false); setHovered(null) }}>
    {chosen.sort((a,b)=>a-b).map(index => { const marker=markers[index]; const preview=scrolling ? marker.current : hovered !== null ? hovered===index : nearEdge
      return <button key={marker.node.dataset.messageId || index} type="button"
      style={{ top: position(index) }} aria-label={marker.label} aria-current={marker.current ? 'location' : undefined}
      onPointerEnter={() => setHovered(index)} onPointerLeave={() => setHovered(null)} onFocus={() => setHovered(index)} onBlur={() => setHovered(null)}
      onClick={() => { const viewport = viewportRef.current; if (!viewport) return; viewport.scrollTo({top:viewport.scrollTop + marker.node.getBoundingClientRect().top - viewport.getBoundingClientRect().top - 12, behavior:window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth'}); marker.node.focus({ preventScroll: true }) }}><span /><span className={`capstone-instruction-marker-tip${preview ? ' is-visible' : ''}`} aria-hidden="true">{marker.label}</span></button>
    })}
  </nav>
}
