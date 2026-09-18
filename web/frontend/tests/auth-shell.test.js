// @vitest-environment jsdom
import { expect, it, vi } from 'vitest'
import { createAuthShell } from '../src/auth-shell.js'

it('opens Settings and Sign out together in the user dropdown', async () => {
  document.body.innerHTML = '<div id="desktop"></div><div id="mobile"></div>'
  const api = { session: async () => ({ authenticated: true, username: 'coco' }), logout: vi.fn() }
  const shell = createAuthShell({ desktopHost: document.querySelector('#desktop'), mobileHost: document.querySelector('#mobile'), api })
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
  shell.destroy()
})
