// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createDashboardGrid, normalizeLayout } from '../src/dashboard/dashboard-grid.js'
import { createWidgetRegistry } from '../src/dashboard/widget-registry.js'

function harness({ preference = { items: {} } } = {}) {
  document.body.innerHTML = '<div id="root"></div>'
  const nodes = []
  const grid = {
    enableMove: vi.fn(), destroy: vi.fn(), removeAll: vi.fn(),
    makeWidget: vi.fn((element, options) => { element.gridstackNode = { ...options, el: element }; nodes.push(element); return element }),
    removeWidget: vi.fn(element => element.remove()),
    save: vi.fn(() => nodes.filter(node => node.isConnected).map(node => ({ ...node.gridstackNode, content: '<unsafe>' }))),
  }
  const gridFactory = vi.fn(() => grid)
  const instances = []
  const registry = createWidgetRegistry()
  registry.register({ type: 'role-workload', title: 'Role workload', defaultW: 24, defaultH: 21,
    create: () => { const instance = { mount: vi.fn(), update: vi.fn(), destroy: vi.fn() }; instances.push(instance); return instance } })
  registry.register({ type: 'jira-team-bugs', title: 'Team Jira bugs', defaultW: 24, defaultH: 16,
    create: () => { const instance = { mount: vi.fn(), update: vi.fn(), destroy: vi.fn() }; instances.push(instance); return instance } })
  const preferenceApi = { get: vi.fn().mockResolvedValue(preference), put: vi.fn().mockResolvedValue({}), reset: vi.fn().mockResolvedValue({}) }
  const page = createDashboardGrid({ root: document.querySelector('#root'), registry, preferenceApi, gridFactory })
  return { page, grid, gridFactory, instances, preferenceApi }
}

