// @vitest-environment jsdom
import { describe, expect, it } from 'vitest'
import { element, escapeHtml } from '../src/dom.js'

describe('DOM helpers', () => {
  it('escapes text and creates text-only elements', () => {
    expect(escapeHtml('<img onerror=x>')).toBe('&lt;img onerror=x&gt;')
    const node = element('span', 'tag', '<unsafe>')
    expect(node.outerHTML).toBe('<span class="tag">&lt;unsafe&gt;</span>')
  })
})
