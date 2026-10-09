export type ControlPhase = 'idle' | 'configuration' | 'submitting' | 'uncertain' | 'running' | 'interrupted' | 'unavailable'
export function controlPolicy(phase: ControlPhase) {
  return { editDraft: true, configure: phase === 'idle', send: phase === 'idle', retry: phase === 'idle' || phase === 'interrupted' }
}

/** One owner spans a complete UI operation, including its ordered model step. */
export class OperationGate {
  private owner?: symbol
  acquire(eligible: boolean): symbol | undefined {
    if (!eligible || this.owner) return
    return this.owner = Symbol('workspace operation')
  }
  owns(token?: symbol): boolean { return token !== undefined && token === this.owner }
  release(token: symbol): void { if (this.owns(token)) this.owner = undefined }
}
