export function initializeTheme() {
  const key = 'smarttest:theme'
  function apply(theme, persist = true) {
    const dark = theme === 'dark'
    document.documentElement.classList.toggle('dark-theme', dark)
    document.body?.classList.toggle('dark-theme', dark)
    for (const input of document.querySelectorAll('.theme-toggle input')) input.checked = dark
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
