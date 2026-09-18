// @vitest-environment jsdom
import { expect, it, vi } from 'vitest'
import { createRankingCard } from '../src/widgets/ranking-card.js'

it('keeps dimension groups independent while querying both selected values', () => {
  const root = document.createElement('div')
  const rowsFor = vi.fn(() => [])
  const config = { productLines: [{ value: 'a', label: 'A' }, { value: 'b', label: 'B' }],
    modes: [{ value: 'x', label: 'X' }, { value: 'y', label: 'Y' }], rowsFor }
  const card = createRankingCard()
  card.mount(root, config)
  const products = [...root.querySelectorAll('[data-product-line-segments] button')]
  const modes = [...root.querySelectorAll('[data-mode-segments] button')]
  modes[1].click()
  expect([...root.querySelectorAll('[data-product-line-segments] button')]).toEqual(products)
  expect(products[0].classList.contains('active')).toBe(true)
  expect(rowsFor).toHaveBeenLastCalledWith('a', 'y')
  products[1].click()
  expect([...root.querySelectorAll('[data-mode-segments] button')]).toEqual(modes)
  expect(modes[1].classList.contains('active')).toBe(true)
  expect(rowsFor).toHaveBeenLastCalledWith('b', 'y')
  card.update({ ...config })
  expect([...root.querySelectorAll('[data-product-line-segments] button')]).toEqual(products)
  card.destroy()
})

it('grows initially and updates the same people without restarting from zero, resetting changed identities only', () => {
  const root = document.createElement('div')
  const chartFactory = vi.fn((_canvas, config) => ({ data: config.data, options: config.options,
    update: vi.fn(), reset: vi.fn(), stop: vi.fn(), destroy: vi.fn() }))
  const card = createRankingCard({ chartFactory })
  let rows = [{ name: 'Alice', count: 2 }, { name: 'Bob', count: 1 }]
  const config = { productLines: [{ value: 'a', label: 'A' }], modes: [{ value: 'x', label: 'X' }], rowsFor: () => rows }
  card.mount(root, config)
  const chart = chartFactory.mock.results[0].value
  expect(chart.options.animation.duration).toBe(500)
  expect(chart.options.animation.delay({ type: 'data', dataIndex: 1 })).toBe(40)
  expect(chart.options.animation.delay({ type: 'data', dataIndex: 30 })).toBe(400)
  expect(chart.options.animation.delay({ type: 'dataset', dataIndex: 3 })).toBe(0)
  expect(chart.options.transitions.resize.animation.duration).toBe(500)
  expect(chart.options.animations.y.duration).toBe(0)
  rows = [{ name: 'Alice', count: 4 }, { name: 'Bob', count: 1 }]
  card.update(config)
  expect(chartFactory).toHaveBeenCalledOnce()
  expect(chart.data.datasets[0].data).toEqual([4, 1])
  expect(chart.update).toHaveBeenCalledOnce()
  expect(chart.reset).not.toHaveBeenCalled()
  rows = [{ name: 'Bob', count: 5 }, { name: 'Alice', count: 4 }]
  card.update(config)
  expect(chart.data.labels).toEqual(['Bob', 'Alice'])
  expect(chart.reset).toHaveBeenCalledOnce()
  expect(chart.update).toHaveBeenCalledWith('none')
  rows = []; card.update(config)
  expect(chart.destroy).toHaveBeenCalledOnce()
  card.destroy()
  expect(chart.destroy).toHaveBeenCalledOnce()
})

it('turns off chart animation when reduced motion is requested', () => {
  vi.stubGlobal('matchMedia', () => ({ matches: true }))
  const chartFactory = vi.fn((_canvas, config) => ({ data: config.data, options: config.options,
    update: vi.fn(), reset: vi.fn(), stop: vi.fn(), destroy: vi.fn() }))
  const card = createRankingCard({ chartFactory })
  const config = { productLines: [{ value: 'a', label: 'A' }], modes: [{ value: 'x', label: 'X' }], rowsFor: () => [{ name: 'Alice', count: 1 }] }
  card.mount(document.createElement('div'), config)
  const chart = chartFactory.mock.results[0].value
  expect(chart.options.animation).toBe(false)
  expect(chart.options.transitions.resize.animation.duration).toBe(0)
  card.update(config)
  expect(chart.update).toHaveBeenCalledWith('none')
  expect(chart.reset).not.toHaveBeenCalled()
  card.destroy(); vi.unstubAllGlobals()
})

it('animates finite horizontal bar geometry with real Chart.js, including resize', async () => {
  let frame
  vi.spyOn(window, 'requestAnimationFrame').mockImplementation(callback => { frame = callback; return 1 })
  vi.useFakeTimers()
  vi.setSystemTime(1000)
  const { Chart, registerables, BasicPlatform } = await import('chart.js')
  Chart.register(...registerables)
  class AnimationPlatform extends BasicPlatform { updateConfig() {} }
  let chart
  const card = createRankingCard({ chartFactory: (_canvas, config) => {
    const canvas = { width: 800, height: 108, style: {}, getContext: () => context }
    const context = new Proxy({ canvas, measureText: text => ({ width: String(text).length * 7 }) }, {
      get: (target, key) => key in target ? target[key] : () => {},
    })
    chart = new Chart(canvas, { ...config, platform: AnimationPlatform,
      options: { ...config.options, responsive: false },
      plugins: [{ id: 'skip-rasterization', beforeDraw: () => false }],
    })
    return chart
  } })
  try {
    card.mount(document.createElement('div'), {
      productLines: [{ value: 'a', label: 'A' }], modes: [{ value: 'x', label: 'X' }],
      rowsFor: () => [{ name: 'Alice', count: 4 }, { name: 'Bob', count: 4 }],
    })
    const bars = chart.getDatasetMeta(0).data
    vi.setSystemTime(1200); frame()
    expect(bars.every(bar => Number.isFinite(bar.x) && Number.isFinite(bar.width))).toBe(true)
    expect(bars[0].width).toBeGreaterThan(bars[1].width)
    expect(bars[1].width).toBeGreaterThan(0)
    chart.resize(800, 144)
    chart.update('resize')
    vi.setSystemTime(1400); frame()
    expect(bars.every(bar => Number.isFinite(bar.x) && Number.isFinite(bar.width))).toBe(true)
    vi.setSystemTime(2200); frame()
    expect(bars[0].width).toBeCloseTo(bars[1].width)
  } finally {
    card.destroy(); vi.useRealTimers(); vi.restoreAllMocks()
  }
})
