/** Live durations use the API clock, then advance on a monotonic clock. */
let sample: {server: number; monotonic: number; roundTrip: number} | undefined
export function observeServerClock(date: string | null, started: number, ended: number): void {
  const server = Date.parse(date ?? '')
  const roundTrip = ended - started
  if (!Number.isFinite(server) || roundTrip < 0 || roundTrip > 2000) return
  if (sample && roundTrip > sample.roundTrip && ended - sample.monotonic < 60000) return
  sample = {server: server + 500 + roundTrip / 2, monotonic: ended, roundTrip}
}
export function serverNow(): number {
  return sample ? sample.server + performance.now() - sample.monotonic : Date.now()
}
export function resetServerClock(): void { sample = undefined }
