const ACTIVE = new Set(['queued', 'running'])

export function createTaskController({ delay = ms => new Promise(resolve => setTimeout(resolve, ms)), interval = 250,
  stateOf = task => task?.state } = {}) {
  let generation = 0
  let disposed = false

  async function run(fetchStatus, taskId, onUpdate) {
    if (disposed) return null
    const current = ++generation
    while (!disposed && current === generation) {
      const task = await fetchStatus(taskId)
      if (disposed || current !== generation) return null
      onUpdate?.(task)
      if (!ACTIVE.has(stateOf(task))) return task
      await delay(interval)
    }
    return null
  }

  return {
    run,
    cancel() { generation += 1 },
    dispose() { disposed = true; generation += 1 },
  }
}
