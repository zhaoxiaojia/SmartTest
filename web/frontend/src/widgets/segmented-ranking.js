function element(tag, className, text) {
  const value = document.createElement(tag)
  if (className) value.className = className
  if (text != null) value.textContent = text
  return value
}

export function createSegmentedRanking({ chartFactory } = {}) {
  let root, chart, config
  let activeProductLine = ''
  let activeMode = ''

  function segments(target, options, active, setActive, className) {
    target.replaceChildren()
    for (const option of options) {
      const button = element('button', `${className}${option.value === active ? ' active' : ''}`, option.label)
      button.type = 'button'
      button.setAttribute('aria-pressed', String(option.value === active))
      button.addEventListener('click', () => { setActive(option.value); render() })
      target.append(button)
    }
  }

  function render() {
    const products = config.productLines ?? []
    const modes = config.modes ?? []
    if (!products.some(item => item.value === activeProductLine)) activeProductLine = products[0]?.value ?? ''
    if (!modes.some(item => item.value === activeMode)) activeMode = modes[0]?.value ?? ''
    segments(root.querySelector('[data-product-line-segments]'), products, activeProductLine, value => { activeProductLine = value }, 'product-line-segment')
    segments(root.querySelector('[data-mode-segments]'), modes, activeMode, value => { activeMode = value }, 'role-segment')
    chart?.destroy()
    chart = null
    const rows = (config.rowsFor?.(activeProductLine, activeMode) ?? [])
      .filter(row => row.count)
      .sort((left, right) => right.count - left.count || left.name.localeCompare(right.name))
    const total = rows.reduce((sum, row) => sum + row.count, 0)
    const surface = root.querySelector('.workload-chart-surface')
    surface.style.height = `${rows.length * 36}px`
    const empty = root.querySelector('[data-ranked-empty]')
    empty.hidden = Boolean(rows.length)
    empty.textContent = config.error || config.emptyText || 'No data in this product line.'
    const canvas = root.querySelector('[data-ranked-chart]')
    canvas.hidden = !rows.length
    if (!rows.length || !chartFactory) return
    chart = chartFactory(canvas, {
      type: 'bar', data: { labels: rows.map(row => row.name), datasets: [{ label: config.datasetLabel || '', data: rows.map(row => row.count) }] },
      options: { indexAxis: 'y', responsive: true, maintainAspectRatio: false,
        layout: { padding: { right: 28 } }, scales: { x: { beginAtZero: true, ticks: { precision: 0 } } },
        plugins: { legend: { display: false }, datalabels: { labels: {
          percentage: { anchor: 'end', align: 'left', offset: 4, color: '#fff', formatter: value => `${Math.round(value / total * 100)}%` },
          value: { anchor: 'end', align: 'right', offset: 4, clip: false, formatter: value => value },
        } } } },
    })
  }

  return {
    mount(target, value) {
      root = target; config = value
      root.innerHTML = `<div class="segmented-ranking"><header class="report-preview-toolbar"><div class="workload-heading">${config.headingHtml || ''}<div class="product-line-segments" data-product-line-segments></div></div><div class="role-segments" data-mode-segments></div></header><div class="workload-chart-scroll"><div class="workload-chart-surface"><canvas data-ranked-chart></canvas><div class="product-space-empty" data-ranked-empty data-workload-empty hidden></div></div></div></div>`
      render()
    },
    update(value) { config = value; if (root) render() },
    destroy() { chart?.destroy(); chart = null; root?.replaceChildren(); root = null },
  }
}
