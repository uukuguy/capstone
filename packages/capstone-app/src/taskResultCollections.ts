import type { ResultProjection } from './threadProtocol'

export type TaskResultCollection = { id: string; attemptId: string; title: string; results: ResultProjection[] }

/** Membership is published by the execution chain, never inferred from labels. */
export function taskResultCollections(results: readonly ResultProjection[], attemptId: string): TaskResultCollection[] {
  const collections = new Map<string, TaskResultCollection>()
  for (const result of results) {
    const view = result.presentation
    if (result.attemptId !== attemptId || view?.purpose !== 'task_output' || result.status === 'unavailable') continue
    const id = JSON.stringify([result.threadId, result.runId, result.attemptId, result.source.domainPackId, view.collectionId])
    const collection = collections.get(id) || {id, attemptId, title:view.collectionTitle, results:[]}
    collection.results.push(result)
    collections.set(id, collection)
  }
  return [...collections.values()]
}
