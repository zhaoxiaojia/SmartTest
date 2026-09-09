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

it('cycles project status label colors every eight labels without reading their values', () => {
  const style = document.createElement('style')
  style.textContent = readFileSync(resolve(import.meta.dirname, '../src/smarttest-theme.css'), 'utf8')
  document.head.append(style)
  const distribution = document.createElement('div')
  distribution.className = 'label-distribution'
  for (let index = 0; index < 9; index += 1) {
    const label = document.createElement('span')
    label.className = 'distribution-label'
    label.textContent = index % 2 ? 'same' : 'different'
    distribution.append(label)
  }
  document.body.append(distribution)

  const colors = [...distribution.children].map(label => {
    const computed = getComputedStyle(label)
    return `${computed.color}|${computed.backgroundColor}`
  })
  expect(new Set(colors.slice(0, 8))).toHaveLength(8)
  expect(colors[8]).toBe(colors[0])
})
