// @vitest-environment node
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { JSDOM } from 'jsdom'
import { describe, expect, it } from 'vitest'

const entries = ['index.html', 'projects.html', 'jira.html', 'tools.html', 'settings.html', 'inbox.html', 'analytics.html', 'audit-email.html']
const brandedEntries = [...entries, 'login.html']

describe('static FAE QA Data Center shell entries', () => {
  it.each(brandedEntries)('%s uses only the shared Web brand token', file => {
    const html = readFileSync(resolve(import.meta.dirname, '..', file), 'utf8')
    const document = new JSDOM(html).window.document
    expect(document.title).not.toContain('SmartTest')
    expect(document.body.textContent).not.toContain('SmartTest')
    expect(html).toContain('__SMARTTEST_WEB_BRAND__')
    expect(html).not.toContain('FAE-QA Data Center')
    expect(html).not.toContain('FAE QA Data Center')
  })

  it('keeps Jira as an empty placeholder and removes migrated entries from old pages', () => {
    const jira = new JSDOM(readFileSync(resolve(import.meta.dirname, '../jira.html'), 'utf8')).window.document
    const projects = new JSDOM(readFileSync(resolve(import.meta.dirname, '../projects.html'), 'utf8')).window.document
    const settings = new JSDOM(readFileSync(resolve(import.meta.dirname, '../settings.html'), 'utf8')).window.document
    expect(jira.querySelector('[data-app-shell]').textContent.trim()).toBe('')
    expect(projects.body.textContent).not.toContain('Weekly Review')
    expect(settings.querySelector('a[href="/audit-email.html"]')).toBeNull()
  })

  it.each(entries)('%s delegates the common shell to AppShell', file => {
    const html = readFileSync(resolve(import.meta.dirname, '..', file), 'utf8')
    const document = new JSDOM(html).window.document
    expect(document.querySelector('[data-app-shell]')).not.toBeNull()
    expect(document.querySelector('.top-nav')).toBeNull()
    expect(document.querySelector('.mobile-menu')).toBeNull()
    expect(document.querySelector('.footer')).toBeNull()
  })

  it.each([
    ['index.html', 'dashboard'], ['projects.html', 'projects'], ['jira.html', 'jira'],
    ['tools.html', 'tools'], ['settings.html', 'settings'], ['audit-email.html', 'audit-email'],
  ])('%s declares its owning page key', (file, pageKey) => {
    const document = new JSDOM(readFileSync(resolve(import.meta.dirname, '..', file), 'utf8')).window.document
    expect(document.querySelector('[data-app-shell]').dataset.pageKey).toBe(pageKey)
  })

  it('keeps portal runtime limited to common interactions', () => {
    const source = readFileSync(resolve(import.meta.dirname, '../public/smarttest-portal.js'), 'utf8')
    expect(source).not.toContain('initReportNavigation')
    expect(source).not.toContain("'/jira.html'")
    expect(source).not.toContain("'/confluence.html'")
  })

})
