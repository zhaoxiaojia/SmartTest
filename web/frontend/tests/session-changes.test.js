// @vitest-environment jsdom
import { expect, it, vi } from 'vitest'
import { createAuthApi } from '../src/api.js'
import { createAuthShell } from '../src/auth-shell.js'

it('does not restart preference hydration for unchanged session confirmation but resets a real same-account login', async () => {
  document.body.innerHTML = '<div id="desktop"></div><div id="mobile"></div>'
  const onSession = vi.fn(), onChanging = vi.fn()
  const api = { session: vi.fn().mockResolvedValue({ authenticated: true, username: 'alice' }) }
  const shell = createAuthShell({ root: document.body, desktopHost: document.querySelector('#desktop'),
    mobileHost: document.querySelector('#mobile'), api, onSession, onChanging })
  try {
    await shell.start()
    await shell.start()
    expect(onSession).toHaveBeenCalledOnce()
    expect(onChanging).not.toHaveBeenCalled()
    window.dispatchEvent(new Event('auth:changed'))
    await vi.waitFor(() => expect(onSession).toHaveBeenCalledTimes(2))
    expect(onChanging).toHaveBeenCalledOnce()
  } finally { shell.destroy() }
})

it('invalidates immediately on another tab login and accepts only the latest session response', async () => {
  document.body.innerHTML = '<div id="desktop"></div><div id="mobile"></div>'
  let oldResponse
  const onChanging = vi.fn(), onSession = vi.fn()
  const api = { session: vi.fn().mockResolvedValueOnce({ authenticated: true, username: 'alice' })
    .mockImplementationOnce(() => new Promise(resolve => { oldResponse = resolve }))
    .mockResolvedValueOnce({ authenticated: true, username: 'bob' }) }
  const shell = createAuthShell({ root: document.body, desktopHost: document.querySelector('#desktop'),
    mobileHost: document.querySelector('#mobile'), api, onChanging, onSession })
  await shell.start()
  window.dispatchEvent(new StorageEvent('storage', { key: 'smarttest:identity-change', newValue: 'one' }))
  expect(onChanging).toHaveBeenCalledOnce()
  window.dispatchEvent(new StorageEvent('storage', { key: 'smarttest:identity-change', newValue: 'two' }))
  await vi.waitFor(() => expect(document.querySelector('[data-user-name]').textContent).toBe('bob'))
  oldResponse({ authenticated: true, username: 'alice' })
  await Promise.resolve()
  expect(document.querySelector('[data-user-name]').textContent).toBe('bob')
  expect(onSession.mock.calls.at(-1)[0].username).toBe('bob')
  shell.destroy()
})

it('announces successful login and logout without storing identity or credentials', async () => {
  localStorage.clear()
  const changed = vi.fn()
  window.addEventListener('auth:changed', changed)
  const api = createAuthApi({ fetchImpl: vi.fn().mockResolvedValue({ ok: true, json: async () => ({ authenticated: true }) }) })
  await api.login('alice', 'private-password')
  await api.logout()
  expect(changed).toHaveBeenCalledTimes(2)
  expect(localStorage.getItem('smarttest:identity-change')).toBeTruthy()
  expect(JSON.stringify(localStorage)).not.toMatch(/alice|private-password/)
  window.removeEventListener('auth:changed', changed)
})
