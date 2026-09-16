// @vitest-environment jsdom
import { expect, it, vi } from 'vitest'

it.each(['changing', 'ready'])('shared authenticated page ignores old bootstrap after session:%s', async eventName => {
  vi.resetModules()
  window.history.replaceState({}, '', '/jira.html')
  document.body.innerHTML = '<main class="main-content"></main>'
  let finishBootstrap
  const shellReady = new Promise(resolve => { finishBootstrap = resolve })
  vi.doMock('../src/main.js', () => ({ shellReady, preferencesReady: Promise.resolve() }))
  const listeners = vi.spyOn(window, 'addEventListener')
  await import('../src/jira-main.js')
  try {
    window.dispatchEvent(new CustomEvent(`session:${eventName}`, {
      detail: { authenticated: true, username: 'bob' }
    }))
    const currentPage = document.querySelector('[aria-label="Jira issue filter"]')
    if (eventName === 'ready') {
      expect(currentPage).not.toBeNull()
      const widget = document.querySelector('[data-page-widget="jira-team-bugs"]')
      expect(widget).not.toBeNull()
      expect(widget.compareDocumentPosition(currentPage) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
      currentPage.querySelector('[name="containsText"]').value = 'Bob current edit'
    } else expect(currentPage).toBeNull()
    finishBootstrap({ authenticated: true, username: 'alice' })
    await shellReady
    await Promise.resolve()
    expect(document.querySelector('[aria-label="Jira issue filter"]')).toBe(currentPage)
    if (currentPage) expect(currentPage.querySelector('[name="containsText"]').value).toBe('Bob current edit')
    else {
      window.dispatchEvent(new CustomEvent('session:ready', { detail: { authenticated: true, username: 'bob' } }))
      expect(document.querySelector('[aria-label="Jira issue filter"]')).not.toBeNull()
    }
  } finally {
    window.dispatchEvent(new Event('session:changing'))
    for (const [name, listener, options] of listeners.mock.calls) window.removeEventListener(name, listener, options)
    listeners.mockRestore()
    vi.doUnmock('../src/main.js')
  }
})
