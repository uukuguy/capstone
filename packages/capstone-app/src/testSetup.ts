// jsdom lacks the browser observer used by assistant-ui's viewport.
globalThis.ResizeObserver = class implements ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}
