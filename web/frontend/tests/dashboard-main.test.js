// @vitest-environment jsdom

import { beforeEach, describe, expect, it, vi } from 'vitest'

const authenticatedPage = vi.hoisted(() => ({ options: null }))

vi.mock('../src/authenticated-page.js', () => ({
  startAuthenticatedPage: vi.fn(options => { authenticatedPage.options = options }),
}))

describe('Dashboard page', () => {
  beforeEach(() => {
    document.body.innerHTML = '<main></main>'
    authenticatedPage.options = null
  })

  it('leaves the authenticated Dashboard content empty', async () => {
    await import('../src/dashboard-main.js')

    const root = document.querySelector('main')
    const page = authenticatedPage.options.mount(root, { username: 'coco' })
    await page.start()

    expect(root.childElementCount).toBe(0)
    expect(root.textContent).toBe('')
  })
})
