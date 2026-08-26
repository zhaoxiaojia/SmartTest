export function safeReturnPath(value) {
  const path = `${value || ''}`
  return path.startsWith('/') && !path.startsWith('//') ? path : '/'
}

export function createLoginPage({ root = document, api, navigate = path => window.location.assign(path) }) {
  const form = root.querySelector('[data-login-form]')
  const status = form.querySelector('[data-auth-status]')
  const destination = safeReturnPath(new URLSearchParams(window.location.search).get('next'))

  form.addEventListener('submit', async event => {
    event.preventDefault()
    const submit = form.querySelector('[type="submit"]')
    status.textContent = 'Signing in…'; submit.disabled = true
    try {
      await api.login(form.elements.username.value, form.elements.password.value)
      form.elements.password.value = ''
      navigate(destination)
    } catch {
      form.elements.password.value = ''
      status.textContent = 'Sign in failed. Check your account or connection.'
    } finally {
      submit.disabled = false
    }
  })

  return {
    async start() {
      try {
        const session = await api.session()
        if (session.authenticated) navigate(destination)
      } catch {
        // The form remains usable and reports any subsequent login failure.
      }
    }
  }
}
