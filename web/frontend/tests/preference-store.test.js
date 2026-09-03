// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPreferenceStore } from '../src/preference-store.js'

describe('PreferenceStore', () => {
  beforeEach(() => { document.body.innerHTML = ''; window.history.replaceState({}, '', '/wifi-database/rvr') })

  it('discards old-account hydration and delayed writes after identity disposal', async () => {
    document.body.innerHTML = '<form data-preference-region><input name="search"></form>'
    let resolveOld
    const api = { get: () => new Promise(resolve => { resolveOld = resolve }), put: vi.fn() }
    const store = createPreferenceStore({ root: document, api })
    const starting = store.start()
    store.destroy()
    resolveOld({ items: { search: 'Alice private' } })
    await starting
    expect(document.querySelector('input').value).toBe('')
    document.querySelector('input').dispatchEvent(new Event('change', { bubbles: true }))
    expect(api.put).not.toHaveBeenCalled()
  })

  it('coalesces concurrent hydration for the same preference scope', async () => {
    document.body.innerHTML = '<form data-preference-region><input name="search"></form>'
    let finish
    const api = { get: vi.fn(() => new Promise(resolve => { finish = resolve })), put: vi.fn() }
    const store = createPreferenceStore({ root: document, api })

    const first = store.start()
    const second = store.start()
    expect(api.get).toHaveBeenCalledOnce()
    finish({ items: { search: 'Apollo' } })
    await Promise.all([first, second])
    expect(document.querySelector('[name="search"]').value).toBe('Apollo')
    store.destroy()
  })

  it('restores and saves standard controls only inside preference regions', async () => {
    document.body.innerHTML = `<form data-preference-region><input name="search"><input id="enabled" type="checkbox"></form><input name="outside">`
    const api = { get: vi.fn().mockResolvedValue({ items: { search: 'apollo', enabled: true } }), put: vi.fn().mockResolvedValue({}) }
    const store = createPreferenceStore({ root: document, api, debounceMs: 0 }); await store.start()
    expect(document.querySelector('[name=search]').value).toBe('apollo'); expect(document.querySelector('#enabled').checked).toBe(true)
    const search = document.querySelector('[name=search]'); search.value = 'zeus'; search.dispatchEvent(new Event('input', { bubbles: true }))
    await vi.waitFor(() => expect(api.put).toHaveBeenCalledWith('wifi-database/rvr', expect.objectContaining({ search: 'zeus' })))
    document.querySelector('[name=outside]').dispatchEvent(new Event('input', { bubbles: true })); expect(api.put).toHaveBeenCalledTimes(1)
  })

  it('restores dynamically inserted controls without per-control code', async () => {
    document.body.innerHTML = '<div data-preference-region></div>'
    const api = { get: vi.fn().mockResolvedValue({ items: { standard: ['11be'] } }), put: vi.fn() }
    const store = createPreferenceStore({ root: document, api }); await store.start()
    const select = document.createElement('select'); select.name = 'standard'; select.multiple = true
    select.innerHTML = '<option value="11ax">11ax</option><option value="11be">11be</option>'
    document.querySelector('[data-preference-region]').append(select)
    await vi.waitFor(() => expect(select.selectedOptions[0]?.value).toBe('11be'))
  })

  it('forces sensitive and unstable controls out and reports unstable ordinary controls', async () => {
    document.body.innerHTML = `<form data-preference-region><input type="password" name="password"><input name="apiToken"><input><input name="temporary" data-preference="off"></form>`
    const api = { get: vi.fn().mockResolvedValue({ items: {} }), put: vi.fn() }
    const store = createPreferenceStore({ root: document, api }); await store.start()
    expect(store.audit()).toEqual([document.querySelectorAll('input')[2]])
    for (const input of document.querySelectorAll('input')) input.dispatchEvent(new Event('change', { bubbles: true }))
    expect(api.put).not.toHaveBeenCalled()
  })

  it('keeps failed writes pending, shows unsynced status, and retries', async () => {
    document.body.innerHTML = '<form data-preference-region><input name="search"></form>'
    const api = { get: vi.fn().mockResolvedValue({ items: {} }), put: vi.fn().mockRejectedValueOnce(new Error('offline')).mockResolvedValue({}) }
    const store = createPreferenceStore({ root: document, api, debounceMs: 0 }); await store.start()
    const input = document.querySelector('input'); input.value = 'retry'; input.dispatchEvent(new Event('input', { bubbles: true }))
    await vi.waitFor(() => expect(document.querySelector('[data-preference-sync]').textContent).toContain('尚未同步'))
    await store.retry(); expect(api.put).toHaveBeenLastCalledWith('wifi-database/rvr', { search: 'retry' })
    expect(document.querySelector('[data-preference-sync]').textContent).toBe('')
  })

  it('uses the common adapter for theme buttons', async () => {
    document.body.innerHTML = `<div data-preference-region data-preference-scope="global"><button data-preference-key="theme" data-preference-value="light"></button><button data-preference-key="theme" data-preference-value="dark"></button></div>`
    const api = { get: vi.fn().mockResolvedValue({ items: { theme: 'dark' } }), put: vi.fn().mockResolvedValue({}) }
    const store = createPreferenceStore({ root: document, api }); await store.start()
    expect(document.querySelector('[data-preference-value=dark]').getAttribute('aria-pressed')).toBe('true')
    document.querySelector('[data-preference-value=light]').click()
    await vi.waitFor(() => expect(api.put).toHaveBeenCalledWith('global', { theme: 'light' }))
  })
})
