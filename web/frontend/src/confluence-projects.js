const STATE_COPY = {
  loading: 'Loading local project facts…',
  ready: '',
  no_snapshot: 'No local project snapshot is available.',
  schema_error: 'Local project snapshot is unreadable.',
  partial_success: 'Some project facts are stale or failed.',
  failed: 'Project facts refresh failed. Sign in and retry refresh.',
  reauthentication_required: 'Please verify your account again before refreshing Confluence data.'
}
const COMMON_FILTERS = [
  '__product_space__', 'date of commercial approval', 'project id',
  'project status', 'current stage', 'project owner', 'support mode'
]

function node(tag, className, text) {
  const item = document.createElement(tag)
  if (className) item.className = className
  if (text != null) item.textContent = text
  return item
}

export function createConfluenceProjects({ root, api, chartFactory, pollDelay = ms => new Promise(resolve => setTimeout(resolve, ms)), maxPolls = 20 }) {
  root.innerHTML = `<section class="report-workspace confluence-projects">
    <header class="report-page-head"><div><div class="eyebrow">Confluence · Project Facts</div><h1>Confluence Projects</h1><p>查看本地只读项目事实与 QA 责任信息。</p></div></header>
    <form class="card report-filter-card" data-preference-region><div class="report-filter-grid" data-main-facets></div>
      <details class="more-filter-panel"><summary>更多筛选</summary><div class="more-filter-options" data-more-facets></div></details>
      <div class="report-filter-grid"><label>Project / Person / Field Search<input class="form-control" name="search" type="search" placeholder="Project, person or Confluence field"></label>
      <div class="filter-actions"><button class="button button-primary" type="submit">Apply Filters</button><button class="button button-secondary" type="button" data-audit>Review Filters</button><button class="button button-secondary" type="button" data-reset data-preference-reset>Reset</button></div></div></form>
    <div class="report-state report-state-loading" role="status">Loading local project facts…</div><div class="inline-status" data-audit-status aria-live="polite"></div>
    <section class="confluence-summary" data-summary></section>
    <section class="card workload-card"><header class="report-preview-toolbar"><div><strong>Role workload</strong><div class="report-preview-meta">Project assignments per QA member</div></div><div class="role-segments" data-role-segments></div></header>
      <div class="workload-chart-scroll"><div class="workload-chart-surface"><canvas data-workload-chart></canvas></div></div></section>
    <section class="card report-preview"><header class="report-preview-toolbar"><strong>QA responsibility details</strong><span class="count-badge" data-count>0 projects</span></header>
      <div class="report-preview-body owner-cards" data-projects></div></section></section>`
  const form = root.querySelector('form')
  const facetRoot = root.querySelector('[data-main-facets]')
  const moreRoot = root.querySelector('[data-more-facets]')
  const status = root.querySelector('[role="status"]')
  const projectsRoot = root.querySelector('[data-projects]')
  const auditButton = root.querySelector('[data-audit]')
  let facets = []
  let cacheReady = false
  let destroyed = false
  let pollGeneration = 0
  let enabledMore = new Set()
  let workloadChart
  let activeRole = ''

  const currentFilters = () => {
    const fields = {}
    for (const facet of facets) {
      const control = form.elements[`field.${facet.key}`]
      const values = control ? selected(control) : []
      if (values.length) fields[facet.key] = values
    }
    return { fields, search: form.elements.search.value }
  }

  function setBusinessControlsEnabled(enabled) {
    cacheReady = enabled
    auditButton.disabled = !enabled
    form.querySelector('[type="submit"]').disabled = !enabled
    form.querySelector('[data-reset]').disabled = !enabled
    form.elements.search.disabled = !enabled
    for (const control of form.querySelectorAll('select, [data-more-facets] input')) {
      control.disabled = !enabled
      control._multiSelect?.setDisabled(!enabled)
    }
  }

  function renderFacets(nextFacets, { loading = false } = {}) {
    const selected = currentFilters().fields
    facets = nextFacets ?? []
    facetRoot.replaceChildren()
    const byKey = new Map(facets.map(facet => [facet.key, facet]))
    for (const key of [...COMMON_FILTERS, ...enabledMore]) {
      const facet = byKey.get(key)
      if (!facet) continue
      const label = node('label', '', facet.labels?.length > 1 ? `${facet.label} (${facet.labels.join(' / ')})` : facet.label)
      const select = node('select', 'form-select'); select.name = `field.${facet.key}`; select.multiple = true
      fillSelect(select, facet.options ?? [])
      for (const option of select.options) option.selected = (selected[facet.key] ?? []).includes(option.value)
      label.append(select); facetRoot.append(label)
      enhanceMultiSelect(select, { emptyLabel: loading ? 'Loading…' : `All ${facet.label}`, compact: true, searchable: false })
    }
    moreRoot.replaceChildren()
    for (const facet of facets.filter(item => !COMMON_FILTERS.includes(item.key))) {
      const label = node('label', 'more-filter-option')
      const checkbox = node('input', 'form-check-input'); checkbox.type = 'checkbox'; checkbox.name = 'enabledMoreFilters'; checkbox.value = facet.key; checkbox.checked = enabledMore.has(facet.key)
      checkbox.addEventListener('change', () => {
        if (checkbox.checked) enabledMore.add(facet.key); else enabledMore.delete(facet.key)
        renderFacets(facets)
      })
      label.append(checkbox, document.createTextNode(facet.label)); moreRoot.append(label)
    }
    setBusinessControlsEnabled(cacheReady && !loading)
  }

  function updateFacetOptions(nextFacets) {
    const invalid = []
    facets = nextFacets ?? facets
    for (const facet of facets) {
      const select = form.elements[`field.${facet.key}`]
      if (!select) continue
      const selectedValues = selected(select)
      const validValues = new Set((facet.options ?? []).map(option => String(option?.value ?? option)))
      fillSelect(select, facet.options ?? [])
      for (const option of select.options) option.selected = selectedValues.includes(option.value)
      if (selectedValues.some(value => !validValues.has(value))) invalid.push(facet.label)
      select._multiSelect?.syncFromSelect()
    }
    if (invalid.length) root.querySelector('[data-audit-status]').textContent = `已清除失效筛选：${invalid.join('、')}`
  }

  function projectKey(project) { return project.identity || `${project.space_key || ''}:${project.project_id || ''}` }

  function readableName(person) {
    const name = String(person?.name ?? '').trim()
    const identity = String(person?.identity ?? '').trim()
    return !name || (identity && name.toLocaleLowerCase() === identity.toLocaleLowerCase()) ? 'Unknown member' : name
  }

  function toggleButton(className, label, panel, expanded = true) {
    const button = node('button', className)
    button.type = 'button'; button.setAttribute('aria-expanded', String(expanded)); button.setAttribute('aria-label', label)
    button.append(node('span', 'accordion-icon', expanded ? '−' : '+'))
    panel.hidden = !expanded
    button.addEventListener('click', () => {
      const next = button.getAttribute('aria-expanded') !== 'true'
      button.setAttribute('aria-expanded', String(next)); button.querySelector('.accordion-icon').textContent = next ? '−' : '+'; panel.hidden = !next
    })
    return button
  }

  function renderSummary(hierarchy, projects) {
    const people = new Set(); let assignments = 0
    for (const role of hierarchy) for (const person of role.people ?? []) {
      people.add(person.identity || readableName(person)); assignments += person.projects?.length ?? 0
    }
    const values = [projects.length, people.size, new Set(projects.map(project => project.space_key).filter(Boolean)).size,
      people.size ? (assignments / people.size).toFixed(1) : '0.0']
    const labels = ['Matched projects', 'Unique QA people', 'Product lines', 'Avg assignments / person']
    const summary = root.querySelector('[data-summary]'); summary.replaceChildren()
    labels.forEach((label, index) => { const card = node('article', 'card summary-metric'); card.dataset.metric = ''; card.append(node('span', '', label), node('strong', '', values[index])); summary.append(card) })
    const definition = node('article', 'card summary-definition'); definition.append(node('strong', '', 'Metric definition'), node('p', '', 'Average assignments per person = role project assignments ÷ unique QA people in the filtered results.'))
    summary.append(definition)
  }

  function renderWorkload(hierarchy) {
    const roles = hierarchy.filter(role => role.people?.length)
    if (!roles.some(role => role.role === activeRole)) activeRole = roles[0]?.role ?? ''
    const segments = root.querySelector('[data-role-segments]'); segments.replaceChildren()
    for (const role of roles) {
      const button = node('button', `role-segment${role.role === activeRole ? ' active' : ''}`, role.role); button.type = 'button'
      button.setAttribute('aria-pressed', String(role.role === activeRole))
      button.addEventListener('click', () => { activeRole = role.role; renderWorkload(hierarchy) }); segments.append(button)
    }
    workloadChart?.destroy(); workloadChart = null
    const role = roles.find(item => item.role === activeRole)
    const surface = root.querySelector('.workload-chart-surface')
    surface.style.height = `${Math.max(240, (role?.people?.length ?? 0) * 36)}px`
    if (!role || !chartFactory) return
    const rows = role.people.map(person => ({ name: readableName(person), count: person.projects?.length ?? 0 }))
      .sort((left, right) => right.count - left.count || left.name.localeCompare(right.name))
    workloadChart = chartFactory(root.querySelector('[data-workload-chart]'), {
      type: 'bar', data: { labels: rows.map(row => row.name), datasets: [{ label: 'Projects', data: rows.map(row => row.count) }] },
      options: { indexAxis: 'y', responsive: true, maintainAspectRatio: false, scales: { x: { beginAtZero: true, ticks: { precision: 0 } } }, plugins: { legend: { display: false } } }
    })
  }

  function renderProjects(hierarchy, projectCount = 0, projects = []) {
    projectsRoot.replaceChildren()
    root.querySelector('[data-count]').textContent = `${projectCount} projects`
    renderSummary(hierarchy ?? [], projects)
    renderWorkload(hierarchy ?? [])
    if (!projectCount) { projectsRoot.append(node('div', 'report-empty', 'No matching projects.')); return }
    const represented = new Set()
    for (const role of hierarchy ?? []) {
      const roleNode = node('article', 'owner-role')
      const roleBody = node('div', 'owner-role-body')
      const assignments = (role.people ?? []).reduce((sum, person) => sum + (person.projects?.length ?? 0), 0)
      const roleHeader = node('header', 'owner-card-header'); roleHeader.append(node('div', 'owner-card-title', role.role), node('span', 'owner-card-meta', `${role.people?.length ?? 0} people · ${assignments} assignments`), toggleButton('owner-role-toggle', `Toggle ${role.role}`, roleBody))
      roleNode.append(roleHeader, roleBody)
      if (!role.people?.length) roleBody.append(node('div', 'report-empty compact', 'No assigned people.'))
      for (const person of role.people ?? []) {
        const personNode = node('section', 'owner-person'); const projectList = node('div', 'owner-project-list')
        const tags = [...new Set((person.projects ?? []).map(project => project.space_key).filter(Boolean))]
        const personHeader = node('header', 'owner-person-header'); personHeader.append(node('strong', '', readableName(person)), node('span', 'owner-card-meta', `${person.projects?.length ?? 0} projects`))
        const tagRoot = node('span', 'owner-space-tags'); tags.forEach(tag => tagRoot.append(node('span', 'owner-space-tag', tag))); personHeader.append(tagRoot, toggleButton('owner-person-toggle', `Toggle projects for ${readableName(person)}`, projectList, false))
        personNode.append(personHeader, projectList)
        for (const project of person.projects ?? []) {
          represented.add(projectKey(project)); projectList.append(node('div', 'owner-project-row', `${project.name || project.project_id} · ${project.space_key || '—'} · ${project.status || '—'}`))
        }
        roleBody.append(personNode)
      }
      projectsRoot.append(roleNode)
    }
    const unavailable = projects.filter(project => project.responsibility_unavailable && !represented.has(projectKey(project)))
    if (unavailable.length) {
      const unavailableNode = node('article', 'owner-role responsibility-unavailable')
      unavailableNode.append(node('header', 'owner-card-header', `Responsibility unavailable (${unavailable.length})`))
      for (const project of unavailable) unavailableNode.append(node('div', 'owner-project-row', `${project.name || project.project_id} · ${project.space_key || '—'}`))
      projectsRoot.append(unavailableNode)
    }
  }

  function present(payload, { updateHierarchy = true, updateFacets = true } = {}) {
    const hasCache = Boolean(payload.snapshotTime) && ['ready', 'partial_success'].includes(payload.state)
    cacheReady = hasCache
    if (!facets.length) renderFacets(payload.facets, { loading: payload.state === 'loading' || !hasCache })
    else if (updateFacets) updateFacetOptions(payload.facets)
    if (updateHierarchy) renderProjects(payload.ownerHierarchy ?? [], payload.projects?.length ?? 0, payload.projects ?? [])
    status.className = `report-state report-state-${payload.state}`
    status.textContent = `${STATE_COPY[payload.state] ?? ''}${payload.snapshotTime ? ` Snapshot: ${payload.snapshotTime}` : ''}`.trim()
    status.hidden = payload.state === 'ready' && !payload.snapshotTime
    if (payload.detailState === 'reauthentication_required') {
      root.querySelector('[data-audit-status]').textContent = 'Please verify your account again before loading responsibility details.'
    }
    setBusinessControlsEnabled(hasCache)
  }

  async function poll(generation, filters, remaining) {
    if (remaining <= 0) {
      status.className = 'report-state report-state-failed'; status.textContent = 'Project facts refresh timed out.'
      return
    }
    await pollDelay(500)
    if (destroyed || generation !== pollGeneration || !root.isConnected) return
    try {
      const payload = await api.getProjectFacts(filters)
      if (destroyed || generation !== pollGeneration || !root.isConnected) return
      present(payload)
      if (payload.state === 'loading') poll(generation, filters, remaining - 1)
    } catch {
      status.className = 'report-state report-state-schema_error'; status.textContent = 'Local project facts API is unavailable.'
      setBusinessControlsEnabled(false)
    }
  }

  async function load({ updateHierarchy = true, updateFacets = true, details = false } = {}) {
    const generation = ++pollGeneration
    if (!details) {
      setBusinessControlsEnabled(false)
      status.className = 'report-state report-state-loading'; status.hidden = false; status.textContent = STATE_COPY.loading
    }
    try {
      const payload = await api.getProjectFacts(currentFilters(), { details })
      if (destroyed || generation !== pollGeneration) return
      present(payload, { updateHierarchy, updateFacets })
      if (payload.state === 'loading') poll(generation, currentFilters(), maxPolls)
    } catch {
      status.className = 'report-state report-state-schema_error'; status.textContent = 'Local project facts API is unavailable.'
      renderProjects([], 0)
      setBusinessControlsEnabled(false)
    }
  }
  form.addEventListener('submit', event => { event.preventDefault(); load({ updateHierarchy: true, updateFacets: false, details: true }) })
  form.addEventListener('preference:restored', event => {
    if (event.target.name !== 'enabledMoreFilters') return
    const restored = event.detail.value
    const next = new Set(Array.isArray(restored) ? restored : [])
    if ([...next].some(key => !enabledMore.has(key)) || [...enabledMore].some(key => !next.has(key))) {
      enabledMore = next; renderFacets(facets)
    }
  })
  root.querySelector('[data-reset]').addEventListener('click', () => {
    form.reset()
    for (const select of form.querySelectorAll('select')) select._multiSelect?.syncFromSelect()
    load({ updateHierarchy: true, updateFacets: false })
  })
  auditButton.addEventListener('click', () => {
    root.querySelector('[data-audit-status]').textContent = 'Client runtime credential is required. Start the Confluence audit in SmartTest Client.'
  })
  return { start: load, destroy() { destroyed = true; pollGeneration += 1; workloadChart?.destroy() } }
}
import { enhanceMultiSelect, fillSelect, selected } from './app.js'
