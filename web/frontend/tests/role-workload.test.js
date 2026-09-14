// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createRoleWorkloadWidget, ROLE_WORKLOAD_LAYOUT } from '../src/widgets/role-workload.js'

const productSpaces = [
  { value: 'DOPL', label: 'China Operator Business' },
  { value: 'SDPL', label: 'Smart Device Business' },
  { value: 'TV', label: 'TV Business' },
  { value: 'OOPL', label: 'Global Operator & STB Business' },
]

describe('RoleWorkloadWidget', () => {
  beforeEach(() => { document.body.innerHTML = '<div id="root"></div>' })

  it('keeps the proven current full-width layout as its minimum width', () => {
    expect(ROLE_WORKLOAD_LAYOUT).toEqual({ defaultW: 24, defaultH: 21 })
  })

  it('keeps the Projects workload sorting, identity cleanup, switching, and chart lifecycle', () => {
    const charts = []
    const chartFactory = vi.fn((canvas, config) => {
      const chart = { config, destroy: vi.fn() }; charts.push(chart); return chart
    })
    const widget = createRoleWorkloadWidget({ chartFactory })
    widget.mount(document.querySelector('#root'), {
      productSpaces,
      ownerHierarchy: [{ role: 'FAE QA', people: [
        { name: '2c93-user', identity: '2c93-user', projects: [{ space_key: 'TV' }] },
        { name: 'Alice', identity: 'alice-key', projects: [{ space_key: 'DOPL' }, { space_key: 'TV' }] },
        { name: 'Bob', identity: 'bob-key', projects: [{ space_key: 'TV' }, { space_key: 'TV' }] },
      ] }],
    })
    expect(charts.at(-1).config.data.labels).toEqual(['Alice'])
    expect(document.body.textContent).not.toContain('2c93-user')
    ;[...document.querySelectorAll('[data-product-line-segments] button')]
      .find(button => button.textContent === 'TV Business').click()
    expect(charts.at(-1).config.data.labels).toEqual(['Bob', 'Alice', 'Unknown member'])
    expect(charts.at(-1).config.data.datasets[0].data).toEqual([2, 1, 1])
    expect(charts[0].destroy).toHaveBeenCalledOnce()
    widget.destroy()
    expect(charts.at(-1).destroy).toHaveBeenCalledOnce()
    expect(document.querySelector('#root').childElementCount).toBe(0)
  })

  it('keeps the existing bounded viewport and per-person chart height', () => {
    const widget = createRoleWorkloadWidget({ chartFactory: () => ({ destroy() {} }) })
    widget.mount(document.querySelector('#root'), {
      productSpaces,
      ownerHierarchy: [{ role: 'FAE QA', people: Array.from({ length: 20 }, (_, index) => ({
        name: `Member ${index}`, identity: `member-${index}`, projects: [{ space_key: 'DOPL' }],
      })) }],
    })
    expect(document.querySelector('.workload-chart-surface').style.height).toBe('720px')
    expect(document.querySelector('.workload-chart-scroll')).not.toBeNull()
  })

  it('shows the existing empty surface when project facts are unavailable', () => {
    const widget = createRoleWorkloadWidget()
    widget.mount(document.querySelector('#root'), { error: 'Local project facts API is unavailable.' })
    expect(document.querySelector('[data-workload-empty]').hidden).toBe(false)
    expect(document.querySelector('[data-workload-empty]').textContent).toBe('Local project facts API is unavailable.')
  })
})
