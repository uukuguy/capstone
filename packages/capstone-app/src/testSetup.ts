// jsdom lacks the browser observer used by assistant-ui's viewport.
globalThis.ResizeObserver = class implements ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}
// assistant-ui schedules scrollTo on animation frames, including after tests.
// jsdom has no scroll layout; keep the browser method present for that lifecycle.
HTMLElement.prototype.scrollTo = function () {}
