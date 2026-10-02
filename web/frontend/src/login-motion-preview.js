import { mountLoginMotion } from './login-background.js'

const preview = document.querySelector('.motion-preview')
mountLoginMotion(preview)
const effects = document.querySelectorAll('[data-effect]')
const pause = document.querySelector('[data-preview-pause]')

for (const button of effects) {
  button.addEventListener('click', () => {
    preview.dataset.motion = button.dataset.effect
    for (const choice of effects) choice.setAttribute('aria-pressed', String(choice === button))
  })
}
pause.addEventListener('click', () => {
  const paused = pause.getAttribute('aria-pressed') !== 'true'
  pause.setAttribute('aria-pressed', String(paused))
  pause.textContent = paused ? '播放' : '暂停'
  syncPlayback()
})
document.querySelector('[data-preview-theme]').addEventListener('click', () => {
  globalThis.SmartTestTheme.apply(document.documentElement.classList.contains('dark-theme') ? 'light' : 'dark')
})
function syncPlayback() {
  preview.classList.toggle('motion-paused', pause.getAttribute('aria-pressed') === 'true')
}
syncPlayback()
