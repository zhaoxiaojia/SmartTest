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
    expect(polar[0].directions.uplink[0].points.filter(point => point.throughput !== null)).toEqual([
      { angle: 0, throughput: 150 },
      { angle: 90, throughput: 50 }
    ])
  })

  it.each([
    [[0, 180], 13, 30],
    [[45, 135], 9, 45],
    [[15, 75], 25, 15]
  ])('completes sparse RVO angles using the legacy 30/45/15 rule', (sourceAngles, length, step) => {
    const polar = groupPolarSeries([
      { ...rows[0], angleDeg: sourceAngles[0], throughputAvgMbps: 100 },
      { ...rows[0], angleDeg: sourceAngles[1], throughputAvgMbps: 50 }
    ], 'RVO')
    const points = polar[0].directions.uplink[0].points
    expect(points).toHaveLength(length)
    expect(points[1].angle).toBe(step)
    expect(points.at(-1).angle).toBe(360)
  })

  it('chooses the legacy RVO completion step independently per scenario', () => {
    const polar = groupPolarSeries([
      { ...rows[0], scenarioGroupKey: 'BAND=5G', angleDeg: 45, throughputAvgMbps: 100 },
      { ...rows[0], scenarioGroupKey: 'BAND=5G', angleDeg: 135, throughputAvgMbps: 50 },
      { ...rows[0], scenarioGroupKey: 'BAND=6G', angleDeg: 15, throughputAvgMbps: 100 },
      { ...rows[0], scenarioGroupKey: 'BAND=6G', angleDeg: 75, throughputAvgMbps: 50 }
    ], 'RVO')
    expect(polar.map(group => group.directions.uplink[0].points.length)).toEqual([9, 25])
  })

  it('uses legacy scenario and series labels from row metadata and scenario keys', () => {
    const groups = groupLineSeries([{
      testReportId: 4, projectNickname: 'Apollo EVT', projectId: 9,
      scenarioGroupKey: 'BAND=5G|STANDARD=11BE|BW=80|CHANNEL=42', direction: 'tx',
      pathLossDb: 10, throughputAvgMbps: 900
    }], 'RVR')
    expect(groups[0].label).toBe('5G · 11BE · 80MHz · CH 42')
    expect(groups[0].directions.uplink[0].label).toBe('Apollo EVT CH 42')
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
    expect(container.querySelector('section').className).toBe('scenario')
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
    expect(worksheet.columns.map(column => column.header)).toEqual([
      'Index', 'Path_Loss_dB', 'Throughput_Avg_Mbps', 'Direction', 'Band', 'Bandwidth_MHz',
      'Channel', 'Center_Freq_MHz', 'Standard', 'Test_Category', 'Protocol', 'Case_Path',
      'Product_Line', 'Project', 'ADB_Device', 'Telnet_IP', 'Created_At'
    ])
    expect(worksheet.addRows.mock.calls[0][0][0]).toMatchObject({ Index: 1, Direction: 'Tx' })
    expect(saveFile.mock.calls[0][1]).toMatch(/^wifi-performance-.*\.xlsx$/)
  })

  it('exports two visible charts per themed PDF page', () => {
    const container = document.createElement('div')
    const canvas = document.createElement('canvas')
    canvas.dataset.exportTitle = '5G - Tx (Uplink)'
    canvas.toDataURL = vi.fn(() => 'data:image/png;base64,chart')
    const second = canvas.cloneNode(); second.toDataURL = canvas.toDataURL
    const third = canvas.cloneNode(); third.toDataURL = canvas.toDataURL
    container.append(canvas, second, third)
    const drawImage = vi.fn(); const fillRect = vi.fn()
    const createCanvas = vi.fn(() => ({
      width: 0, height: 0,
      getContext: () => ({ fillStyle: '', fillRect, drawImage }),
      toDataURL: () => 'data:image/png;base64,composed'
    }))
    const pdf = { internal: { pageSize: { getWidth: () => 842, getHeight: () => 595 } }, setFont: vi.fn(), setFontSize: vi.fn(), text: vi.fn(), addImage: vi.fn(), addPage: vi.fn(), save: vi.fn() }
    const JsPdf = vi.fn(() => pdf)

    exportVisibleChartsPdf(container, { JsPdf, createCanvas, background: '#111722', dataType: 'RVO' })

    expect(fillRect).toHaveBeenCalledTimes(3)
    expect(drawImage).toHaveBeenCalledTimes(3)
    expect(pdf.addImage).toHaveBeenCalledTimes(3)
    expect(pdf.addPage).toHaveBeenCalledTimes(1)
    expect(pdf.text).toHaveBeenCalledWith('Type: RVO', expect.any(Number), expect.any(Number))
    const [, , , , width, height] = pdf.addImage.mock.calls[0]
    expect(width / height).toBeCloseTo((canvas.width + 36) / (canvas.height + 36))
    expect(pdf.save.mock.calls[0][0]).toMatch(/^wifi-performance-.*\.pdf$/)
  })
})
