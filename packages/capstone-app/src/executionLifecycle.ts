/** Reserved application-owned IDs from ExecutionStages, independent of titles. */
export function isExecutionLifecycleStep(id: string): boolean {
  return id === 'task-preparation' || id === 'task-execution' || /^task-finalization-[1-9]\d*$/.test(id)
}
