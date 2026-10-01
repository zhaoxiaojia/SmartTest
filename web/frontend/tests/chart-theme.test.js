// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest'
import { Chart, registerables, BasicPlatform } from 'chart.js'
import ChartDataLabels from 'chartjs-plugin-datalabels'
import { initializeTheme, initializeChartTheme } from '../src/theme.js'

Chart.register(...registerables, ChartDataLabels)
afterEach(() => { Object.values(Chart.instances).forEach(chart => chart.destroy()); document.documentElement.style.cssText = ''; vi.restoreAllMocks() })

it('refreshes resolved chart defaults once per theme while preserving explicit text colors', () => {
  initializeTheme()
  document.documentElement.style.setProperty('--text-primary', '#1e293b')
  const stop = initializeChartTheme(Chart)
  expect(initializeChartTheme(Chart)).toBe(stop)
  const create = options => {
    const canvas = { width: 600, height: 300, style: {}, getContext: () => context }
    const context = new Proxy({ canvas, measureText: text => ({ width: String(text).length * 7 }) }, { get: (target, key) => key in target ? target[key] : () => {} })
    return new Chart(canvas, { type: 'bar', platform: BasicPlatform, data: { labels: ['Alice'], datasets: [{ label: 'Current', data: [3] }] }, options: { responsive: false, animation: false, plugins: { title: { display: true, text: 'Title' } }, ...options } })
  }
  try {
    const ordinary = create({})
    const custom = create({ color: '#ff00ff', scales: { x: { ticks: { color: '#00ff00' } } }, plugins: { legend: { labels: { color: '#ff0000' } }, title: { display: true, text: 'Custom', color: '#ffaa00' }, datalabels: { color: '#00ffff' } } })
    expect(ordinary.scales.x.options.ticks.color).toBe('#1e293b')
    const update = vi.spyOn(ordinary, 'update')
    for (const [theme, color] of [['dark', '#ffffff'], ['light', '#1e293b']]) {
      document.documentElement.style.setProperty('--text-primary', color)
      globalThis.SmartTestTheme.apply(theme)
      expect(ordinary.scales.x.options.ticks.color).toBe(color)
      expect(ordinary.options.plugins.legend.labels.color).toBe(color)
      expect(ordinary.options.plugins.title.color).toBe(color)
      expect(custom.options.color).toBe('#ff00ff')
      expect(custom.scales.x.options.ticks.color).toBe('#00ff00')
      expect(custom.options.plugins.legend.labels.color).toBe('#ff0000')
      expect(custom.options.plugins.title.color).toBe('#ffaa00')
      expect(custom.options.plugins.datalabels.color).toBe('#00ffff')
      if (theme === 'dark') {
        const added = create({})
        expect(added.scales.x.options.ticks.color).toBe(color)
        expect(added.options.plugins.legend.labels.color).toBe(color)
        added.destroy()
      }
    }
    expect(update).toHaveBeenCalledTimes(2)
    expect(update).toHaveBeenLastCalledWith('none')
  } finally { stop() }
})
