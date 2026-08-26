export function createAuthShell({ root = document, desktopHost, mobileHost, api }) {
  let state = { authenticated: false }
  const userNode = () => {
    if (!state.authenticated) {
      const login = document.createElement('a')
      const current = `${window.location.pathname}${window.location.search}${window.location.hash}`
      login.className = 'button button-secondary user-login'; login.dataset.login = ''
      login.href = `/login.html?next=${encodeURIComponent(current)}`; login.textContent = 'Sign in'
      return login
    }
    const label = `${state.displayName || state.username || ''}`
    const menu = document.createElement('div'); menu.className = 'user-menu'
    const trigger = document.createElement('button'); trigger.className = 'user-trigger'; trigger.dataset.userTrigger = ''; trigger.type = 'button'
    const avatar = document.createElement('span'); avatar.className = 'user-avatar'; avatar.dataset.userAvatar = ''
    if (state.avatarUrl) {
      const image = document.createElement('img'); image.setAttribute('src', `${state.avatarUrl}`); image.alt = ''; avatar.append(image)
    } else {
      avatar.textContent = (label.trim()[0] || '?').toUpperCase()
    }
    const name = document.createElement('span'); name.dataset.userName = ''; name.textContent = label
    const logout = document.createElement('button'); logout.className = 'user-logout'; logout.dataset.logout = ''; logout.type = 'button'; logout.hidden = true; logout.textContent = 'Sign out'
    trigger.append(avatar, name); menu.append(trigger, logout)
    return menu
  }
  const render = () => {
    desktopHost.replaceChildren(userNode()); mobileHost.replaceChildren(userNode())
    const greeting = root.querySelector?.('#greeting')
    if (greeting) {
      const base = greeting.dataset.greetingBase || greeting.textContent.trim()
      greeting.dataset.greetingBase = base
      greeting.textContent = state.authenticated && state.username ? `${base}, ${state.username}` : base
    }
  }
  root.addEventListener('click', async event => {
    const trigger = event.target.closest('[data-user-trigger]')
    if (trigger) { const logout = trigger.parentElement.querySelector('[data-logout]'); logout.hidden = !logout.hidden }
    if (event.target.closest('[data-logout]') && api) { await api.logout(); state = { authenticated: false }; render() }
  })
  return {
    async start() {
      if (api) { try { state = await api.session() } catch { state = { authenticated: false } } }
      render()
    }
  }
}
