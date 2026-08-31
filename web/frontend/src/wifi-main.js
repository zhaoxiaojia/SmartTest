import { Chart, registerables } from 'chart.js'

import { createWifiDatabaseApi } from './api.js'
import { mountWifiDatabase } from './wifi-database.js'
import { createChartController, exportPerformanceExcel, exportVisibleChartsPdf } from './dashboard.js'

Chart.register(...registerables)

export function startWifiData() {
  const root = document.querySelector('main.main-content')
  if (!root) return

  const charts = createChartController({ chartFactory: (canvas, config) => new Chart(canvas, config) })
  return mountWifiDatabase({
    root,
    api: createWifiDatabaseApi({ baseUrl: globalThis.SMARTTEST_API_BASE ?? '/api' }),
    capabilities: {
      charts,
      exportExcel: async rows => {
        const exceljs = await import('exceljs')
        const Workbook = exceljs.Workbook ?? exceljs.default?.Workbook
        await exportPerformanceExcel(rows, { Workbook })
      },
      exportPdf: async (container, dataType) => {
        const { jsPDF } = await import('jspdf')
        exportVisibleChartsPdf(container, { JsPdf: jsPDF, dataType })
      }
    }
  })
}
