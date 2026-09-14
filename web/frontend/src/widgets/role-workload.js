function node(tag, className, text) {
  const item = document.createElement(tag)
  if (className) item.className = className
  if (text != null) item.textContent = text
  return item
}

function readableName(person) {
  const name = String(person?.name ?? '').trim()
  const identity = String(person?.identity ?? '').trim()
  return !name || (identity && name.toLocaleLowerCase() === identity.toLocaleLowerCase()) ? 'Unknown member' : name
}

export const ROLE_WORKLOAD_LAYOUT = Object.freeze({
  defaultW: 24,
  defaultH: 21,
})

export function createRoleWorkloadWidget({ chartFactory } = {}) {
  let root
  let chart
  let data = { ownerHierarchy: [], productSpaces: [] }
  let activeRole = ''
  let activeProductLine = ''

  function render() {
    const roles = (data.ownerHierarchy ?? []).filter(role => role.people?.length)
    if (!roles.some(role => role.role === activeRole)) activeRole = roles[0]?.role ?? ''
    if (!(data.productSpaces ?? []).some(option => option.value === activeProductLine)) {
      activeProductLine = data.productSpaces?.[0]?.value ?? ''
    }
    const productLineSegments = root.querySelector('[data-product-line-segments]')
    productLineSegments.replaceChildren()
    for (const productLine of data.productSpaces ?? []) {
      const button = node('button', `product-line-segment${productLine.value === activeProductLine ? ' active' : ''}`, productLine.label)
      button.type = 'button'
      button.setAttribute('aria-pressed', String(productLine.value === activeProductLine))
      button.addEventListener('click', () => { activeProductLine = productLine.value; render() })
      productLineSegments.append(button)
    }
    const roleSegments = root.querySelector('[data-role-segments]')
    roleSegments.replaceChildren()
    for (const role of roles) {
      const button = node('button', `role-segment${role.role === activeRole ? ' active' : ''}`, role.role)
      button.type = 'button'
      button.setAttribute('aria-pressed', String(role.role === activeRole))
      button.addEventListener('click', () => { activeRole = role.role; render() })
      roleSegments.append(button)
    }
    chart?.destroy()
    chart = null
    const selectedRole = roles.find(item => item.role === activeRole)
    const rows = (selectedRole?.people ?? []).map(person => ({
      name: readableName(person),
      count: (person.projects ?? []).filter(project => project.space_key === activeProductLine).length,
    })).filter(person => person.count)
      .sort((left, right) => right.count - left.count || left.name.localeCompare(right.name))
    const surface = root.querySelector('.workload-chart-surface')
    surface.style.height = `${rows.length * 36}px`
    const empty = root.querySelector('[data-workload-empty]')
    empty.hidden = Boolean(rows.length)
    empty.textContent = data.error || 'No assignments in this product line.'
    const canvas = root.querySelector('[data-workload-chart]')
    canvas.hidden = !rows.length
    if (!rows.length || !chartFactory) return
    chart = chartFactory(canvas, {
      type: 'bar', data: { labels: rows.map(row => row.name), datasets: [{ label: 'Projects', data: rows.map(row => row.count) }] },
      options: { indexAxis: 'y', responsive: true, maintainAspectRatio: false,
        layout: { padding: { right: 28 } },
        scales: { x: { beginAtZero: true, ticks: { precision: 0 } } },
        plugins: { legend: { display: false }, datalabels: {
          anchor: 'end', align: 'right', clip: false, formatter: value => value,
        } } },
    })
  }

  return {
    mount(target, config = {}) {
      root = target
      const heading = config.shellTitle ? '' : '<div><strong>Role workload</strong><div class="report-preview-meta">Project assignments per QA member</div></div>'
      root.innerHTML = `<div class="role-workload"><header class="report-preview-toolbar"><div class="workload-heading">${heading}<div class="product-line-segments" data-product-line-segments></div></div><div class="role-segments" data-role-segments></div></header><div class="workload-chart-scroll"><div class="workload-chart-surface"><canvas data-workload-chart></canvas><div class="product-space-empty" data-workload-empty hidden>No assignments in this product line.</div></div></div></div>`
      data = config
      render()
    },
    update(config = {}) { data = config; if (root) render() },
    destroy() { chart?.destroy(); chart = null; root?.replaceChildren(); root = null },
  }
}
