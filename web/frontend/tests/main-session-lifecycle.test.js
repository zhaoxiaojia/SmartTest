// @vitest-environment jsdom
import { expect, it, vi } from 'vitest'

it('clears all disposable Projects displays on identity change from a non-Projects page', async () => {
  window.history.replaceState({}, '', '/jira.html')
  document.body.innerHTML = '<nav class="nav-right"></nav><div class="mobile-menu-footer"></div>'
  sessionStorage.setItem('smarttest:projects-display:alice', '{"projects":[]}')
  sessionStorage.setItem('smarttest:projects-display:bob', '{"projects":[]}')
  sessionStorage.setItem('unrelated', 'keep')
  const fetchImpl = vi.fn().mockResolvedValue({
    ok: true, json: async () => ({ authenticated: true, username: 'alice' }),
  })
  vi.stubGlobal('fetch', fetchImpl)

  const { shellReady } = await import('../src/main.js')
  await shellReady
  window.dispatchEvent(new Event('auth:changed'))

  expect(sessionStorage.getItem('smarttest:projects-display:alice')).toBeNull()
  expect(sessionStorage.getItem('smarttest:projects-display:bob')).toBeNull()
  expect(sessionStorage.getItem('unrelated')).toBe('keep')
  vi.unstubAllGlobals()
})
