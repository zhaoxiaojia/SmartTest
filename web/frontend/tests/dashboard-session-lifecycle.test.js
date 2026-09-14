// @vitest-environment jsdom
import { expect, it, vi } from 'vitest'

it('destroys and clears the prior Dashboard before mounting the next account', async () => {
  vi.resetModules()
  document.body.innerHTML = '<main class="main-content"></main>'
  let finishBootstrap
  const shellReady = new Promise(resolve => { finishBootstrap = resolve })
  vi.doMock('../src/main.js', () => ({ shellReady }))
  const { startAuthenticatedPage } = await import('../src/authenticated-page.js')
  const pages = []
  startAuthenticatedPage({ mount(root, session) {
    root.textContent = `${session.username} dashboard`
    const page = { account: session.username, start: vi.fn(), destroy: vi.fn() }
    pages.push(page)
    return page
  } })
  try {
    window.dispatchEvent(new CustomEvent('session:ready', { detail: { authenticated: true, username: 'alice' } }))
    expect(document.querySelector('main').textContent).toBe('alice dashboard')
    window.dispatchEvent(new Event('session:changing'))
    expect(pages[0].destroy).toHaveBeenCalledOnce()
    expect(document.querySelector('main').textContent).toBe('')
    window.dispatchEvent(new CustomEvent('session:ready', { detail: { authenticated: true, username: 'bob' } }))
    expect(document.querySelector('main').textContent).toBe('bob dashboard')
    expect(document.querySelector('main').textContent).not.toContain('alice')
    finishBootstrap({ authenticated: true, username: 'alice' })
    await shellReady
    await Promise.resolve()
    expect(document.querySelector('main').textContent).toBe('bob dashboard')
    expect(pages).toHaveLength(2)
  } finally {
    window.dispatchEvent(new Event('session:changing'))
    vi.doUnmock('../src/main.js')
  }
})
