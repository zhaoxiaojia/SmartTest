// @vitest-environment jsdom
import { beforeEach, describe, expect, it } from 'vitest'

import { createAppShell, navigation } from '../src/app-shell.js'

describe('AppShell', () => {
  beforeEach(() => { document.body.innerHTML = '<div data-app-shell></div>' })

  it('owns the complete Tools shell including account hosts', () => {
    const shell = createAppShell({ pageKey: 'tools' })
    expect([...document.querySelectorAll('.nav-menu a')].map(link => link.textContent.trim()))
      .toEqual(navigation.map(item => item.title))
    expect(document.querySelectorAll('.nav-link.active')).toHaveLength(1)
    expect(document.querySelector('.nav-link.active').getAttribute('href')).toBe('/tools.html')
    expect(shell.desktopHost).not.toBeNull()
    expect(shell.mobileHost).not.toBeNull()
    expect(shell.contentRoot.matches('main.main-content')).toBe(true)
  })

  it.each([
    ['audit-email', 'tools'], ['wifi', 'wifi'], ['projects', 'projects'],
  ])('maps %s to the declared %s navigation owner', (pageKey, activeKey) => {
    createAppShell({ pageKey })
    expect(document.querySelector('.nav-link.active').dataset.pageKey).toBe(activeKey)
  })

  it('fails explicitly when the required host is absent', () => {
    document.body.replaceChildren()
    expect(() => createAppShell({ pageKey: 'tools' })).toThrow('app_shell_host_missing')
  })
})
