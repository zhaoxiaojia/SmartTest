// @vitest-environment jsdom
import { describe, expect, it, vi } from 'vitest'

import {
  createChartController,
  exportPerformanceExcel,
  exportVisibleChartsPdf,
  groupLineSeries,
  groupPolarSeries
} from '../src/dashboard.js'

const rows = [
  { testReportId: 1, reportName: 'a.csv', scenarioGroupKey: 'BAND=5G|BW=80|STANDARD=BE', direction: 'tx', pathLossDb: 20, throughputAvgMbps: 900, project: 'Apollo' },
  { testReportId: 1, reportName: 'a.csv', scenarioGroupKey: 'BAND=5G|BW=80|STANDARD=BE', direction: 'tx', pathLossDb: 10, throughputAvgMbps: 1000, project: 'Apollo' },
  { testReportId: 2, reportName: 'b.csv', scenarioGroupKey: 'BAND=5G|BW=80|STANDARD=BE', direction: 'rx', pathLossDb: 10, throughputAvgMbps: 800, project: 'Zeus' }
]

describe('legacy Wi-Fi Database domain processing', () => {
  it('groups PEAK/RVR rows by scenario and direction with path-loss ordering', () => {
    const groups = groupLineSeries(rows, 'PEAK_THROUGHPUT')
    expect(groups).toHaveLength(1)
    expect(groups[0].directions.uplink[0].points.map(point => point.x)).toEqual([10, 20])
    expect(groups[0].directions.downlink[0].label).toContain('Zeus')

    const rvr = groupLineSeries([{ ...rows[0], direction: null }], 'RVR')
    expect(rvr[0].directions.uplink).toHaveLength(1)
  })

  it('averages duplicate RVO angles inside scenario and direction polar series', () => {
    const polar = groupPolarSeries([
      { ...rows[0], angleDeg: 0, throughputAvgMbps: 100 },
      { ...rows[0], angleDeg: 0, throughputAvgMbps: 200 },
      { ...rows[0], angleDeg: 90, throughputAvgMbps: 50 }
    ], 'RVO')
    expect(polar[0].directions.uplink[0].points).toEqual([
      { angle: 0, throughput: 150 },
      { angle: 90, throughput: 50 }
    ])
  })

  it('destroys old chart instances when rendering another datatype', () => {
    const created = []
    const factory = vi.fn(() => {
      const chart = { destroy: vi.fn() }
      created.push(chart)
      return chart
    })
    const controller = createChartController({ chartFactory: factory })
    const container = document.createElement('div')

    controller.render(container, rows, 'PEAK_THROUGHPUT')
    controller.render(container, [{ ...rows[0], angleDeg: 0 }], 'RVO')

    expect(created[0].destroy).toHaveBeenCalledOnce()
    expect(created[1].destroy).toHaveBeenCalledOnce()
    expect(factory.mock.calls[0][1].type).toBe('line')
    expect(factory.mock.calls[2][1].type).toBe('radar')
    controller.clear()
    expect(created[2].destroy).toHaveBeenCalledOnce()
  })

  it('exports original performance rows through an ExcelJS workbook', async () => {
    const worksheet = { columns: null, addRows: vi.fn() }
    const workbook = { addWorksheet: vi.fn(() => worksheet), xlsx: { writeBuffer: vi.fn(async () => new Uint8Array([1, 2])) } }
    const Workbook = vi.fn(() => workbook)
    const saveFile = vi.fn()

    await exportPerformanceExcel(rows, { Workbook, saveFile, now: new Date('2026-08-24T12:00:00Z') })

    expect(workbook.addWorksheet).toHaveBeenCalledWith('Performance')
    expect(worksheet.columns.map(column => column.key)).toEqual(Object.keys(rows[0]))
    expect(worksheet.addRows).toHaveBeenCalledWith(rows)
    expect(saveFile.mock.calls[0][1]).toMatch(/^wifi-performance-.*\.xlsx$/)
  })

  it('exports each visible chart to PDF', () => {
    const container = document.createElement('div')
    const canvas = document.createElement('canvas')
    canvas.dataset.exportTitle = '5G - Tx (Uplink)'
    canvas.toDataURL = vi.fn(() => 'data:image/png;base64,chart')
    container.append(canvas)
    const pdf = { text: vi.fn(), addImage: vi.fn(), addPage: vi.fn(), save: vi.fn() }
    const JsPdf = vi.fn(() => pdf)

    exportVisibleChartsPdf(container, { JsPdf })

    expect(pdf.text).toHaveBeenCalledWith('5G - Tx (Uplink)', 24, 24)
    expect(pdf.addImage).toHaveBeenCalled()
    expect(pdf.save.mock.calls[0][0]).toMatch(/^wifi-performance-.*\.pdf$/)
  })
})
