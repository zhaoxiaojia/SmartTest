const STATE_COPY = {
  loading: 'Loading project catalog…',
  ready: '',
  no_snapshot: 'No local project snapshot is available.',
  schema_error: 'Local project snapshot is unreadable.',
  partial_success: 'Some project facts are stale or failed.',
  failed: 'Project catalog load failed.',
  reauthentication_required: 'Please verify your account again before refreshing project data.'
}
const COMMON_FILTERS = [
  '__product_space__', 'date of commercial approval', 'project id',
  'project status', 'current stage', 'project owner', 'support mode'
]
import { createAsyncFeedback } from './async-feedback.js'
import { createDownloadButton } from './download-button.js'

function node(tag, className, text) {
  const item = document.createElement(tag)
  if (className) item.className = className
  if (text != null) item.textContent = text
  return item
}

export function createProjects({ root, api, chartFactory, waitForPreferences, account,
  pollDelay = ms => new Promise(resolve => setTimeout(resolve, ms)), downloadNavigate }) {
  const displayKey = account ? `smarttest:projects-display:${encodeURIComponent(String(account).trim().toLocaleLowerCase())}` : ''
  const readDisplay = () => {
    if (!displayKey) return null
    try { return JSON.parse(sessionStorage.getItem(displayKey)) } catch { return null }
  }
  const saveDisplay = payload => {
    if (!displayKey || !['ready', 'partial_success'].includes(payload?.state)) return
    try { sessionStorage.setItem(displayKey, JSON.stringify(payload)) } catch { /* optional display acceleration */ }
  }
  root.innerHTML = `<section class="report-workspace projects-workspace">
    <header class="report-page-head"><div><div class="eyebrow">Projects · Current Facts</div><h1>Projects</h1><p>查看本地只读项目事实与 QA 责任信息。</p></div></header>
    <form class="card report-filter-card" data-preference-region><div class="report-state report-state-loading" role="status">Loading project catalog…</div><div class="report-filter-grid" data-main-facets></div>
      <details class="more-filter-panel"><summary>更多筛选</summary><div class="more-filter-options" data-more-facets></div></details>
      <div class="report-filter-grid"><label>Project / Person / Field Search<input class="form-control" name="search" type="search" placeholder="Project, person or field"></label>
      <div class="filter-actions"><button class="button button-primary" type="submit">Apply Filters</button><button class="button button-secondary" type="button" data-cancel hidden>Cancel Sync</button><button class="button button-secondary" type="button" data-reset data-preference-reset>Reset</button></div></div>
      <section class="weekly-review"><strong class="weekly-review-title">Weekly Review</strong><div class="weekly-review-controls"><label>Start<input class="form-control" name="reviewStartDate" type="date"></label><label>End<input class="form-control" name="reviewEndDate" type="date"></label>
        <button class="button button-secondary" type="button" data-audit>Review Filters</button><button class="button button-secondary" type="button" data-audit-cancel disabled>Cancel Review</button><button class="button button-primary" type="button" data-audit-download disabled>Download</button></div></section></form>
    <div class="async-feedback" data-async-feedback></div><div class="inline-status" data-audit-status aria-live="polite"></div>
    <section class="projects-summary" data-summary></section>
    <section class="card workload-card"><header class="report-preview-toolbar"><div><strong>Role workload</strong><div class="report-preview-meta">Project assignments per QA member</div></div><div class="role-segments" data-role-segments></div></header>
      <div class="workload-chart-scroll"><div class="workload-chart-surface"><canvas data-workload-chart></canvas></div></div></section>
    <section class="card report-preview"><header class="report-preview-toolbar"><strong>Projects by Product Space</strong><span class="count-badge" data-count>0 projects</span></header>
      <div class="report-preview-body product-space-groups" data-projects></div></section></section>`
  const form = root.querySelector('form')
  const facetRoot = root.querySelector('[data-main-facets]')
  const moreRoot = root.querySelector('[data-more-facets]')
  const status = root.querySelector('[role="status"]')
  const projectsRoot = root.querySelector('[data-projects]')
  const auditButton = root.querySelector('[data-audit]')
  const cancelButton = root.querySelector('[data-cancel]')
  const auditCancelButton = root.querySelector('[data-audit-cancel]')
  const auditDownloadButton = root.querySelector('[data-audit-download]')
  let facets = []
  let cacheReady = false
  let destroyed = false
  let pollGeneration = 0
  let enabledMore = new Set()
  let workloadChart
  let activeRole = ''
  let activeSync = null
  let activeAuditId = ''
  let productSpaceDefinitions = []
  const feedback = createAsyncFeedback({ root: root.querySelector('[data-async-feedback]'),
    cancelButton, onCancel: cancelSync })
  const auditDownload = createDownloadButton({
    element: auditDownloadButton,
    prepare: async () => (await api.exportConfluenceAudit(activeAuditId)).download,
    navigate: downloadNavigate,
    artifactUrl: api.downloadUrl,
  })
  auditDownload.element.disabled = true

  function setDefaultReviewPeriod() {
    const now = new Date(Date.now() + 8 * 60 * 60 * 1000)
    const day = now.getUTCDay() || 7
    const monday = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() - day + 1))
    const previous = new Date(monday.getTime() - 7 * 24 * 60 * 60 * 1000)
    form.elements.reviewStartDate.value = previous.toISOString().slice(0, 10)
    form.elements.reviewEndDate.value = monday.toISOString().slice(0, 10)
  }
  setDefaultReviewPeriod()

  function taskState(value) {
    return ({ running: 'running', queued: 'running', completed: 'success',
      failed: 'failed', cancelled: 'cancelled' }[value] ?? 'idle')
  }

  function childMessage(message, task) {
    const child = task?.visibleChild
    return child ? `${message} · ${child.label}` : message
  }

  function updateFeedback(sync) {
    const task = sync?.task
    if (sync?.state === 'loading') feedback.update({ state: task ? taskState(task.state) : 'running',
      message: childMessage('Syncing project details…', task),
      processed: task?.progress?.processed ?? sync.completed, total: task?.progress?.total ?? sync.total })
    else if (sync?.state === 'failed') feedback.update({ state: 'failed', message: 'Project detail sync failed.' })
    else if (sync?.state === 'cancelled') feedback.update({ state: 'cancelled' })
    else if (sync?.state === 'ready' && feedback.state === 'running') feedback.update({ state: 'success' })
  }

  function updateAuditFeedback(audit) {
    const task = audit?.task
    const running = ['queued', 'running'].includes(audit?.status)
    const state = task ? taskState(task.state) : (running ? 'running' : ({
      completed: 'success', failed: 'failed', cancelled: 'cancelled'
    }[audit?.status] ?? 'idle'))
    const stage = childMessage('', task) || audit?.stage
    feedback.update({ state, stage, processed: task?.progress?.processed ?? audit?.progress?.processed,
      total: task?.progress?.total ?? audit?.progress?.total })
  }

  const currentFilters = () => {
    const fields = {}
    for (const facet of facets) {
      const control = form.elements[`field.${facet.key}`]
      const values = control ? selected(control) : []
      if (values.length) fields[facet.key] = values
    }
    return { fields, search: form.elements.search.value }
  }

  const contextToken = filters => JSON.stringify({
    fields: Object.fromEntries(Object.entries(filters.fields ?? {}).sort(([a], [b]) => a.localeCompare(b))
      .map(([key, values]) => [key, [...values].map(value => String(value).trim()).filter(Boolean).sort()])),
    search: String(filters.search ?? '').trim()
  })

  function setBusinessControlsEnabled(enabled, { applyEnabled = enabled } = {}) {
    cacheReady = cacheReady || applyEnabled
    auditButton.disabled = !applyEnabled
    form.querySelector('[type="submit"]').disabled = !applyEnabled
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
      select.dataset.readyLabel = `All ${facet.label}`
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
    setBusinessControlsEnabled(cacheReady || (loading && facets.some(facet => facet.options?.length)),
      { applyEnabled: cacheReady })
  }

  function updateFacetOptions(nextFacets) {
    const invalid = []
    facets = nextFacets ?? facets
    for (const select of form.querySelectorAll('select[name^="field."]')) {
      select._multiSelect?.setEmptyLabel(select.dataset.readyLabel)
    }
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

  function renderSummary(hierarchy, projects, accessibleProjectCount) {
    const people = new Set(); let assignments = 0
    for (const role of hierarchy) for (const person of role.people ?? []) {
      people.add(person.identity || readableName(person)); assignments += person.projects?.length ?? 0
    }
    const values = [accessibleProjectCount ?? projects.length, projects.length, people.size,
      new Set(projects.map(project => project.space_key).filter(Boolean)).size,
      people.size ? (assignments / people.size).toFixed(1) : '0.0']
    const labels = ['Accessible projects', 'Matched projects', 'Unique QA people', 'Product lines', 'Avg assignments / person']
    const summary = root.querySelector('[data-summary]'); summary.replaceChildren()
    labels.forEach((label, index) => { const card = node('article', 'card summary-metric'); card.dataset.metric = ''; card.append(node('span', '', label), node('strong', '', values[index])); summary.append(card) })
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

  function renderProjects(hierarchy, projects = [], accessibleProjectCount) {
    projectsRoot.replaceChildren()
    const seenProjects = new Set()
    const uniqueProjects = projects.filter(project => {
      const key = projectKey(project)
      if (seenProjects.has(key)) return false
      seenProjects.add(key)
      return true
    })
    root.querySelector('[data-count]').textContent = `${uniqueProjects.length} projects`
    renderSummary(hierarchy ?? [], uniqueProjects, accessibleProjectCount)
    renderWorkload(hierarchy ?? [])
    const projectStage = project => String(project.stage || project.fields?.['current stage'] || '').trim()
    const productSpaceLabels = new Map(productSpaceDefinitions.map(option => [
      String(option?.value ?? option).trim(),
      typeof option === 'object' ? String(option?.label ?? '').trim() : '',
    ]))

    const displayValue = value => Array.isArray(value) ? value.filter(item => item != null && String(item).trim()).join(', ') : String(value ?? '').trim()
    const projectDisplayName = project => String(project.name || project.project_id || '').trim()
      .replace(/^\d+\.\*?\s*/, '').replace(/\s*-\s*Project Status Report\s*$/i, '').trim()
    const coreFields = new Set(['__product_space__', 'project id', 'project status', 'current stage', 'support mode'])
    const addFact = (rootNode, label, value) => {
      const text = displayValue(value)
      if (!text) return
      const row = node('div', 'project-card-fact')
      row.append(node('span', 'project-card-label', label), node('span', 'project-card-value', text))
      rootNode.append(row)
    }
    const createProjectCard = (project, productSpaceLabel) => {
      const card = node('article', 'kanban-card project-card')
      card.dataset.projectId = projectKey(project)
      const summary = node('div', 'project-card-summary')
      const heading = node('div', 'kanban-card-title', projectDisplayName(project))
      const identifier = node('div', 'kanban-card-desc', project.project_id)
      const badges = node('div', 'project-card-badges')
      for (const value of [productSpaceLabel, project.status, projectStage(project) || 'Unspecified', project.support_mode]) {
        if (value) badges.append(node('span', 'badge badge-blue', value))
      }
      const facts = node('div', 'project-card-details project-card-facts')
      addFact(facts, 'Customer', project.customer_summary)
      for (const [role, people] of Object.entries(project.roles ?? {})) {
        addFact(facts, role, (people ?? []).map(readableName))
      }
      for (const [label, value] of Object.entries(project.fields ?? {})) {
        if (!coreFields.has(label.toLocaleLowerCase())) addFact(facts, label, value)
      }
      summary.append(heading, identifier, badges)
      card.append(summary)
      if (facts.childElementCount) card.append(facts)
      return card
    }

    const groupByMajorFaeQa = projects => {
      const groups = new Map()
      for (const project of projects) {
        const people = (project.roles?.['Major FAE QA'] ?? []).filter(person => readableName(person))
        for (const person of people.length ? people : [{ identity: '__unassigned__', name: 'Unassigned' }]) {
          const name = readableName(person)
          const key = person.identity || name
          if (!groups.has(key)) groups.set(key, { name, projects: [] })
          groups.get(key).projects.push(project)
        }
      }
      return [...groups.values()].sort((left, right) => right.projects.length - left.projects.length)
    }

    for (const { value: productSpaceKey, label: productSpaceLabel } of productSpaceDefinitions) {
      const spaceProjects = uniqueProjects.filter(project => project.space_key === productSpaceKey)
      const group = node('details', 'product-space-group'); group.dataset.productSpaceGroup = ''; group.open = true
      const summary = node('summary', 'product-space-summary')
      const count = node('span', 'kanban-count', spaceProjects.length); count.dataset.productCount = ''
      summary.append(node('strong', 'kanban-title', productSpaceLabel), count)
      const qaGroups = node('div', 'major-fae-qa-groups'); qaGroups.dataset.productGrid = ''
      if (spaceProjects.length) {
        for (const qa of groupByMajorFaeQa(spaceProjects)) {
          const qaGroup = node('details', 'major-fae-qa-group'); qaGroup.dataset.majorFaeQaGroup = ''
          const qaSummary = node('summary', 'major-fae-qa-summary')
          const qaCount = node('span', 'kanban-count', qa.projects.length); qaCount.dataset.qaProjectCount = ''
          qaSummary.append(node('strong', '', qa.name), qaCount)
          const cards = node('div', 'product-card-grid')
          qa.projects.forEach(project => cards.append(createProjectCard(project, productSpaceLabels.get(productSpaceKey))))
          qaGroup.append(qaSummary, cards); qaGroups.append(qaGroup)
        }
      } else qaGroups.append(node('div', 'product-space-empty', 'No projects.'))
      group.append(summary, qaGroups); projectsRoot.append(group)
    }
  }

  function present(payload, {
    updateHierarchy = true, updateFacets = true, detailRequested = false,
  } = {}) {
    const hasCache = ['ready', 'partial_success'].includes(payload.state)
    const hasDetailJob = detailRequested || Boolean(activeSync)
    const syncing = hasDetailJob && payload.sync?.state === 'loading'
    if (hasDetailJob) updateFeedback(payload.sync)
    if (payload.productSpaces) productSpaceDefinitions = payload.productSpaces
    cacheReady = hasCache
    if (!facets.length) renderFacets(payload.facets, { loading: payload.state === 'loading' || !hasCache })
    else if (updateFacets && hasCache) updateFacetOptions(payload.facets)
    if (updateHierarchy) {
      renderProjects(payload.ownerHierarchy ?? [], payload.projects ?? [], payload.accessibleProjectCount)
    }
    status.className = `report-state report-state-${payload.state}`
    status.textContent = STATE_COPY[payload.state] ?? ''
    status.hidden = payload.state === 'ready'
    if (payload.detailState === 'reauthentication_required') {
      root.querySelector('[data-audit-status]').textContent = 'Please verify your account again before loading responsibility details.'
    }
    setBusinessControlsEnabled(hasCache, { applyEnabled: hasCache && !syncing })
    auditButton.disabled = !hasCache || syncing
    saveDisplay(payload)
  }

  async function poll(generation) {
    await pollDelay(500)
    if (destroyed || generation !== pollGeneration || !root.isConnected) return
    try {
      const sync = await api.getProjectFactsStatus()
      if (destroyed || generation !== pollGeneration || !root.isConnected) return
      if (sync.state === 'loading') {
        if (activeSync) updateFeedback(sync)
        poll(generation)
      }
      else {
        const filters = activeSync?.filters ?? currentFilters()
        const payload = await api.getProjectFacts(filters, { details: false })
        if (destroyed || generation !== pollGeneration || !root.isConnected) return
        const contextUnchanged = !activeSync || contextToken(currentFilters()) === activeSync.token
        if (!activeSync || contextUnchanged) present(payload)
        updateFeedback(sync)
        activeSync = null
        setBusinessControlsEnabled(cacheReady, { applyEnabled: cacheReady })
      }
    } catch {
      if (destroyed || generation !== pollGeneration) return
      if (activeSync) feedback.update({ state: 'failed', message: 'Project detail sync failed.' })
      status.className = 'report-state report-state-schema_error'; status.textContent = 'Local project facts API is unavailable.'
      setBusinessControlsEnabled(false)
    }
  }

  async function load({ updateHierarchy = true, updateFacets = true, details = false,
    snapshot = false, reset = false,
    beginPolling = true } = {}) {
    const generation = ++pollGeneration
    const requestedFilters = currentFilters()
    if (!details && !cacheReady) {
      setBusinessControlsEnabled(false)
      status.className = 'report-state report-state-loading'; status.hidden = false; status.textContent = STATE_COPY.loading
    }
    try {
      const options = { details,
        ...(snapshot ? { snapshot: true } : {}), ...(reset ? { reset: true } : {}) }
      const payload = await api.getProjectFacts(requestedFilters, options)
      if (destroyed || generation !== pollGeneration) return
      present(payload, { updateHierarchy, updateFacets, detailRequested: details })
      if (details && payload.sync?.state === 'loading') {
        activeSync = { token: contextToken(requestedFilters), filters: requestedFilters }
      }
      if (beginPolling && (payload.state === 'loading' || payload.sync?.state === 'loading')) poll(generation)
      return payload
    } catch {
      if (destroyed || generation !== pollGeneration) return
      if (details || feedback.state === 'running') feedback.update({ state: 'failed', message: 'Project detail sync failed.' })
      status.className = 'report-state report-state-schema_error'; status.textContent = 'Local project facts API is unavailable.'
      if (!cacheReady) renderProjects([])
      setBusinessControlsEnabled(false)
    }
  }
  form.addEventListener('submit', event => {
    event.preventDefault()
    setBusinessControlsEnabled(cacheReady, { applyEnabled: false })
    load({ updateHierarchy: true, updateFacets: false, details: true })
  })
  form.addEventListener('preference:restored', event => {
    if (event.target.name !== 'enabledMoreFilters') return
    const restored = event.detail.value
    const next = new Set(Array.isArray(restored) ? restored : [])
    if ([...next].some(key => !enabledMore.has(key)) || [...enabledMore].some(key => !next.has(key))) {
      enabledMore = next; renderFacets(facets)
    }
  })
  root.querySelector('[data-reset]').addEventListener('click', () => {
    form.elements.search.value = ''
    for (const select of form.querySelectorAll('select[name^="field."]')) {
      for (const option of select.options) option.selected = false
      select._multiSelect?.syncFromSelect()
    }
    enabledMore.clear()
    renderFacets(facets)
    load({ reset: true })
  })
  auditButton.addEventListener('click', async () => {
    auditButton.disabled = true
    auditCancelButton.disabled = false
    auditDownload.element.disabled = true
    root.querySelector('[data-audit-status]').textContent = ''
    try {
      const created = await api.createConfluenceAudit({
        filters: currentFilters(),
        startDate: form.elements.reviewStartDate.value,
        endDate: form.elements.reviewEndDate.value,
      })
      if (destroyed) return
      activeAuditId = created.auditId
      let audit = created
      updateAuditFeedback(audit)
      while (['queued', 'running'].includes(audit.status)) {
        await pollDelay(500)
        if (destroyed) return
        audit = await api.getConfluenceAudit(activeAuditId)
        if (destroyed) return
        updateAuditFeedback(audit)
      }
      auditDownload.element.disabled = audit.status !== 'completed'
    } catch (error) {
      if (destroyed) return
      root.querySelector('[data-audit-status]').textContent = error?.status === 422 ? 'invalid review period' : 'audit unavailable'
      feedback.update({ state: 'failed' })
    } finally {
      if (!destroyed) { auditButton.disabled = false; auditCancelButton.disabled = true }
    }
  })
  auditCancelButton.addEventListener('click', async () => {
    await api.cancelConfluenceAudit(activeAuditId)
    auditCancelButton.disabled = true
  })
  async function cancelSync() {
    await api.cancelProjectSync()
    pollGeneration += 1
    activeSync = null
    cancelButton.hidden = true
    feedback.update({ state: 'cancelled' })
    setBusinessControlsEnabled(cacheReady, { applyEnabled: cacheReady })
  }
  async function start() {
    const previousDisplay = readDisplay()
    if (previousDisplay) present(previousDisplay)
    const loaded = await load({ snapshot: true })
    await waitForPreferences?.()
    if (destroyed) return
    return loaded
  }
  return {
    start,
    destroy() { destroyed = true; pollGeneration += 1; auditDownload.destroy(); workloadChart?.destroy() },
  }
}
import { enhanceMultiSelect, fillSelect, selected } from './wifi-database.js'
