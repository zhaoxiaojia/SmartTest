import { shellReady } from './main.js'

export function startAuthenticatedPage({ mount }) {
  const root = document.querySelector('main.main-content')
  const section = document.createElement('div')
  root.replaceChildren(section)
  let page
  let account
  let bootstrapPending = true

  function clear() {
    page?.destroy?.()
    page = null
    section.replaceChildren()
  }

  function showSession(session) {
    const nextAccount = session?.authenticated ? session.username : null
    if (account === nextAccount) return
    account = nextAccount
    clear()
    if (!session?.authenticated) {
      section.textContent = 'Please sign in.'
      return
    }
    page = mount(section)
    void page?.start?.()
  }

  window.addEventListener('session:changing', () => {
    bootstrapPending = false
    clear()
    account = undefined
  })
  window.addEventListener('session:ready', event => {
    bootstrapPending = false
    showSession(event.detail)
  })
  void shellReady.then(session => { if (bootstrapPending) showSession(session) })
}
