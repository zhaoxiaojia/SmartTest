// @vitest-environment jsdom
import { expect, it, vi } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { mount } from '../src/pages/settings.js'

it('replays dark mode and synchronizes shell and settings switches through the existing theme preference', async () => {
  document.body.innerHTML = '<div data-app-shell data-page-key="settings"></div>'
  const style = document.createElement('style')
  style.textContent = readFileSync(resolve(import.meta.dirname, '../src/smarttest-theme.css'), 'utf8')
  document.head.append(style)
  const writes = []
  vi.stubGlobal('fetch', vi.fn(async (url, options = {}) => {
    if (options.method === 'PUT') writes.push(JSON.parse(options.body))
    return { ok: true, json: async () => url.includes('/auth/session')
      ? { authenticated: true, username: 'alice' } : { items: { theme: 'dark' } } }
  }))
  const { shellReady, preferencesReady } = await import('../src/main.js')
  await shellReady; await preferencesReady
  mount(document.querySelector('main')).start()
  await vi.waitFor(() => expect(document.querySelectorAll('.theme-toggle input')).toHaveLength(3))
  await vi.waitFor(() => expect([...document.querySelectorAll('.theme-toggle input')].every(input => input.checked)).toBe(true))
  expect(document.querySelector('.theme-toggle input').getAttribute('aria-label')).toBe('Dark theme')
  document.querySelector('.theme-toggle input').click()
  await vi.waitFor(() => expect(writes).toContainEqual({ items: { theme: 'light' }, schemaVersion: 1 }))
  expect([...document.querySelectorAll('.theme-toggle input')].every(input => !input.checked)).toBe(true)
  expect(document.documentElement.classList.contains('dark-theme')).toBe(false)
  vi.unstubAllGlobals()
})
