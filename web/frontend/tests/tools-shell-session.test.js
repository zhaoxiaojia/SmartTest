// @vitest-environment jsdom
import { expect, it, vi } from 'vitest'

it('renders the authenticated account in both Tools shell account hosts', async () => {
  window.history.replaceState({}, '', '/tools.html')
  document.body.innerHTML = '<div data-app-shell data-page-key="tools"></div>'
  vi.stubGlobal('fetch', vi.fn(async url => ({
    ok: true,
    json: async () => new URL(url, window.location.origin).pathname === '/api/auth/session'
      ? { authenticated: true, username: 'coco', displayName: 'Coco' }
      : { items: {} },
  })))
  const { shellReady } = await import('../src/main.js')
  try {
    expect(await shellReady).toMatchObject({ authenticated: true, username: 'coco' })
    expect([...document.querySelectorAll('[data-user-name]')].map(node => node.textContent)).toEqual(['Coco', 'Coco'])
  } finally {
    vi.unstubAllGlobals()
  }
})
