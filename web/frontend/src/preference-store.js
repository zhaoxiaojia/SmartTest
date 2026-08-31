const SENSITIVE = /password|passwd|secret|token|cookie|credential|authorization/i
const EXCLUDED_TYPES = new Set(['password', 'hidden', 'file', 'submit', 'reset', 'button', 'image'])
const STANDARD = 'input, textarea, select'

function regionOf(element) { return element.closest?.('[data-preference-region]') }
function scopeOf(element, defaultScope) { return (regionOf(element)?.dataset.preferenceScope || defaultScope).replace(/^\/+/, '') }
function keyOf(element) { return element.dataset?.preferenceKey || element.name || element.id || '' }
function eligible(element) {
  if (!regionOf(element) || element.dataset?.preference === 'off') return false
  const key = keyOf(element)
  if (!key || SENSITIVE.test(key)) return false
  if (element.matches?.(STANDARD) && EXCLUDED_TYPES.has(element.type)) return false
  return element.matches?.(STANDARD) || Boolean(element.dataset?.preferenceKey && element.dataset?.preferenceValue)
}
function read(element) {
  if (element.dataset?.preferenceValue != null) return element.dataset.preferenceValue
  if (element.type === 'checkbox') {
    const peers = [...regionOf(element).querySelectorAll('input[type="checkbox"]')].filter(peer => keyOf(peer) === keyOf(element))
    return peers.length > 1 ? peers.filter(peer => peer.checked).map(peer => peer.value) : element.checked
  }
  if (element.type === 'radio') return element.checked ? element.value : undefined
  if (element.tagName === 'SELECT' && element.multiple) return [...element.selectedOptions].map(option => option.value)
  return element.value
}
function restore(element, value) {
  if (element.dataset?.preferenceValue != null) {
    const active = `${value}` === element.dataset.preferenceValue
    element.setAttribute('aria-pressed', `${active}`); element.classList.toggle('active', active)
  } else if (element.type === 'checkbox') element.checked = Array.isArray(value) ? value.map(String).includes(element.value) : Boolean(value)
  else if (element.type === 'radio') element.checked = `${element.value}` === `${value}`
  else if (element.tagName === 'SELECT' && element.multiple) {
    const values = new Set(Array.isArray(value) ? value.map(String) : [])
    for (const option of element.options) option.selected = values.has(option.value)
    element._multiSelect?.syncFromSelect?.()
  } else if (value != null) element.value = `${value}`
  element.dispatchEvent(new CustomEvent('preference:restored', { bubbles: true, detail: { value } }))
}

export function createPreferenceStore({ root = document, api, route = () => window.location.pathname, debounceMs = 300 } = {}) {
  const values = new Map(); const timers = new Map(); const pending = new Map(); const flights = new Map()
  let observer; let status
  const scopeValues = scope => {
    if (!values.has(scope)) values.set(scope, {})
    return values.get(scope)
  }
  const ensureStatus = () => {
    if (!status) { status = document.createElement('div'); status.dataset.preferenceSync = ''; status.className = 'preference-sync-status'; status.setAttribute('aria-live', 'polite'); document.body.append(status) }
    return status
  }
  async function loadScope(scope) {
    if (values.has(scope)) return scopeValues(scope)
    try { values.set(scope, (await api.get(scope)).items || {}) } catch { values.set(scope, {}) }
    return scopeValues(scope)
  }
  async function flush(scope) {
    if (flights.has(scope)) return flights.get(scope)
    let failed = false
    const flight = (async () => {
      while (pending.has(scope)) {
        const batch = pending.get(scope); pending.delete(scope)
        try { await api.put(scope, batch); ensureStatus().textContent = '' }
        catch {
          failed = true
          pending.set(scope, { ...batch, ...(pending.get(scope) || {}) })
          ensureStatus().textContent = '设置尚未同步，恢复连接后可重试。'; break
        }
      }
    })().finally(() => {
      flights.delete(scope)
      if (!failed && pending.has(scope)) void flush(scope)
    })
    flights.set(scope, flight)
    return flight
  }
  function schedule(scope, key, value, delayed) {
    scopeValues(scope)[key] = value
    pending.set(scope, { ...(pending.get(scope) || {}), [key]: value })
    clearTimeout(timers.get(scope))
    if (delayed) timers.set(scope, setTimeout(() => flush(scope), debounceMs))
    else void flush(scope)
  }
  async function hydrate(container = root) {
    const controls = [...(container.matches?.(`${STANDARD}, [data-preference-key][data-preference-value]`) ? [container] : []),
      ...container.querySelectorAll?.(`${STANDARD}, [data-preference-key][data-preference-value]`) || []]
    const scopes = [...new Set(controls.filter(eligible).map(item => scopeOf(item, route())))]
    await Promise.all(scopes.map(loadScope))
    for (const control of controls.filter(eligible)) {
      const saved = scopeValues(scopeOf(control, route()))
      if (Object.hasOwn(saved, keyOf(control))) restore(control, saved[keyOf(control)])
    }
  }
  function handle(event) {
    const reset = event.target.closest?.('[data-preference-reset]')
    if (reset && regionOf(reset)) {
      const scope = scopeOf(reset, route()); pending.delete(scope); values.set(scope, {})
      void api.reset(scope).catch(() => { ensureStatus().textContent = '设置尚未同步，恢复连接后可重试。' })
      return
    }
    const control = event.target.closest?.(`${STANDARD}, [data-preference-key][data-preference-value]`)
    if (!control || !eligible(control)) return
    if (control.dataset?.preferenceValue != null && event.type !== 'click') return
    const value = read(control); if (value === undefined) return
    const delayed = event.type === 'input' && ['text', 'search', 'date', 'email', 'number', ''].includes(control.type)
    schedule(scopeOf(control, route()), keyOf(control), value, delayed)
    if (control.dataset?.preferenceValue != null) {
      for (const peer of regionOf(control).querySelectorAll('[data-preference-key]')) {
        if (keyOf(peer) === keyOf(control)) restore(peer, value)
      }
    }
  }
  return {
    async start() {
      ensureStatus(); await hydrate()
      root.addEventListener('input', handle); root.addEventListener('change', handle); root.addEventListener('click', handle)
      observer = new MutationObserver(records => records.forEach(record => {
        if (record.target.nodeType === 1) void hydrate(record.target)
        record.addedNodes.forEach(node => { if (node.nodeType === 1) void hydrate(node) })
      }))
      observer.observe(root.documentElement || root, { childList: true, subtree: true })
    },
    retry: async () => Promise.all([...pending.keys()].map(flush)),
    audit() {
      return [...root.querySelectorAll('[data-preference-region] input, [data-preference-region] textarea, [data-preference-region] select')]
        .filter(element => element.dataset.preference !== 'off' && !EXCLUDED_TYPES.has(element.type) && !SENSITIVE.test(keyOf(element)) && !keyOf(element))
    },
    destroy() { observer?.disconnect(); root.removeEventListener('input', handle); root.removeEventListener('change', handle); root.removeEventListener('click', handle) }
  }
}
