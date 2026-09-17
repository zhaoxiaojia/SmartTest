// @vitest-environment jsdom
import { expect, it, vi } from 'vitest'
import { createRankingCard } from '../src/widgets/ranking-card.js'

it('keeps dimension groups independent while querying both selected values', () => {
  const root = document.createElement('div')
  const rowsFor = vi.fn(() => [])
  const config = { productLines: [{ value: 'a', label: 'A' }, { value: 'b', label: 'B' }],
    modes: [{ value: 'x', label: 'X' }, { value: 'y', label: 'Y' }], rowsFor }
  const card = createRankingCard()
  card.mount(root, config)
  const products = [...root.querySelectorAll('[data-product-line-segments] button')]
  const modes = [...root.querySelectorAll('[data-mode-segments] button')]
  modes[1].click()
  expect([...root.querySelectorAll('[data-product-line-segments] button')]).toEqual(products)
  expect(products[0].classList.contains('active')).toBe(true)
  expect(rowsFor).toHaveBeenLastCalledWith('a', 'y')
  products[1].click()
  expect([...root.querySelectorAll('[data-mode-segments] button')]).toEqual(modes)
  expect(modes[1].classList.contains('active')).toBe(true)
  expect(rowsFor).toHaveBeenLastCalledWith('b', 'y')
  card.update({ ...config })
  expect([...root.querySelectorAll('[data-product-line-segments] button')]).toEqual(products)
  card.destroy()
})
