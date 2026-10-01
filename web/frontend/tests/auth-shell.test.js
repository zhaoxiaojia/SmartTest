// @vitest-environment jsdom
import { expect, it, vi } from 'vitest'
import { createAuthShell } from '../src/auth-shell.js'

it('opens Settings and Sign out together in the user dropdown', async () => {
  document.body.innerHTML = '<div id="desktop"></div><div id="mobile"></div>'
  let finishLogout
  const api = { session: async () => ({ authenticated: true, username: 'coco' }), logout: vi.fn(() => new Promise(resolve => { finishLogout = resolve })) }
  const navigate = vi.fn()
  const shell = createAuthShell({ desktopHost: document.querySelector('#desktop'), mobileHost: document.querySelector('#mobile'), api, navigate })
  await shell.start()
  const menu = document.querySelector('#desktop [data-user-dropdown]')
  expect(menu).not.toBeNull()
  expect(menu.hidden).toBe(true)
  document.querySelector('#desktop [data-user-trigger]').click()
  expect(menu.hidden).toBe(false)
  expect(menu.querySelector('a').getAttribute('href')).toBe('/settings.html')
  expect(menu.querySelector('a').textContent).toBe('Settings')
  menu.querySelector('[data-logout]').click()
  await vi.waitFor(() => expect(api.logout).toHaveBeenCalledOnce())
  expect(navigate).not.toHaveBeenCalled()
  finishLogout()
  await vi.waitFor(() => expect(navigate).toHaveBeenCalledOnce())
  expect(navigate.mock.calls[0][0]).toMatch(/^\/login.html\?next=/)
  expect(document.querySelector('[data-login]')).toBeNull()
  shell.destroy()
})

it('redirects confirmed unauthenticated visits to the existing login and preserves the return path', async () => {
  window.history.replaceState({}, '', '/jira.html?tab=task#details')
  document.body.innerHTML = '<div id="desktop"></div><div id="mobile"></div>'
  const navigate = vi.fn()
  const shell = createAuthShell({ desktopHost: document.querySelector('#desktop'), mobileHost: document.querySelector('#mobile'),
    api: { session: async () => ({ authenticated: false }) }, navigate })
  try {
    await shell.start()
    expect(navigate).toHaveBeenCalledWith('/login.html?next=%2Fjira.html%3Ftab%3Dtask%23details')
    expect(document.querySelector('[data-login]')).toBeNull()
  } finally { shell.destroy() }
})

it('does not navigate or replace the authenticated menu when logout rejects', async () => {
  document.body.innerHTML = '<div id="desktop"></div><div id="mobile"></div>'
  const root = new EventTarget()
  root.querySelector = () => null
  const listeners = vi.spyOn(root, 'addEventListener')
  const navigate = vi.fn()
  const shell = createAuthShell({ root, desktopHost: document.querySelector('#desktop'), mobileHost: document.querySelector('#mobile'),
    api: { session: async () => ({ authenticated: true, username: 'coco' }), logout: async () => { throw new Error('Authentication failed (503).') } }, navigate })
  try {
    await shell.start()
    const click = listeners.mock.calls.find(([name]) => name === 'click')[1]
    await expect(click({ target: document.querySelector('[data-logout]') })).rejects.toThrow('Authentication failed (503).')
    expect(navigate).not.toHaveBeenCalled()
    expect(document.querySelector('[data-user-name]').textContent).toBe('coco')
  } finally { shell.destroy(); listeners.mockRestore() }
})
