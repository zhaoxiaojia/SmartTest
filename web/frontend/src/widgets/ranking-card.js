import './ranking-card.css'
import { element } from '../dom.js'

export function createRankingCard({ chartFactory } = {}) {
  let root, chart, config
  let activeProductLine = ''
  let activeMode = ''
  const resizeObserver = typeof ResizeObserver === 'function' ? new ResizeObserver(() => {
    if (root) positionModeBackground(root.querySelector('[data-mode-segments]'))
  }) : null

  function segments(target, options, active, setActive, className) {
    const buttons = [...target.children]
    if (buttons.length !== options.length || buttons.some((button, index) => button.dataset.value !== String(options[index].value))) {
      target.replaceChildren()
      for (const option of options) {
        const button = element('button', className, option.label)
        button.type = 'button'
        button.dataset.value = String(option.value)
        button.addEventListener('click', () => {
          setActive(option.value)
          selectSegment(target, option.value)
          renderChart()
        })
        target.append(button)
      }
    }
    ;[...target.children].forEach((button, index) => { button.textContent = options[index].label })
    selectSegment(target, active)
  }

  function selectSegment(target, active) {
    for (const button of target.children) {
      const selected = button.dataset.value === String(active)
      button.classList.toggle('active', selected)
      button.setAttribute('aria-pressed', String(selected))
    }
    if (target.matches('[data-mode-segments]')) positionModeBackground(target)
  }

  function positionModeBackground(target) {
    const selected = target.querySelector('.active')
    if (!selected) return
    target.style.setProperty('--segment-left', `${selected.offsetLeft}px`)
    target.style.setProperty('--segment-width', `${selected.offsetWidth}px`)
  }

  function render() {
    const products = config.productLines ?? []
    const modes = config.modes ?? []
    if (!products.some(item => item.value === activeProductLine)) activeProductLine = products[0]?.value ?? ''
    if (!modes.some(item => item.value === activeMode)) activeMode = modes[0]?.value ?? ''
    segments(root.querySelector('[data-product-line-segments]'), products, activeProductLine, value => { activeProductLine = value }, 'product-line-segment')
    segments(root.querySelector('[data-mode-segments]'), modes, activeMode, value => { activeMode = value }, 'role-segment')
    renderChart()
  }

  function renderChart() {
    const rows = (config.rowsFor?.(activeProductLine, activeMode) ?? [])
      .filter(row => row.count)
      .sort((left, right) => right.count - left.count || left.name.localeCompare(right.name))
    const total = rows.reduce((sum, row) => sum + row.count, 0)
    const surface = root.querySelector('.workload-chart-surface')
    surface.style.height = `${rows.length * 36 + 36}px`
    const empty = root.querySelector('[data-ranked-empty]')
    empty.hidden = Boolean(rows.length)
    empty.textContent = config.error || config.emptyText || 'No data in this product line.'
    const canvas = root.querySelector('[data-ranked-chart]')
    canvas.hidden = !rows.length
    if (!rows.length || !chartFactory) {
      chart?.destroy()
      chart = null
      return
    }
    const reducedMotion = globalThis.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    const next = {
      type: 'bar', data: { labels: rows.map(row => row.name), datasets: [{ label: config.datasetLabel || '', data: rows.map(row => row.count) }] },
      options: { indexAxis: 'y', responsive: true, maintainAspectRatio: false,
        animation: reducedMotion ? false : { duration: 500, easing: 'easeOutQuart',
          delay: context => context.type === 'data' ? Math.min(context.dataIndex * 40, 400) : 0 },
        transitions: { resize: { animation: { duration: reducedMotion ? 0 : 500 } } },
        animations: { y: { duration: 0 }, width: {
          from: context => Number.isFinite(context.element?.width) ? context.element.width : 0,
        } },
        layout: { padding: { right: 28 } }, scales: {
          x: { beginAtZero: true, ticks: { precision: 0 } },
          y: { ticks: { autoSkip: false } },
        },
        plugins: { legend: { display: false }, datalabels: { labels: {
          percentage: { anchor: 'end', align: 'left', offset: 4, color: '#fff', formatter: value => `${Math.round(value / total * 100)}%` },
          value: { anchor: 'end', align: 'right', offset: 4, clip: false, formatter: value => value },
        } } } },
    }
    if (!chart) {
      chart = chartFactory(canvas, next)
      return
    }
    const labelsChanged = chart.data.labels.length !== next.data.labels.length
      || chart.data.labels.some((label, index) => label !== next.data.labels[index])
    chart.stop()
    chart.data = next.data
    chart.options = next.options
    if (labelsChanged && !reducedMotion) {
      // Reordered rows must not morph one person's bar into another person's bar.
      chart.update('none')
      chart.reset()
    }
    if (reducedMotion) chart.update('none')
    else chart.update()
  }

  return {
    mount(target, value) {
      root = target; config = value
      root.innerHTML = `<div class="segmented-ranking"><header class="report-preview-toolbar"><div class="workload-heading">${config.headingHtml || ''}<div class="product-line-segments" data-product-line-segments></div></div><div class="role-segments" data-mode-segments></div></header><div class="workload-chart-scroll"><div class="workload-chart-surface"><canvas data-ranked-chart></canvas><div class="product-space-empty" data-ranked-empty data-workload-empty hidden></div></div></div></div>`
      render()
      resizeObserver?.observe(root.querySelector('[data-mode-segments]'))
    },
    update(value) { config = value; if (root) render() },
    destroy() { resizeObserver?.disconnect(); chart?.destroy(); chart = null; root?.replaceChildren(); root = null },
  }
}
