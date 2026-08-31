import { Chart, registerables } from 'chart.js'
import { createManualAuditApi, createProjectFactsApi } from './api.js'
import { createConfluenceProjects } from './confluence-projects.js'
import { preferencesReady, shellReady } from './main.js'
import { createJiraManualAudit } from './manual-audits.js'

const projectFactsApi = createProjectFactsApi()
const manualAuditApi = createManualAuditApi()
Chart.register(...registerables)
const root = document.querySelector('main.main-content')
const source = window.location.pathname === '/confluence.html' ? 'confluence' : 'jira'
const section = document.createElement('div')
root.replaceChildren(section)
let page
let account
let bootstrapPending = true
window.addEventListener('session:changing', () => {
  bootstrapPending = false
  page?.destroy(); page = null; account = undefined; section.replaceChildren()
})
function showSession(session) {
  const nextAccount = session?.authenticated ? session.username : null
  if (account === nextAccount) return
  account = nextAccount
  page?.destroy(); section.replaceChildren()
  if (!session?.authenticated) { page = null; section.textContent = 'Please sign in.'; return }
  if (source === 'confluence') {
    page = createConfluenceProjects({
      root: section, api: { ...projectFactsApi, ...manualAuditApi },
      chartFactory: (canvas, config) => new Chart(canvas, config),
      waitForPreferences: async () => { await preferencesReady; await new Promise(resolve => setTimeout(resolve, 0)) }
    })
    void page.start()
  } else page = createJiraManualAudit({ root: section, api: manualAuditApi })
}
window.addEventListener('session:ready', event => {
  bootstrapPending = false
  showSession(event.detail)
})
void shellReady.then(session => { if (bootstrapPending) showSession(session) })
