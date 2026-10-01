// @vitest-environment jsdom
import { expect, it } from 'vitest'
import { boardCover } from '../src/login-board-motion.js'

it('maps PCB points with the same centered cover crop as the desktop background', () => {
  expect(boardCover(1672, 941)).toEqual({ scale: 1, x: 0, y: 0 })
  const cover = boardCover(1000, 941)
  expect(cover.scale).toBe(1)
  expect(cover.x).toBe(-336)
  expect(cover.y).toBe(0)
})

it('uses the mobile background position for the same artwork geometry', () => {
  const cover = boardCover(390, 844, '25% center')
  expect(cover.scale).toBeCloseTo(844 / 941)
  expect(cover.x).toBeCloseTo((390 - 1672 * cover.scale) * .25)
  expect(cover.y).toBeCloseTo(0)
})
