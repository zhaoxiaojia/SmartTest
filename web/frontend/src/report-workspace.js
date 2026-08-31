const COPY = {
  jira: { eyebrow: 'Jira · Report Center', title: 'Jira Reports', subtitle: '筛选并查看 Client 端业务生成的 Jira 审查报告。', source: 'Jira' }
}

const STATE_COPY = {
  loading: 'Loading reports…', empty: 'No reports available.',
  unauthorized: 'You do not have permission to view these reports.',
  config_missing: 'Report source is not configured.',
  external_failure: 'Report source is unavailable.',
  partial_success: 'Some reports could not be loaded.'
}

function element(tag, className, text) {
  const node = document.createElement(tag)
  if (className) node.className = className
  if (text != null) node.textContent = text
  return node
}

function setState(status, state) {
  status.className = `report-state report-state-${state}`
  status.textContent = STATE_COPY[state] ?? ''
  status.hidden = state === 'ready'
}

function formatDate(value) {
  if (!value) return 'Unknown time'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN', { hour12: false })
}

export function createReportWorkspace({ root, source, api }) {
  const copy = COPY[source]
  const filters = `<div class="report-filter-grid report-filter-grid-jira">
        <label class="report-jql-field">JQL<textarea class="form-control" name="jql" rows="3" placeholder="Paste the JQL used by the Client audit."></textarea>
          <span>只读查找 Client 已生成的报告；新审查仍在 Client 中执行。</span></label>
        <button class="button button-primary" type="submit">Find Generated Reports</button></div>`
  root.innerHTML = `<section class="report-workspace">
    <header class="report-page-head"><div><div class="eyebrow"></div><h1></h1><p></p></div>
      <div class="report-actions"><button class="button button-secondary" type="button" data-refresh>↻ 更新报告</button><a class="button button-primary is-disabled" data-download>⇩ Download</a></div></header>
    <form class="card report-filter-card" data-preference-region>${filters}</form>
    <div class="report-state report-state-loading" role="status">Loading reports…</div>
    <div class="report-master-detail">
      <aside class="card report-directory"><header><strong>Reports</strong><span class="count-badge" data-count>0 reports</span></header><div class="report-directory-list"></div></aside>
      <section class="card report-preview"><div class="report-preview-toolbar"><div><strong data-preview-title>Select a report</strong><div class="report-preview-meta" data-preview-meta></div></div><div class="report-actions"><a class="button button-secondary is-disabled" data-source-link target="_blank" rel="noopener">Open in ${copy.source} ↗</a><a class="button button-primary is-disabled" data-preview-download>⇩ Download</a></div></div><article class="report-preview-body"><div class="report-empty">Select a report to view its full content.</div></article></section>
    </div></section>`
  root.querySelector('.eyebrow').textContent = copy.eyebrow
  root.querySelector('h1').textContent = copy.title
  root.querySelector('.report-page-head p').textContent = copy.subtitle
  const form = root.querySelector('form')
  const status = root.querySelector('[role="status"]')
  const directory = root.querySelector('.report-directory-list')
  const body = root.querySelector('.report-preview-body')
  const title = root.querySelector('[data-preview-title]')
  const meta = root.querySelector('[data-preview-meta]')
  const downloads = root.querySelectorAll('[data-download], [data-preview-download]')
  const sourceLink = root.querySelector('[data-source-link]')
  let selectedId = ''

  function setLinks(report) {
    for (const link of downloads) {
      link.href = report ? api.downloadUrl(source, report.id) : ''
      link.classList.toggle('is-disabled', !report)
    }
    sourceLink.href = report?.sourceUrl || ''
    sourceLink.classList.toggle('is-disabled', !report?.sourceUrl)
  }

  function renderDetail(report) {
    title.textContent = report.title
    meta.textContent = `Generated ${formatDate(report.generatedAt)} · Source: ${copy.source}${report.productLine ? ` / ${report.productLine}` : ''}`
    setLinks(report)
    body.replaceChildren()
    const metrics = element('div', 'report-summary')
    const definitions = [['Total', report.summary?.total], ['Passed', report.summary?.passed], ['Attention', report.summary?.attention], ['Failed', report.summary?.failed]]
    for (const [label, value] of definitions) {
      const card = element('div', 'report-metric'); card.append(element('span', '', label), element('strong', '', value ?? '—')); metrics.append(card)
    }
    body.append(metrics)
    for (const section of report.sections ?? []) {
      const wrapper = element('section', 'report-section'); wrapper.append(element('h2', '', section.title))
      const scroll = element('div', 'report-table-scroll'); const table = element('table', 'report-preview-table')
      const head = element('thead'); const headRow = element('tr')
      for (const header of section.headers ?? []) headRow.append(element('th', '', header ?? ''))
      head.append(headRow); table.append(head)
      const tableBody = element('tbody')
      for (const row of section.rows ?? []) { const tr = element('tr'); for (const value of row) tr.append(element('td', '', value ?? '')); tableBody.append(tr) }
      table.append(tableBody); scroll.append(table); wrapper.append(scroll); body.append(wrapper)
    }
  }

  async function select(report, item) {
    selectedId = report.id
    directory.querySelectorAll('.report-directory-item').forEach(row => row.classList.toggle('active', row === item))
    body.replaceChildren(element('div', 'report-empty', 'Loading report…'))
    try { renderDetail(await api.getReport(source, report.id)) } catch (error) {
      const state = error?.status === 401 || error?.status === 403 ? 'unauthorized' : 'external_failure'
      setState(status, state); body.replaceChildren(element('div', 'report-empty', STATE_COPY[state]))
    }
  }

  async function load() {
    const filters = Object.fromEntries(new FormData(form))
    setState(status, 'loading'); directory.replaceChildren(); setLinks(null)
    title.textContent = STATE_COPY.loading; meta.textContent = ''
    body.replaceChildren(element('div', 'report-empty', STATE_COPY.loading))
    let payload
    try { payload = await api.listReports(source, filters) } catch (error) {
      setState(status, error?.status === 401 || error?.status === 403 ? 'unauthorized' : 'external_failure'); return
    }
    setState(status, payload.state)
    root.querySelector('[data-count]').textContent = `${payload.reports?.length ?? 0} reports`
    for (const report of payload.reports ?? []) {
      const item = element('button', 'report-directory-item'); item.type = 'button'
      const row = element('span', 'report-directory-meta')
      row.append(element('span', '', formatDate(report.generatedAt)), element('span', `report-status-tag report-status-${report.status}`, report.status === 'attention' ? 'Attention' : 'Completed'))
      item.append(element('strong', '', report.title), row)
      item.addEventListener('click', () => select(report, item)); directory.append(item)
    }
    const first = [...directory.children].find((_, index) => payload.reports[index]?.id === selectedId) ?? directory.firstElementChild
    if (first) await select(payload.reports[[...directory.children].indexOf(first)], first)
    else { title.textContent = 'No report selected'; meta.textContent = ''; body.replaceChildren(element('div', 'report-empty', STATE_COPY[payload.state] ?? STATE_COPY.empty)) }
  }
  form.addEventListener('submit', event => { event.preventDefault(); load() })
  root.querySelector('[data-refresh]').addEventListener('click', load)
  return { start: load }
}
