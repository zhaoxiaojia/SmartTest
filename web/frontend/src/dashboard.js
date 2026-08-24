const DIRECTIONS = ['uplink', 'downlink']

function directionOf(row, dataType) {
  const value = `${row?.direction ?? ''}`.trim().toLowerCase()
  if (value === 'tx' || value === 'uplink') return 'uplink'
  if (value === 'rx' || value === 'downlink') return 'downlink'
  return dataType === 'RVR' || dataType === 'RVO' ? 'uplink' : null
}

function scenarioOf(row) {
  const key = row.scenarioGroupKey || row.casePath || 'scenario'
  const label = `${key}`.split('|').map(part => part.trim()).filter(Boolean).join(' · ') || 'Scenario'
  return { key, label }
}

function seriesOf(row) {
  const key = `${row.testReportId ?? 'unknown'}__${row.scenarioGroupKey ?? ''}`
  const project = `${row.projectNickname || row.project || (row.projectId != null ? `Project ${row.projectId}` : 'Unknown Project')}`
  return { key, label: project }
}

function scenarioMap() {
  return new Map()
}

function ensureScenario(scenarios, row) {
  const identity = scenarioOf(row)
  if (!scenarios.has(identity.key)) {
    scenarios.set(identity.key, { ...identity, directions: { uplink: new Map(), downlink: new Map() } })
  }
  return scenarios.get(identity.key)
}

function finalize(scenarios, convert) {
  return [...scenarios.values()].map(scenario => ({
    key: scenario.key,
    label: scenario.label,
    directions: Object.fromEntries(DIRECTIONS.map(direction => [
      direction,
      [...scenario.directions[direction].values()].map(convert)
    ]))
  }))
}

export function groupLineSeries(rows, dataType) {
  const scenarios = scenarioMap()
  for (const row of rows ?? []) {
    const direction = directionOf(row, dataType)
    if (!direction || !Number.isFinite(row.pathLossDb) || !Number.isFinite(row.throughputAvgMbps)) continue
    const bucket = ensureScenario(scenarios, row).directions[direction]
    const series = seriesOf(row)
    if (!bucket.has(series.key)) bucket.set(series.key, { label: series.label, points: [] })
    bucket.get(series.key).points.push({ x: row.pathLossDb, y: row.throughputAvgMbps })
  }
  return finalize(scenarios, group => ({ ...group, points: group.points.sort((a, b) => a.x - b.x) }))
}

export function groupPolarSeries(rows, dataType) {
  const scenarios = scenarioMap()
  for (const row of rows ?? []) {
    const direction = directionOf(row, dataType)
    if (!direction || !Number.isFinite(row.angleDeg) || !Number.isFinite(row.throughputAvgMbps)) continue
    const bucket = ensureScenario(scenarios, row).directions[direction]
    const series = seriesOf(row)
    if (!bucket.has(series.key)) bucket.set(series.key, { label: series.label, angles: new Map() })
    const values = bucket.get(series.key).angles.get(row.angleDeg) ?? []
    values.push(row.throughputAvgMbps)
    bucket.get(series.key).angles.set(row.angleDeg, values)
  }
  return finalize(scenarios, group => ({
    label: group.label,
    points: [...group.angles].sort(([a], [b]) => a - b).map(([angle, values]) => ({
      angle,
      throughput: values.reduce((sum, value) => sum + value, 0) / values.length
    }))
  }))
}

const colors = ['#321fdb', '#3399ff', '#2eb85c', '#f9b115', '#e55353', '#6f42c1']

export function createChartController({ chartFactory }) {
  let instances = []
  function clear() {
    for (const instance of instances) instance.destroy()
    instances = []
  }
  function render(container, rows, dataType) {
    clear()
    container.replaceChildren()
    const scenarios = dataType === 'RVO' ? groupPolarSeries(rows, dataType) : groupLineSeries(rows, dataType)
    for (const scenario of scenarios) {
      const section = document.createElement('section')
      section.className = 'scenario card card-body mb-3'
      const title = document.createElement('h2')
      title.className = 'h5'
      title.textContent = scenario.label
      section.append(title)
      for (const direction of DIRECTIONS) {
        const groups = scenario.directions[direction]
        if (!groups.length) continue
        const heading = document.createElement('h3')
        heading.className = 'h6 mt-3'
        heading.textContent = direction === 'uplink' ? 'Tx (Uplink)' : 'Rx (Downlink)'
        const canvas = document.createElement('canvas')
        canvas.dataset.exportTitle = `${scenario.label} - ${heading.textContent}`
        section.append(heading, canvas)
        const config = dataType === 'RVO' ? polarConfig(groups) : lineConfig(groups)
        instances.push(chartFactory(canvas, config))
      }
      container.append(section)
    }
    if (!instances.length) container.textContent = 'No matching performance data.'
  }
  return { clear, render }
}

function lineConfig(groups) {
  return {
    type: 'line',
    data: { datasets: groups.map((group, index) => ({
      label: group.label,
      data: group.points,
      borderColor: colors[index % colors.length],
      backgroundColor: colors[index % colors.length],
      tension: 0.2
    })) },
    options: { parsing: false, responsive: true, plugins: { legend: { display: true } }, scales: {
      x: { type: 'linear', title: { display: true, text: 'Path Loss (dB)' } },
      y: { beginAtZero: true, title: { display: true, text: 'Throughput (Mbps)' } }
    } }
  }
}

function polarConfig(groups) {
  const angles = [...new Set(groups.flatMap(group => group.points.map(point => point.angle)))].sort((a, b) => a - b)
  return {
    type: 'radar',
    data: {
      labels: angles.map(angle => `${angle}°`),
      datasets: groups.map((group, index) => ({
        label: group.label,
        data: angles.map(angle => group.points.find(point => point.angle === angle)?.throughput ?? null),
        borderColor: colors[index % colors.length],
        backgroundColor: `${colors[index % colors.length]}22`,
        spanGaps: true
      }))
    },
    options: { responsive: true, scales: { r: { beginAtZero: true, title: { display: true, text: 'Throughput (Mbps)' } } } }
  }
}

function downloadExcel(buffer, filename) {
  const blob = new Blob([buffer], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}

export async function exportPerformanceExcel(rows, { Workbook, saveFile = downloadExcel, now = new Date() }) {
  if (!rows?.length) throw new Error('No data available to export.')
  const workbook = new Workbook()
  const worksheet = workbook.addWorksheet('Performance')
  const keys = [...new Set(rows.flatMap(row => Object.keys(row)))]
  worksheet.columns = keys.map(key => ({ header: key, key }))
  worksheet.addRows(rows)
  const buffer = await workbook.xlsx.writeBuffer()
  const timestamp = now.toISOString().replace(/[:T]/g, '-').split('.')[0]
  saveFile(buffer, `wifi-performance-${timestamp}.xlsx`)
}

export function exportVisibleChartsPdf(container, { JsPdf }) {
  const canvases = [...container.querySelectorAll('canvas')].filter(canvas => canvas.width > 0 && canvas.height > 0)
  if (!canvases.length) throw new Error('No charts available for PDF export.')
  const documentPdf = new JsPdf({ orientation: 'landscape', unit: 'pt', format: 'a4' })
  canvases.forEach((canvas, index) => {
    if (index) documentPdf.addPage()
    documentPdf.text(canvas.dataset.exportTitle || 'Wi-Fi performance', 24, 24)
    documentPdf.addImage(canvas.toDataURL('image/png'), 'PNG', 24, 40, 790, 500)
  })
  documentPdf.save(`wifi-performance-${new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')}.pdf`)
}
