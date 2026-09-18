const states = { queued: '等待执行', running: '执行中', completed: '已完成', partial: '部分完成', failed: '失败', historical_seed: '历史记录', historical_preview: '历史预览' }

export function createAuditEmailPage({ root, api, pollDelay = () => new Promise(resolve => setTimeout(resolve, 1000)) }) {
  let destroyed = false
  let generation = 0
  let offset = 0
  root.innerHTML = `<section class="page-stack">
    <section class="card"><h2>审查与报告</h2><p>发件人：fae-qa-auto@amlogic.com</p><p>立即触发与每周五北京时间 18:00 的 Windows 任务执行相同的本周周一到周五审查，并将 Jira 与 Confluence 邮件发送至 fae.qa@amlogic.com。</p>
    <button class="button button-primary" data-trigger>立即触发</button><p data-status role="status" aria-live="polite">加载执行历史…</p></section>
    <section class="card"><h2>执行历史</h2><p>每次执行独立保存；截图记录仅供历史对比。</p><div style="overflow-x:auto"><table class="report-table" style="width:100%"><thead><tr><th>时间</th><th>来源</th><th>结果</th><th>操作</th></tr></thead><tbody data-history></tbody></table></div><div class="filter-actions"><button class="button button-secondary" data-prev>较新记录</button><span data-count></span><button class="button button-secondary" data-next>更早记录</button></div></section>
    <section class="card" data-detail hidden><h2>报告详情</h2><div data-reports></div><label>运行信息（可选择复制）<textarea class="form-control" data-evidence readonly rows="8" style="width:100%"></textarea></label></section></section>`
  const status = root.querySelector('[data-status]')
  const trigger = root.querySelector('[data-trigger]')
  async function listing() {
    const result = await api.list(offset)
    if (destroyed) return
    const body = root.querySelector('[data-history]'); body.replaceChildren()
    for (const row of result.runs) {
      const tr = document.createElement('tr')
      const label = row.label.includes('T') ? new Date(row.label).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false }) : row.label
      for (const value of [label, { manual: '立即触发', scheduled: '每周任务', screenshot: '截图' }[row.source] || row.source, states[row.state] || row.state]) {
        const td = document.createElement('td'); td.textContent = value; tr.append(td)
      }
      const td = document.createElement('td'); const button = document.createElement('button')
      button.type = 'button'; button.className = 'button button-secondary'; button.textContent = '查看'; button.dataset.view = ''
      button.addEventListener('click', () => { const current = ++generation; void perform(async () => follow(await api.get(row.id), current)) })
      td.append(button); tr.append(td); body.append(tr)
    }
    root.querySelector('[data-count]').textContent = result.total ? `${offset + 1}–${offset + result.runs.length} / ${result.total}` : '暂无记录'
    root.querySelector('[data-prev]').disabled = offset === 0
    root.querySelector('[data-next]').disabled = offset + 4 >= result.total
  }
  function show(detail) {
    if (destroyed) return
    status.textContent = `${states[detail.state] || detail.state} · ${detail.id}`
    root.querySelector('[data-detail]').hidden = false
    root.querySelector('[data-evidence]').value = detail.evidence || ''
    const reports = root.querySelector('[data-reports]'); reports.replaceChildren()
    for (const [kind, title] of [['jira', 'Jira'], ['confluence', 'Confluence']]) {
      const heading = document.createElement('h3'); heading.textContent = `${title} 报告`; reports.append(heading)
      const report = detail.reports[kind]
      if (report?.html) {
        const frame = document.createElement('iframe'); frame.title = `${title} 报告预览`; frame.setAttribute('sandbox', '')
        frame.style.cssText = 'width:100%;height:490px;border:1px solid var(--border-color);background:white;margin-bottom:20px'
        frame.srcdoc = report.html; reports.append(frame)
      } else { const text = document.createElement('p'); text.textContent = report?.error || '此期没有可用报告。'; reports.append(text) }
      for (const name of report?.attachments || []) {
        const link = document.createElement('a'); link.textContent = name; link.className = 'button button-secondary'
        link.href = api.attachmentUrl(detail.id, kind, name); reports.append(link)
      }
    }
  }
  async function follow(detail, current) {
    while (!destroyed && current === generation) {
      show(detail)
      if (!['queued', 'running'].includes(detail.state)) { await listing(); return }
      await pollDelay()
      if (destroyed || current !== generation) return
      detail = await api.get(detail.id)
    }
  }
  async function perform(action) { try { await action() } catch (error) { if (!destroyed) status.textContent = error.message } }
  trigger.addEventListener('click', () => perform(async () => {
    trigger.disabled = true; status.textContent = '正在触发…'
    try { const detail = await api.trigger(); if (destroyed) return; offset = 0; await listing(); await follow(detail, ++generation) }
    finally { if (!destroyed) trigger.disabled = false }
  }))
  for (const [selector, delta] of [['[data-prev]', -4], ['[data-next]', 4]]) root.querySelector(selector).addEventListener('click', () => perform(async () => { offset += delta; await listing() }))
  return { async start() { await perform(async () => { await listing(); if (!destroyed) status.textContent = '可查看历史，或立即触发本周 Jira 与 Confluence 审查并发送邮件。' }) }, destroy() { destroyed = true; generation++; root.replaceChildren() } }
}
