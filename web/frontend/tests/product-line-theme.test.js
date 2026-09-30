// @vitest-environment jsdom
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { afterEach, expect, it } from 'vitest'

function mountProductLineTheme() {
  const source = readFileSync(resolve(import.meta.dirname, '../src/product-line-theme.css'), 'utf8')
  const wirelessRule = source.match(/\[data-product-line="Wireless Connection"\]\[data-product-surface\] \{[^}]+\}/)?.[0]
  const darkWirelessRule = source.match(/\.dark-theme \[data-product-line="Wireless Connection"\]\[data-product-surface\] \{[^}]+\}/)?.[0]
  const compactRule = source.match(/\[data-product-line="Wireless Connection"\]\[data-product-surface\]:is\([^}]+\}/)?.[0]
  const layoutRule = source.match(/\[data-product-line="Wireless Connection"\]\[data-product-surface="layout"\] \{[^}]+\}/)?.[0]
  const nestedRule = source.match(/\[data-product-surface="layout"\] \[data-product-line\]\[data-product-surface\]:not\(\[data-product-surface="layout"\]\) \{[^}]+\}/)?.[0]
  const transparentDisclosureRule = source.match(/\[data-product-surface="layout"\] \[data-product-surface="disclosure"\] \{[^}]+\}/)?.[0]
  const transparentGroupRule = source.match(/\[data-product-surface="layout"\] :is\(\.stage-group, \.launch-os-group, \.stage-summary, \.launch-os-summary\) \{[^}]+\}/)?.[0]
  const motionRule = source.match(/@keyframes product-ofdm-flow \{[\s\S]*?\n\}/)?.[0]
  expect(wirelessRule && darkWirelessRule && compactRule && layoutRule && nestedRule && transparentDisclosureRule && transparentGroupRule && motionRule).toBeTruthy()
  const style = document.createElement('style')
  style.textContent = `.stage-summary { background: rgb(255, 255, 255); }\n${wirelessRule}\n${compactRule}\n${layoutRule}\n${darkWirelessRule}\n${nestedRule}\n${transparentDisclosureRule}\n${transparentGroupRule}\n${motionRule}`
  document.head.append(style)
  return style.sheet
}

afterEach(() => {
  document.head.innerHTML = ''
  document.body.innerHTML = ''
  document.documentElement.className = ''
})

it('uses the Wireless OFDM motion across every supported product surface', () => {
  const sheet = mountProductLineTheme()
  const surfaces = ['layout', 'card', 'button', 'badge', 'disclosure'].map(surface => {
    const element = document.createElement(surface === 'button' ? 'button' : 'div')
    element.dataset.productLine = 'Wireless Connection'
    element.dataset.productSurface = surface
    document.body.append(element)
    return element
  })

  for (const [index, surface] of surfaces.entries()) {
    const computed = getComputedStyle(surface)
    expect(computed.getPropertyValue('--product-motion').trim()).toBe('product-ofdm-flow 9.5s linear infinite')
    const expectedSize = index < 2 ? '480px 120px' : '240px 60px'
    expect(computed.getPropertyValue('--product-motion-size').trim()).toBe(expectedSize)
    expect(computed.backgroundRepeat).toBe('repeat-x')
  }
  const motion = [...sheet.cssRules].find(rule => rule.name === 'product-ofdm-flow')
  expect([...motion.cssRules].map(rule => [rule.keyText, rule.style.getPropertyValue('background-position')])).toEqual([
    ['from', '0 50%'],
    ['to', 'var(--product-ofdm-shift) 50%'],
  ])

  const child = document.createElement('article')
  child.dataset.productLine = 'Wireless Connection'
  child.dataset.productSurface = 'disclosure'
  surfaces[0].append(child)
  expect(getComputedStyle(child).getPropertyValue('--product-motion').trim()).toBe('none')
  expect(getComputedStyle(child).backgroundImage).toBe('none')
  expect(getComputedStyle(child).backgroundColor).toBe('rgba(0, 0, 0, 0)')

  const stageGroup = document.createElement('section')
  stageGroup.className = 'stage-group'
  const stageSummary = document.createElement('summary')
  stageSummary.className = 'stage-summary'
  stageGroup.append(stageSummary)
  surfaces[0].append(stageGroup)
  expect(getComputedStyle(stageGroup).backgroundColor).toBe('rgba(0, 0, 0, 0)')
  expect(getComputedStyle(stageSummary).backgroundColor).toBe('rgba(0, 0, 0, 0)')

  document.documentElement.classList.add('dark-theme')
  expect(getComputedStyle(surfaces[0]).getPropertyValue('--product-motion-pattern')).toContain('wireless-ofdm-dark.svg')
  expect(getComputedStyle(child).getPropertyValue('--product-motion-pattern').trim()).toBe('none')
  expect(getComputedStyle(child).backgroundImage).toBe('none')
})
