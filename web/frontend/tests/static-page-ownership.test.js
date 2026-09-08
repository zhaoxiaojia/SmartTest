// @vitest-environment node
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const source = file => readFileSync(resolve(import.meta.dirname, '../src', file), 'utf8')

describe('static page ownership', () => {
  it.each(['settings', 'inbox', 'analytics'])('%s owns and mounts its page content', pageKey => {
    const page = source(`pages/${pageKey}.js`)
    expect(page).toContain('export function mount')
    expect(page).toContain('root.innerHTML')
  })

  it('loads only the selected page module through dynamic imports', () => {
    const entry = source('static-page-main.js')
    expect(entry).toContain("settings: () => import('./pages/settings.js')")
    expect(entry).toContain("inbox: () => import('./pages/inbox.js')")
    expect(entry).toContain("analytics: () => import('./pages/analytics.js')")
    expect(entry).not.toContain('static-page-content')
  })
})
