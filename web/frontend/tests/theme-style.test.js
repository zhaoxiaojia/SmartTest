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

it('colors distribution labels by their reusable presentation slots', () => {
  const style = document.createElement('style')
  style.textContent = readFileSync(resolve(import.meta.dirname, '../src/smarttest-theme.css'), 'utf8')
  document.head.append(style)
  const distribution = document.createElement('div')
  distribution.className = 'label-distribution'
  for (const slot of [0, 1, 0, 2, 3, 4, 5, 6, 7]) {
    const label = document.createElement('span')
    label.className = 'distribution-label'
    label.dataset.colorSlot = String(slot)
    label.textContent = slot % 2 ? 'same' : 'different'
    distribution.append(label)
  }
  document.body.append(distribution)

  const colors = [...distribution.children].map(label => {
    const computed = getComputedStyle(label)
    return `${computed.color}|${computed.backgroundColor}`
  })
  expect(colors[2]).toBe(colors[0])
  expect(new Set(colors.filter((_, index) => index !== 2))).toHaveLength(8)
})
