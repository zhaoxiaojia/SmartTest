// @vitest-environment jsdom
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { expect, it } from 'vitest'

it('uses the document root as the conditional page-scroll owner', () => {
  const style = document.createElement('style')
  style.textContent = readFileSync(resolve(import.meta.dirname, '../src/smarttest-theme.css'), 'utf8')
  document.head.append(style)

  expect(getComputedStyle(document.documentElement).overflowY).toBe('auto')
})

it('keeps hidden stage groups visually collapsed', () => {
  const style = document.createElement('style')
  style.textContent = readFileSync(resolve(import.meta.dirname, '../src/smarttest-theme.css'), 'utf8')
  document.head.append(style)
  const stageGroups = document.createElement('div')
  stageGroups.className = 'stage-groups'
  stageGroups.hidden = true
  document.body.append(stageGroups)

  expect(getComputedStyle(stageGroups).display).toBe('none')
})

it('makes product line names larger than Current Stage headings', () => {
  const style = document.createElement('style')
  style.textContent = readFileSync(resolve(import.meta.dirname, '../src/smarttest-theme.css'), 'utf8')
  document.head.append(style)
  const productLine = document.createElement('strong')
  productLine.className = 'kanban-title'
  const stageSummary = document.createElement('summary')
  const stageHeading = document.createElement('strong')
  stageSummary.className = 'stage-summary'
  stageSummary.append(stageHeading)
  document.body.append(productLine, stageSummary)

  expect(getComputedStyle(productLine).fontSize).toBe('1rem')
  expect(getComputedStyle(stageHeading).fontSize).toBe('0.8125rem')
})

it('colors stages independently from project statuses', () => {
  const style = document.createElement('style')
  style.textContent = readFileSync(resolve(import.meta.dirname, '../src/smarttest-theme.css'), 'utf8')
  document.head.append(style)
  const distribution = document.createElement('div')
  distribution.className = 'label-distribution'
  for (const slot of [1, 2, 1, 3, 4, 5, 6, 7, 8, 9]) {
    const label = document.createElement('span')
    label.className = 'stage-summary'
    label.dataset.projectStage = String(slot)
    label.textContent = slot % 2 ? 'same' : 'different'
    distribution.append(label)
  }
  document.body.append(distribution)

  const colors = [...distribution.children].map(label => {
    const computed = getComputedStyle(label)
    const theme = getComputedStyle(document.documentElement)
    const resolveColor = value => theme.getPropertyValue(value.slice(4, -1)).trim()
    expect(computed.borderLeftWidth).toBe('3px')
    expect(computed.borderLeftStyle).toBe('solid')
    expect(resolveColor(computed.borderLeftColor)).toBe(resolveColor(computed.color))
    return `${resolveColor(computed.color)}|${resolveColor(computed.background)}`
  })
  expect(colors[2]).toBe(colors[0])
  expect(new Set(colors.filter((_, index) => index !== 2))).toHaveLength(8)
  expect(colors).toEqual([
    '#2457A7|#F0F5FF', '#237A52|#EFFAF4', '#2457A7|#F0F5FF',
    '#A85C00|#FFF5E8', '#806600|#FFFBE8', '#0052CC|#EDF3FF',
    '#00875A|#EDF8F3', '#A54832|#FFF2EF', '#42526E|#F1F3F6', '#42526E|#F1F3F6',
  ])
})

it('colors project statuses by their semantic meaning', () => {
  const style = document.createElement('style')
  style.textContent = readFileSync(resolve(import.meta.dirname, '../src/smarttest-theme.css'), 'utf8')
  document.head.append(style)
  const colors = ['block', 'warning', 'normal'].map(tone => {
    const label = document.createElement('span')
    label.className = 'distribution-label'
    label.dataset.statusTone = tone
    document.body.append(label)
    const computed = getComputedStyle(label)
    const theme = getComputedStyle(document.documentElement)
    const resolveColor = value => theme.getPropertyValue(value.slice(4, -1)).trim()
    return `${resolveColor(computed.color)}|${resolveColor(computed.background)}`
  })

  expect(new Set(colors)).toHaveLength(3)
  expect(colors).toEqual(['#FFFFFF|#BF2600', '#172B4D|#FF991F', '#FFFFFF|#00875A'])
})

it('preserves GridStack content insets instead of forcing widget content to item height', () => {
  const style = document.createElement('style')
  style.textContent = readFileSync(resolve(import.meta.dirname, '../src/smarttest-theme.css'), 'utf8')
  document.head.append(style)
  const workspace = document.createElement('div')
  workspace.className = 'dashboard-workspace'
  workspace.innerHTML = '<div class="grid-stack"><div class="grid-stack-item"><div class="grid-stack-item-content dashboard-widget-card"></div></div></div>'
  document.body.append(workspace)

  expect(getComputedStyle(workspace.querySelector('.dashboard-widget-card')).height).not.toBe('100%')
})
