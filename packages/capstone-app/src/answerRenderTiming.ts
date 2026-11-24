const arrivals = new Map<string, number>()
const maximumArrivals = 128

export function recordAnswerArrival(attemptId: string) {
  if (!import.meta.env.DEV || arrivals.has(attemptId)) return
  if (arrivals.size >= maximumArrivals) {
    const oldest = arrivals.keys().next().value
    if (oldest !== undefined) arrivals.delete(oldest)
  }
  arrivals.set(attemptId, performance.now())
}

export function consumeAnswerArrival(attemptId: string) {
  const time = arrivals.get(attemptId)
  arrivals.delete(attemptId)
  return time
}

export function hasAnswerArrival(attemptId: string) {
  return arrivals.has(attemptId)
}
