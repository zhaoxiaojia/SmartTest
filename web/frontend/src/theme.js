const chartThemes = new WeakMap()

export function initializeChartTheme(Chart) {
  if (chartThemes.has(Chart)) return chartThemes.get(Chart)
  const original = Chart.defaults.color
  Chart.defaults.color = () => getComputedStyle(document.documentElement).getPropertyValue('--text-primary').trim()
  function refresh() {
    for (const chart of Object.values(Chart.instances)) chart.update('none')
  }
  refresh()
  window.addEventListener('theme:changed', refresh)
  const stop = () => {
    window.removeEventListener('theme:changed', refresh)
    chartThemes.delete(Chart)
    Chart.defaults.color = original
  }
  chartThemes.set(Chart, stop)
  return stop
}

export function initializeTheme() {
  const key = 'smarttest:theme'
  function apply(theme, persist = true) {
    const dark = theme === 'dark'
    document.documentElement.classList.toggle('dark-theme', dark)
    document.body?.classList.toggle('dark-theme', dark)
    for (const input of document.querySelectorAll('.theme-toggle input')) input.checked = dark
    window.dispatchEvent(new CustomEvent('theme:changed', { detail: { theme: dark ? 'dark' : 'light' } }))
    if (persist) {
      try { localStorage.setItem(key, dark ? 'dark' : 'light') } catch { /* optional first-paint hint */ }
    }
  }
  function clear() {
    try { localStorage.removeItem(key) } catch { /* optional first-paint hint */ }
    apply('light', false)
  }
  globalThis.SmartTestTheme = { apply, clear }
  try {
    const theme = localStorage.getItem(key)
    if (theme === 'dark' || theme === 'light') apply(theme, false)
  } catch { /* unavailable storage retains the existing default */ }
}
