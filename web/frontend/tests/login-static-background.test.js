// @vitest-environment jsdom
import { expect, it } from 'vitest'
import { readFileSync, existsSync } from 'node:fs'

it('loads the white static background without starting the old animated board', async () => {
  document.body.innerHTML = readFileSync('login.html', 'utf8')
  const style = document.createElement('style')
  style.textContent = readFileSync('src/smarttest-theme.css', 'utf8')
  document.head.append(style)
  await import('../src/login-main.js')
  const surface = document.querySelector('[data-login-board]')
  expect(getComputedStyle(surface).backgroundSize).toBe('min(100vw, 1672px, 177.68svh) auto')
  expect(surface.querySelector('svg, canvas, [data-signal]')).toBeNull()
  expect(getComputedStyle(surface).getPropertyValue('--login-art')).toContain('/images/login-pcb-white-v1.png')
  expect(existsSync('public/images/login-pcb-white-v1.png')).toBe(true)
  document.documentElement.classList.add('dark-theme')
  expect(getComputedStyle(surface).getPropertyValue('--login-art')).toContain('/images/login-pcb-dark-v1.png')
  expect(existsSync('public/images/login-pcb-dark-v1.png')).toBe(true)
  document.documentElement.classList.remove('dark-theme')
  expect(document.querySelector('[data-login-form]')).not.toBeNull()
  style.remove()
})
