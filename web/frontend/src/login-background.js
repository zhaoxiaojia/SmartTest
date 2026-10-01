export const LOGIN_BACKGROUNDS = [
  { id: 'pcb' },
]

const STORAGE_KEY = 'smarttest.login.background'

export function selectLoginBackground({ backgrounds = LOGIN_BACKGROUNDS, storage = sessionStorage, random = Math.random } = {}) {
  if (!backgrounds.length) return ''
  let stored
  try { stored = storage.getItem(STORAGE_KEY) } catch { /* Storage may be unavailable in hardened browsers. */ }
  if (backgrounds.some(background => background.id === stored)) return stored
  const selected = backgrounds[Math.min(backgrounds.length - 1, Math.floor(random() * backgrounds.length))].id
  try { storage.setItem(STORAGE_KEY, selected) } catch { /* The selected background still works for this page load. */ }
  return selected
}

export function applyLoginBackground({ root = document, backgrounds = LOGIN_BACKGROUNDS, storage, random } = {}) {
  const surface = root.querySelector('[data-login-board]')
  if (!surface) return ''
  const id = selectLoginBackground({ backgrounds, storage: storage ?? sessionStorage, random })
  surface.dataset.loginBackground = id
  return id
}
