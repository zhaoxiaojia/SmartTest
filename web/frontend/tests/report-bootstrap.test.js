// @vitest-environment jsdom
import { expect, it, vi } from 'vitest'

it.each(['changing', 'ready'])('ignores old bootstrap after session:%s', async eventName => {
  vi.resetModules()
  window.history.replaceState({}, '', '/jira.html')
  document.body.innerHTML = '<main class="main-content"></main>'
  let finishBootstrap
  const shellReady = new Promise(resolve => { finishBootstrap = resolve })
  vi.doMock('../src/main.js', () => ({ shellReady, preferencesReady: Promise.resolve() }))
  const listeners = vi.spyOn(window, 'addEventListener')
  await import('../src/report-main.js')
  try {
    window.dispatchEvent(new CustomEvent(`session:${eventName}`, {
      detail: { authenticated: true, username: 'bob' }
    }))
    const currentForm = document.querySelector('form')
    if (eventName === 'ready') {
      expect(currentForm).not.toBeNull()
      currentForm.elements.auditInput.value = 'Bob current edit'
    } else expect(currentForm).toBeNull()
    finishBootstrap({ authenticated: true, username: 'alice' })
    await shellReady
    await Promise.resolve()
    expect(document.querySelector('form')).toBe(currentForm)
    if (currentForm) expect(currentForm.elements.auditInput.value).toBe('Bob current edit')
    else {
      window.dispatchEvent(new CustomEvent('session:ready', { detail: { authenticated: true, username: 'bob' } }))
      expect(document.querySelector('form')).not.toBeNull()
    }
  } finally {
    window.dispatchEvent(new Event('session:changing'))
    for (const [name, listener, options] of listeners.mock.calls) window.removeEventListener(name, listener, options)
    listeners.mockRestore()
    vi.doUnmock('../src/main.js')
  }
})
