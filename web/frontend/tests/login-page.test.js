// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { createLoginPage, safeReturnPath } from '../src/login-page.js'

describe('SmartTest login page', () => {
  beforeEach(() => {
    document.body.innerHTML = `<form data-login-form>
      <input name="username"><input name="password" type="password">
      <div data-auth-status></div><button type="submit">Sign in</button>
    </form>`
    window.history.replaceState({}, '', '/login.html')
  })

  it('authenticates once and returns to the requested internal page', async () => {
    window.history.replaceState({}, '', '/login.html?next=%2Fprojects.html%3Fview%3Downers')
    const api = { session: vi.fn().mockResolvedValue({ authenticated: false }), login: vi.fn().mockResolvedValue({ authenticated: true }) }
    const navigate = vi.fn()
    await createLoginPage({ root: document, api, navigate }).start()
    const form = document.querySelector('form')
    form.elements.username.value = 'coco'; form.elements.password.value = 'secret'
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
    await vi.waitFor(() => expect(navigate).toHaveBeenCalledWith('/projects.html?view=owners'))
    expect(api.login).toHaveBeenCalledWith('coco', 'secret')
    expect(form.elements.password.value).toBe('')
  })

  it('does not allow an external return URL', () => {
    expect(safeReturnPath('https://evil.example/path')).toBe('/')
    expect(safeReturnPath('//evil.example/path')).toBe('/')
    expect(safeReturnPath('/jira.html')).toBe('/jira.html')
  })

  it('shows a safe failure and remains on the login page', async () => {
    const api = { session: vi.fn().mockResolvedValue({ authenticated: false }), login: vi.fn().mockRejectedValue(new Error('LDAP detail')) }
    const navigate = vi.fn()
    await createLoginPage({ root: document, api, navigate }).start()
    const form = document.querySelector('form')
    form.elements.username.value = 'coco'; form.elements.password.value = 'bad'
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
    await vi.waitFor(() => expect(document.querySelector('[data-auth-status]').textContent).toContain('Sign in failed'))
    expect(navigate).not.toHaveBeenCalled()
    expect(form.elements.password.value).toBe('')
  })
})
