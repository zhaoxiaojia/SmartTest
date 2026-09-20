import { describe, expect, it, vi } from 'vitest'
import { createTaskController } from '../src/task-polling.js'

describe('task controller', () => {
  it('ignores stale completions and stops after dispose', async () => {
    const release = []
    const fetchStatus = vi.fn(id => new Promise(resolve => release.push(() => resolve({ id, state: 'completed' }))))
    const controller = createTaskController({ delay: async () => {} })
    const first = controller.run(fetchStatus, 'old')
    const second = controller.run(fetchStatus, 'new')
    release[0](); release[1]()
    expect(await first).toBeNull()
    expect(await second).toEqual({ id: 'new', state: 'completed' })
    controller.dispose()
    expect(await controller.run(fetchStatus, 'late')).toBeNull()
  })

  it('polls queued and running states until a terminal task', async () => {
    const fetchStatus = vi.fn()
      .mockResolvedValueOnce({ state: 'queued' })
      .mockResolvedValueOnce({ state: 'running' })
      .mockResolvedValueOnce({ state: 'failed' })
    const delay = vi.fn().mockResolvedValue()
    const controller = createTaskController({ delay })
    expect(await controller.run(fetchStatus, 'task')).toEqual({ state: 'failed' })
    expect(delay).toHaveBeenCalledTimes(2)
  })
})
