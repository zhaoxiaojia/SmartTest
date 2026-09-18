const PREFIXES = Object.freeze({
  projects: 'smarttest:projects-display:',
  jiraSelfTest: 'smarttest:jira-self-test-display:',
})

export function createDisposableDisplayCache(scope, account, cardKey = '') {
  const key = account ? `${PREFIXES[scope]}${encodeURIComponent(String(account).trim().toLocaleLowerCase())}${cardKey ? `:${encodeURIComponent(cardKey)}` : ''}` : ''
  return {
    read() { try { return key ? JSON.parse(sessionStorage.getItem(key)) : null } catch { return null } },
    write(payload) { try { if (key) sessionStorage.setItem(key, JSON.stringify(payload)) } catch { /* optional display acceleration */ } },
  }
}

export function clearDisposableDisplayState() {
  for (let index = sessionStorage.length - 1; index >= 0; index -= 1) {
    const key = sessionStorage.key(index)
    if (Object.values(PREFIXES).some(prefix => key?.startsWith(prefix))) sessionStorage.removeItem(key)
  }
}
