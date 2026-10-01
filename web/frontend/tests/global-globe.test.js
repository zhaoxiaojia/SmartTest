// @vitest-environment jsdom
import { expect, it, vi } from 'vitest'
import { geoDistance } from 'd3-geo'
import { createGlobalGlobe, globalLocations } from '../src/global-globe.js'

it('hides rear hemisphere markers, rotates the geography and bounds visible labels', () => {
  const gradient = { addColorStop() {} }
  const points = []
  const labels = []
  const context = { save() {}, restore() {}, beginPath() {}, clip() {}, fill() {}, stroke() {}, moveTo() {}, lineTo() {}, closePath() {},
    arc: vi.fn((...args) => points.push(args)), createRadialGradient: () => gradient,
    measureText: text => ({ width: text.length * 5 }), fillText: text => labels.push(text) }
  const draw = createGlobalGlobe(context)
  draw(900, 430, 0, false)
  const front = globalLocations.filter(location => geoDistance(location.coordinates, [110, 18]) < Math.PI / 2)
  // Small-radius arcs are city markers; the sphere outline is much larger.
  expect(points.filter(point => point[2] <= 3.2)).toHaveLength(front.length)
  expect(labels.filter(label => /^(Office|Customer)/.test(label)).length).toBeLessThanOrEqual(2)
  expect(labels).toContain('Asia')
  expect(labels).not.toContain('North America')
  const initial = points.filter(point => point[2] <= 3.2)
  points.length = labels.length = 0
  draw(900, 430, 90000, true)
  expect(points.filter(point => point[2] <= 3.2)).not.toEqual(initial)
  expect(labels.filter(label => /^(Office|Customer)/.test(label)).length).toBeLessThanOrEqual(2)
  expect(labels).toContain('North America')
  expect(labels).not.toContain('Asia')
  points.length = labels.length = 0
  draw(140, 42, 100000, false)
  expect(labels).toHaveLength(0)
})
