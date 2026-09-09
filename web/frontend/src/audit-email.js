const states = { historical_seed: '截图历史', historical_preview: '历史预览', queued: '等待执行', running: '审查中', completed: '报告已生成', failed: '执行失败', partial: '部分完成' }
const eventStates = { pending: '等待到期', running: '执行中', completed: '已完成', partial: '部分完成', failed: '失败' }
const deliveryStates = { sending: '发送中', accepted: 'SMTP 已接受', failed: '发送失败', skipped: '未发送' }

export function createAuditEmailPage({ root, api, pollDelay = () => new Promise(resolve => setTimeout(resolve, 1000)) }) {
  let destroyed = false
  let offset = 0
  let generation = 0
  let eventTimer
  let eventPolling = false
  const knownEventStates = new Map()
  root.innerHTML = `<section class="report-workspace">
    <header class="report-page-head"><div><div class="eyebrow">Tools · Weekly Audit Email</div><h1>定期审查邮件</h1><p>逐次保存 Jira 与 Confluence 审查报告，查看最近四期对比。</p></div></header>
    <section class="card"><h2>审查与报告</h2><p>发件人：fae-qa-auto@amlogic.com</p><p>立即触发仅生成报告，供调试查看。</p>
    <button class="button button-primary" data-trigger>立即触发</button><p data-status role="status" aria-live="polite">加载执行历史…</p></section>
    <section class="card"><h2>每周定时任务</h2><p>按北京时间自动执行固定范围的 Jira 与 Confluence 审查，并发送两封报告邮件。</p>
    <form data-schedule-form class="filter-actions"><label>星期<select class="form-control" data-schedule-weekday><option value="0">星期一</option><option value="1">星期二</option><option value="2">星期三</option><option value="3">星期四</option><option value="4">星期五</option><option value="5">星期六</option><option value="6">星期日</option></select></label><label>时间（北京时间）<input class="form-control" type="time" data-schedule-time required></label><label><input type="checkbox" data-schedule-enabled checked> 启用</label><button class="button button-primary" type="submit" data-schedule-save>保存配置</button><button class="button button-secondary" type="button" data-schedule-delete>删除配置</button></form>
    <p data-schedule-status role="status" aria-live="polite">加载定时配置…</p><div data-schedule-latest></div></section>
    <section class="card"><h2>定制管理 · 一次性事件</h2><p>到期执行 Jira 与 Confluence 审查，将两封报告邮件及当期附件发送给 chao.li@amlogic.com、ping.xiong@amlogic.com。</p><p>时间按北京时间（UTC+8）计算。事件只执行一次。</p>
    <form data-event-form class="filter-actions"><label>未来日期时间（北京时间）<input class="form-control" type="datetime-local" data-event-time required></label><button class="button button-primary" data-event-create type="submit">创建一次性事件</button></form><p data-event-status role="status" aria-live="polite"></p>
    <div style="overflow-x:auto"><table class="report-table" style="width:100%"><thead><tr><th>北京时间</th><th>事件 / 状态</th><th>Jira 邮件</th><th>Confluence 邮件</th><th>报告</th></tr></thead><tbody data-events></tbody></table></div></section>
    <section class="card"><h2>执行历史</h2><p>每次执行独立保存；截图记录仅供历史对比。</p><div style="overflow-x:auto"><table class="report-table" style="width:100%"><thead><tr><th>时间</th><th>来源</th><th>结果</th><th>操作</th></tr></thead><tbody data-history></tbody></table></div><div class="filter-actions"><button class="button button-secondary" data-prev>较新记录</button><span data-count></span><button class="button button-secondary" data-next>更早记录</button></div></section>
    <section class="card" data-detail hidden><h2>报告详情</h2><div data-reports></div><label>运行信息（可选择复制）<textarea class="form-control" data-evidence readonly rows="8" style="width:100%"></textarea></label></section></section>`
  const status = root.querySelector('[data-status]')
  const trigger = root.querySelector('[data-trigger]')
  const scheduleWeekday = root.querySelector('[data-schedule-weekday]')
  const scheduleTime = root.querySelector('[data-schedule-time]')
  const scheduleEnabled = root.querySelector('[data-schedule-enabled]')
  const scheduleStatus = root.querySelector('[data-schedule-status]')
  scheduleWeekday.value = '4'; scheduleTime.value = '15:00'
  function showSchedule(schedule) {
    if (destroyed) return
    const latest = root.querySelector('[data-schedule-latest]'); latest.replaceChildren()
    if (!schedule) {
      scheduleWeekday.value = '4'; scheduleTime.value = '15:00'; scheduleEnabled.checked = true
      scheduleStatus.textContent = '尚未配置；默认值为每周五 15:00。'
      root.querySelector('[data-schedule-delete]').disabled = true
      return
    }
    scheduleWeekday.value = String(schedule.weekday); scheduleTime.value = schedule.time
    scheduleEnabled.checked = schedule.enabled
    scheduleStatus.textContent = schedule.enabled
      ? `已启用 · 下次执行：${new Date(schedule.nextRunAt).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false })}`
      : '已停用'
    root.querySelector('[data-schedule-delete]').disabled = false
    if (schedule.lastRunId) {
      const button = document.createElement('button'); button.type = 'button'; button.className = 'button button-secondary'
      button.dataset.scheduleView = ''; button.textContent = `最近结果：${eventStates[schedule.lastState] || states[schedule.lastState] || schedule.lastState}`
      button.addEventListener('click', () => { const current = ++generation; void perform(async () => follow(await api.get(schedule.lastRunId), current)) })
      latest.append(button)
    }
  }
  async function loadSchedule() {
    if (!api.getSchedule) { showSchedule(null); return }
    showSchedule((await api.getSchedule()).schedule)
  }
  async function listing() {
    const result = await api.list(offset)
    if (destroyed) return
    const body = root.querySelector('[data-history]')
    body.replaceChildren()
    for (const row of result.runs) {
      const tr = document.createElement('tr')
      const label = row.label.includes('T') ? new Date(row.label).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false }) : row.label
      for (const value of [label, { manual: '手动', one_time: '一次性事件', weekly: '每周任务', screenshot: '截图' }[row.source] || row.source, states[row.state] || row.state]) {
        const td = document.createElement('td'); td.textContent = value; tr.append(td)
      }
      const td = document.createElement('td'); const button = document.createElement('button')
      button.type = 'button'; button.className = 'button button-secondary'; button.textContent = '查看'; button.dataset.view = ''
      button.addEventListener('click', () => {
        const current = ++generation
        void perform(async () => follow(await api.get(row.id), current))
      })
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
      } else {
        const text = document.createElement('p'); text.textContent = report?.error || '此期没有可用报告。'; reports.append(text)
      }
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
  async function perform(action) {
    try { await action() } catch (error) { if (!destroyed) status.textContent = error.message }
  }
  async function events() {
    clearTimeout(eventTimer)
    let result
    try { result = await api.listEvents() } catch (error) {
      if (!destroyed && eventPolling) eventTimer = setTimeout(() => { void perform(events) }, 1000)
      throw error
    }
    if (destroyed) return
    const body = root.querySelector('[data-events]'); body.replaceChildren()
    const completed = []
    for (const event of result.events) {
      const previous = knownEventStates.get(event.id)
      if (['pending', 'running'].includes(previous) && !['pending', 'running'].includes(event.state) && event.runId) completed.push(event)
      knownEventStates.set(event.id, event.state)
      const tr = document.createElement('tr')
      const delivery = kind => {
        const item = event.deliveries[kind]
        return item ? `${deliveryStates[item.state] || item.state}${item.error ? ` · ${item.error}` : ''}` : '等待执行'
      }
      for (const text of [new Date(event.dueAt).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false }),
        `${event.id} · ${eventStates[event.state] || event.state}${event.error ? ` · ${event.error}` : ''}`, delivery('jira'), delivery('confluence')]) {
        const td = document.createElement('td'); td.textContent = text; tr.append(td)
      }
      const td = document.createElement('td')
      if (event.runId) {
        const button = document.createElement('button'); button.className = 'button button-secondary'; button.textContent = '查看'; button.dataset.eventView = ''
        button.addEventListener('click', () => { const current = ++generation; void perform(async () => follow(await api.get(event.runId), current)) })
        td.append(button)
      }
      tr.append(td); body.append(tr)
    }
    eventPolling = result.events.some(event => ['pending', 'running'].includes(event.state))
    if (completed.length) {
      await listing()
      show(await api.get(completed[0].runId))
    }
    if (eventPolling) {
      eventTimer = setTimeout(() => { void perform(events) }, 1000)
    }
  }
  root.querySelector('[data-event-form]').addEventListener('submit', async event => {
    event.preventDefault()
    const button = root.querySelector('[data-event-create]')
    const message = root.querySelector('[data-event-status]')
    const value = root.querySelector('[data-event-time]').value
    const dueAt = `${value}:00+08:00`
    if (!value || new Date(dueAt).getTime() <= Date.now()) { message.textContent = '请选择未来的北京时间。'; return }
    button.disabled = true
    try {
      const created = await api.createEvent(dueAt)
      if (destroyed) return
      message.textContent = `事件已创建：${created.id}`
      await events()
    } catch (error) { if (!destroyed) message.textContent = error.message }
    finally { if (!destroyed) button.disabled = false }
  })
  root.querySelector('[data-schedule-form]').addEventListener('submit', async event => {
    event.preventDefault()
    const button = root.querySelector('[data-schedule-save]'); button.disabled = true
    try {
      const result = await api.saveSchedule({ weekday: Number(scheduleWeekday.value), time: scheduleTime.value, enabled: scheduleEnabled.checked })
      showSchedule(result.schedule)
    } catch (error) { if (!destroyed) scheduleStatus.textContent = error.message }
    finally { if (!destroyed) button.disabled = false }
  })
  root.querySelector('[data-schedule-delete]').addEventListener('click', async () => {
    const button = root.querySelector('[data-schedule-delete]'); button.disabled = true
    try { await api.deleteSchedule(); showSchedule(null) }
    catch (error) { if (!destroyed) { scheduleStatus.textContent = error.message; button.disabled = false } }
  })
  trigger.addEventListener('click', () => perform(async () => {
    trigger.disabled = true
    status.textContent = '正在触发…'
    try {
      const detail = await api.trigger()
      if (destroyed) return
      offset = 0; await listing(); await follow(detail, ++generation)
    } finally { if (!destroyed) trigger.disabled = false }
  }))
  for (const [selector, delta] of [['[data-prev]', -4], ['[data-next]', 4]]) {
    root.querySelector(selector).addEventListener('click', () => perform(async () => { offset += delta; await listing() }))
  }
  return { async start() { await perform(async () => { await listing(); await events(); await loadSchedule(); if (!destroyed) status.textContent = '可查看历史，或立即触发新一期审查。' }) }, destroy() { destroyed = true; eventPolling = false; generation++; clearTimeout(eventTimer); root.replaceChildren() } }
}