describe('DashboardGrid', () => {
  beforeEach(() => { document.body.innerHTML = '' })

  it('normalizes valid registered widgets and reports invalid or unknown records without HTML', () => {
    const registry = createWidgetRegistry()
    registry.register({ type: 'role-workload', title: 'Role workload', defaultW: 24, defaultH: 20, create() {} })
    const result = normalizeLayout([
      { id: 'good', type: 'role-workload', x: 0, y: 0, w: 24, h: 20, content: '<b>x</b>', config: {} },
      { id: 'bad', type: 'unknown', x: 0, y: 0, w: 1, h: 1 },
      { id: 'wide', type: 'role-workload', x: 23, y: 0, w: 2, h: 20 },
    ], registry)
    expect(result.layout).toEqual([{ id: 'good', type: 'role-workload', x: 0, y: 0, w: 24, h: 20, config: {} }])
    expect(result.errors).toHaveLength(2)
  })

  it('loads the default as read-only and only writes an allowlisted maximum-column layout on save', async () => {
    const { page, grid, preferenceApi } = harness()
    await page.start()
    expect(document.querySelector('[data-widget-type="role-workload"]')).not.toBeNull()
    expect(document.querySelector('[data-widget-type="jira-team-bugs"]')).not.toBeNull()
    expect(grid.enableMove).toHaveBeenLastCalledWith(false)
    document.querySelector('[data-edit-dashboard]').click()
    expect(grid.enableMove).toHaveBeenLastCalledWith(true)
    expect(document.querySelector('.dashboard-workspace').classList.contains('is-editing')).toBe(true)
    document.querySelector('[data-save-dashboard]').click()
    await vi.waitFor(() => expect(preferenceApi.put).toHaveBeenCalledOnce())
    expect(grid.save).toHaveBeenCalledWith(false)
    expect(preferenceApi.put.mock.calls[0]).toEqual(['dashboard/layout', { layout: [{
      id: 'role-workload-default', type: 'role-workload', x: 0, y: 0, w: 24, h: 21, config: {},
    }, { id: 'jira-team-bugs-default', type: 'jira-team-bugs', x: 0, y: 21, w: 24, h: 16, config: {} }] }])
    page.destroy()
    expect(grid.destroy).toHaveBeenCalledOnce()
  })

  it('saves the registered fixed size instead of a changed GridStack size', async () => {
    const { page, grid, preferenceApi } = harness()
    await page.start()
    document.querySelector('[data-edit-dashboard]').click()
    grid.save.mockReturnValue([{
      id: 'role-workload-default', type: 'role-workload', x: 0, y: 0,
      w: 12, h: 9,
    }])
    document.querySelector('[data-save-dashboard]').click()
    await vi.waitFor(() => expect(preferenceApi.put).toHaveBeenCalledOnce())
    expect(preferenceApi.put.mock.calls[0][1].layout[0]).toMatchObject({ w: 24, h: 21 })
    expect(document.querySelector('[data-dashboard-status]').textContent).toBe('')
  })

  it('configures the 24/12/1 responsive grid with resizing disabled', async () => {
    const { page, gridFactory } = harness()
    await page.start()
    const options = gridFactory.mock.calls[0][0]
    expect(options).toMatchObject({
      column: 24, cellHeight: 30, margin: 8,
      columnOpts: { breakpoints: [{ w: 700, c: 1 }, { w: 1180, c: 12 }] },
      disableResize: true,
    })
  })

  it('selects an addable widget from the registry before adding it at its registered size', async () => {
    const { page, grid } = harness()
    await page.start()
    document.querySelector('[data-edit-dashboard]').click()
    const addButton = document.querySelector('[data-add-widget]')
    addButton.click()
    const picker = document.querySelector('[data-widget-picker]')
    expect(addButton.getAttribute('aria-expanded')).toBe('true')
    expect(picker.hidden).toBe(false)
    expect([...picker.querySelectorAll('[data-add-widget-type]')].map(button => button.textContent)).toEqual(['Role workload', 'Team Jira bugs'])
    picker.querySelector('[data-add-widget-type="role-workload"]').click()
    expect(picker.hidden).toBe(true)
    expect(grid.makeWidget.mock.calls.at(-1)[1]).toMatchObject({ type: 'role-workload', w: 24, h: 21, noResize: true })
  })

  it('cancels in-memory edits without writing and destroys replaced instances', async () => {
    const { page, instances, preferenceApi } = harness()
    await page.start()
    document.querySelector('[data-edit-dashboard]').click()
    document.querySelector('[data-remove-widget]').click()
    expect(instances[0].destroy).toHaveBeenCalledOnce()
    document.querySelector('[data-cancel-dashboard]').click()
    expect(preferenceApi.put).not.toHaveBeenCalled()
    expect(document.querySelector('[data-widget-type="role-workload"]')).not.toBeNull()
  })

  it('deletes the personal preference only after saving a restored default', async () => {
    const personal = { items: { layout: [{ id: 'personal', type: 'role-workload', x: 0, y: 4, w: 12, h: 14, config: {} }] } }
    const { page, preferenceApi } = harness({ preference: personal })
    await page.start()
    document.querySelector('[data-edit-dashboard]').click()
    document.querySelector('[data-restore-dashboard]').click()
    expect(preferenceApi.reset).not.toHaveBeenCalled()
    document.querySelector('[data-save-dashboard]').click()
    await vi.waitFor(() => expect(preferenceApi.reset).toHaveBeenCalledWith('dashboard/layout'))
    expect(preferenceApi.put).not.toHaveBeenCalled()
  })

  it('keeps edit mode and reports invalid serialized coordinates instead of writing', async () => {
    const { page, grid, preferenceApi } = harness()
    await page.start()
    document.querySelector('[data-edit-dashboard]').click()
    grid.save.mockReturnValue([{ id: 'role-workload-default', type: 'role-workload', x: -1, y: 0, w: 24, h: 21 }])
    document.querySelector('[data-save-dashboard]').click()
    await vi.waitFor(() => expect(document.querySelector('[data-dashboard-status]').textContent).toContain('Invalid dashboard widget'))
    expect(document.querySelector('[data-edit-actions]').hidden).toBe(false)
    expect(preferenceApi.put).not.toHaveBeenCalled()
  })
})
