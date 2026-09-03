// @vitest-environment node
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { JSDOM } from 'jsdom'
import { describe, expect, it } from 'vitest'

const entries = ['index.html', 'projects.html', 'jira.html', 'settings.html', 'inbox.html', 'analytics.html']
const brandedEntries = [...entries, 'login.html']
const navigation = ['Dashboard', 'Projects', 'Jira', 'Wi-Fi Data', 'Settings']

describe('static FAE-QA Data Center shell entries', () => {
  it.each(brandedEntries)('%s uses only the FAE-QA Data Center user-facing brand', file => {
    const document = new JSDOM(readFileSync(resolve(import.meta.dirname, '..', file), 'utf8')).window.document
    expect(document.title).not.toContain('SmartTest')
    expect(document.body.textContent).not.toContain('SmartTest')
    expect(`${document.title} ${document.body.textContent}`).toContain('FAE-QA Data Center')
  })

  it.each(entries)('%s owns the common shell and main mount point', file => {
    const html = readFileSync(resolve(import.meta.dirname, '..', file), 'utf8')
    const document = new JSDOM(html).window.document
    expect(document.querySelector('.logo').textContent.replace(/\s+/g, ' ').trim()).toContain('FAE-QA Data Center')
    expect([...document.querySelectorAll('.nav-menu a')].map(link => link.textContent.trim())).toEqual(navigation)
    expect([...document.querySelectorAll('.mobile-menu-nav a')].map(link => link.textContent.trim())).toEqual(navigation)
    expect(document.querySelector('main.main-content')).not.toBeNull()
  })

  it('keeps portal runtime limited to common interactions', () => {
    const source = readFileSync(resolve(import.meta.dirname, '../public/smarttest-portal.js'), 'utf8')
    expect(source).not.toContain('initReportNavigation')
    expect(source).not.toContain("'/jira.html'")
    expect(source).not.toContain("'/confluence.html'")
  })

  it('provides the Wi-Fi sub-navigation statically for route activation', () => {
    const document = new JSDOM(readFileSync(resolve(import.meta.dirname, '../index.html'), 'utf8')).window.document
    expect([...document.querySelectorAll('.database-nav a')].map(link => link.textContent.trim())).toEqual(['Peak Throughput', 'RVR', 'RVO'])
  })
})
