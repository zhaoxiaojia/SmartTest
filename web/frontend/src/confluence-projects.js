const STATE_COPY = {
  loading: 'Loading local project facts…',
  ready: '',
  no_snapshot: 'No local project snapshot is available.',
  schema_error: 'Local project snapshot is unreadable.',
  partial_success: 'Some project facts are stale or failed.',
  failed: 'Project facts refresh failed. Sign in and retry refresh.'
}
const COMMON_FILTERS = [
  '__product_space__', 'date of commercial approval', 'project id',
  'project status', 'current stage', 'project owner', 'support mode'
]
const MORE_FILTERS_KEY = 'smarttest-confluence-more-filters'

function node(tag, className, text) {
  const item = document.createElement(tag)
  if (className) item.className = className
  if (text != null) item.textContent = text
  return item
}

export function createConfluenceProjects({ root, api, pollDelay = ms => new Promise(resolve => setTimeout(resolve, ms)), maxPolls = 20 }) {
  root.innerHTML = `<section class="report-workspace confluence-projects">
    <header class="report-page-head"><div><div class="eyebrow">Confluence · Project Facts</div><h1>Confluence Projects</h1><p>查看本地只读项目事实与 QA 责任信息。</p></div>
      <div class="report-actions"><button class="button button-primary" type="button" data-audit>生成项目审查报告</button></div></header>
    <form class="card report-filter-card"><div class="report-filter-grid" data-main-facets></div>
      <details class="more-filter-panel"><summary>更多筛选</summary><div class="more-filter-options" data-more-facets></div></details>
      <div class="report-filter-grid"><label>Project / Person Search<input class="form-control" name="search" type="search" placeholder="Project, person or Confluence identity"></label>
      <div class="filter-actions"><button class="button button-primary" type="submit">Apply Filters</button><button class="button button-secondary" type="button" data-reset>Reset</button></div></div></form>
    <div class="report-state report-state-loading" role="status">Loading local project facts…</div><div class="inline-status" data-audit-status aria-live="polite"></div>
    <section class="card report-preview"><header class="report-preview-toolbar"><strong>Owner hierarchy</strong><span class="count-badge" data-count>0 projects</span></header>
      <div class="report-preview-body" data-projects></div></section></section>`
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
  try { enabledMore = new Set(JSON.parse(localStorage.getItem(MORE_FILTERS_KEY) || '[]')) } catch { enabledMore = new Set() }

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
      const checkbox = node('input', 'form-check-input'); checkbox.type = 'checkbox'; checkbox.value = facet.key; checkbox.checked = enabledMore.has(facet.key)
      checkbox.addEventListener('change', () => {
        if (checkbox.checked) enabledMore.add(facet.key); else enabledMore.delete(facet.key)
        localStorage.setItem(MORE_FILTERS_KEY, JSON.stringify([...enabledMore]))
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

  function renderProjects(hierarchy, projectCount = 0) {
    projectsRoot.replaceChildren()
    root.querySelector('[data-count]').textContent = `${projectCount} projects`
    if (!projectCount) { projectsRoot.append(node('div', 'report-empty', 'No matching projects.')); return }
    for (const role of hierarchy ?? []) {
      const roleNode = node('details', 'owner-role'); roleNode.open = true
      roleNode.append(node('summary', '', `${role.role} (${role.people?.length ?? 0})`))
      if (!role.people?.length) roleNode.append(node('div', 'report-empty', 'No assigned people.'))
      for (const person of role.people ?? []) {
        const personNode = node('details', 'owner-person'); personNode.open = true
        personNode.append(node('summary', '', `${person.name || person.identity} · ${person.identity || 'No stable identity'}`))
        for (const project of person.projects ?? []) {
          const projectNode = node('details', 'owner-project')
          projectNode.append(node('summary', '', `${project.name || project.project_id} · ${project.space_key || '—'} · ${project.status || '—'}`))
          const list = node('dl', 'project-basic-information')
          for (const [key, value] of Object.entries(project.fields ?? {})) {
            list.append(node('dt', '', key), node('dd', '', value || '—'))
          }
          projectNode.append(list); personNode.append(projectNode)
        }
        roleNode.append(personNode)
      }
      projectsRoot.append(roleNode)
    }
  }

  function present(payload, { updateHierarchy = true, updateFacets = true } = {}) {
    const hasCache = Boolean(payload.snapshotTime) && ['ready', 'partial_success'].includes(payload.state)
    cacheReady = hasCache
    if (!facets.length) renderFacets(payload.facets, { loading: payload.state === 'loading' || !hasCache })
    else if (updateFacets) updateFacetOptions(payload.facets)
    if (updateHierarchy) renderProjects(payload.ownerHierarchy ?? [], payload.projects?.length ?? 0)
    status.className = `report-state report-state-${payload.state}`
    status.textContent = `${STATE_COPY[payload.state] ?? ''}${payload.snapshotTime ? ` Snapshot: ${payload.snapshotTime}` : ''}`.trim()
    status.hidden = payload.state === 'ready' && !payload.snapshotTime
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

  async function load({ updateHierarchy = true, updateFacets = true } = {}) {
    const generation = ++pollGeneration
    setBusinessControlsEnabled(false)
    status.className = 'report-state report-state-loading'; status.hidden = false; status.textContent = STATE_COPY.loading
    try {
      const payload = await api.getProjectFacts(currentFilters())
      if (destroyed || generation !== pollGeneration) return
      present(payload, { updateHierarchy, updateFacets })
      if (payload.state === 'loading') poll(generation, currentFilters(), maxPolls)
    } catch {
      status.className = 'report-state report-state-schema_error'; status.textContent = 'Local project facts API is unavailable.'
      renderProjects([], 0)
      setBusinessControlsEnabled(false)
    }
  }
  form.addEventListener('submit', event => { event.preventDefault(); load({ updateHierarchy: true, updateFacets: false }) })
  root.querySelector('[data-reset]').addEventListener('click', () => {
    form.reset()
    for (const select of form.querySelectorAll('select')) select._multiSelect?.syncFromSelect()
    load({ updateHierarchy: true, updateFacets: false })
  })
  auditButton.addEventListener('click', () => {
    root.querySelector('[data-audit-status]').textContent = 'Client runtime credential is required. Start the Confluence audit in SmartTest Client.'
  })
  return { start: load, destroy() { destroyed = true; pollGeneration += 1 } }
}
import { enhanceMultiSelect, fillSelect, selected } from './app.js'
