// @vitest-environment jsdom
import { expect, it, vi } from 'vitest'

it('imports the real entry and preserves Apply controls and Review polling across same-session ready', async () => {
  window.history.replaceState({}, '', '/confluence.html')
  document.body.innerHTML = '<nav class="nav-right"></nav><div class="mobile-menu-footer"></div><main class="main-content"></main>'
  const ready = { state: 'ready', accessibleProjectCount: 1,
    facets: [{ key: '__product_space__', label: 'Product Space', options: ['TV'] }],
    projects: [{ project_id: 'P1', name: 'Project One', space_key: 'TV' }], ownerHierarchy: [], sync: { state: 'idle' } }
  const respond = data => ({ ok: true, json: async () => data })
  let finishRefresh, finishApply, finishReview
  let snapshotRequests = 0
  const reviewRequests = []
  const fetchImpl = vi.fn(async (url, options = {}) => {
    const path = new URL(url, window.location.origin)
    if (path.pathname === '/api/auth/session') return respond({ authenticated: true, username: 'alice' })
    if (path.pathname.startsWith('/api/preferences/')) return respond({ items: {} })
    if (path.pathname === '/api/confluence/project-facts') {
      if (path.searchParams.get('details') === '1') return new Promise(resolve => { finishApply = data => resolve(respond(data)) })
      snapshotRequests += 1
      if (snapshotRequests === 2) return new Promise(resolve => { finishRefresh = data => resolve(respond(data)) })
      return respond(ready)
    }
    if (path.pathname === '/api/audits/confluence' && options.method === 'POST') {
      return respond({ auditId: 'review-alice', status: 'queued', progress: { processed: 0, total: 1 } })
    }
    if (path.pathname === '/api/audits/confluence/review-alice') {
      reviewRequests.push(path.pathname)
      return new Promise(resolve => { finishReview = data => resolve(respond(data)) })
    }
    throw new Error(`Unexpected request: ${path.pathname}`)
  })
  vi.stubGlobal('fetch', fetchImpl)
  await import('../src/report-main.js')
  try {
    await vi.waitFor(() => expect(finishRefresh).toBeTypeOf('function'))
    const form = document.querySelector('main form')
    const select = form.elements['field.__product_space__']
    select.value = 'TV'
    form.elements.search.value = 'Project One'
    form.elements.reviewStartDate.value = '2026-08-17'
    form.elements.reviewEndDate.value = '2026-08-24'
    finishRefresh(ready)
    await vi.waitFor(() => expect(form.querySelector('[type="submit"]').disabled).toBe(false))
    expect(form.elements['field.__product_space__']).toBe(select)
    expect(select.value).toBe('TV')

    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
    await vi.waitFor(() => expect(finishApply).toBeTypeOf('function'))
    expect(document.querySelector('main form')).toBe(form)
    finishApply(ready)
    await vi.waitFor(() => expect(form.querySelector('[data-audit]').disabled).toBe(false))
    form.querySelector('[data-audit]').click()
    await vi.waitFor(() => expect(finishReview).toBeTypeOf('function'))
    window.dispatchEvent(new CustomEvent('session:ready', { detail: { authenticated: true, username: 'alice' } }))
    expect(document.querySelector('main form')).toBe(form)
    expect(form.elements['field.__product_space__']).toBe(select)
    expect(form.elements.search.value).toBe('Project One')
    expect(form.elements.reviewStartDate.value).toBe('2026-08-17')
    expect(form.elements.reviewEndDate.value).toBe('2026-08-24')
    finishReview({ auditId: 'review-alice', status: 'running', progress: { processed: 0, total: 1 } })
    await vi.waitFor(() => expect(reviewRequests).toHaveLength(2))
    expect(reviewRequests).toEqual(['/api/audits/confluence/review-alice', '/api/audits/confluence/review-alice'])

    window.dispatchEvent(new Event('session:changing'))
    expect(document.querySelector('main form')).toBeNull()
    finishReview({ auditId: 'review-alice', status: 'completed', progress: { processed: 1, total: 1 } })
    window.dispatchEvent(new CustomEvent('session:ready', { detail: { authenticated: true, username: 'alice' } }))
    await vi.waitFor(() => expect(document.querySelector('main form')).not.toBeNull())
    expect(document.querySelector('main form')).not.toBe(form)
    expect(document.querySelector('[data-audit-download]').disabled).toBe(true)
    const nextForm = document.querySelector('main form')
    window.dispatchEvent(new CustomEvent('session:ready', { detail: { authenticated: true, username: 'bob' } }))
    expect(document.querySelector('main form')).not.toBe(nextForm)
    expect(document.querySelector('[name="search"]').value).toBe('')
    expect(document.querySelector('[data-audit-download]').disabled).toBe(true)
  } finally {
    window.dispatchEvent(new Event('session:changing'))
    vi.unstubAllGlobals()
  }
})
