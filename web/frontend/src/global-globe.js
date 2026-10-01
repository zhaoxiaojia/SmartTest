import { geoDistance, geoGraticule10, geoOrthographic, geoPath } from 'd3-geo'
import boundaries from './geo/global-boundaries.json'

const geographyLabels = [
  ['North America', -105, 45], ['South America', -60, -15], ['Europe', 18, 53],
  ['Africa', 20, 5], ['Asia', 95, 43], ['Australia', 134, -25], ['Antarctica', 0, -78],
  ['Pacific Ocean', 160, 10], ['Pacific Ocean', -140, 5], ['Atlantic Ocean', -35, 20],
  ['Indian Ocean', 75, -20], ['Arctic Ocean', 0, 78], ['Southern Ocean', 90, -58],
]

// City centers, not building addresses; customer points represent headquarters only.
export const globalLocations = [
  ['Mountain View', -122.08, 37.39, 'US-06'], ['Bangalore', 77.59, 12.97, '356'],
  ['Seoul', 126.98, 37.57, '410'], ['Singapore', 103.82, 1.35, '702'],
  ['Tokyo', 139.69, 35.68, '392'], ['London', -.13, 51.51, '826'],
  ['Milan', 9.19, 45.46, '380'], ['Munich', 11.58, 48.14, '276'],
  ['Istanbul', 28.98, 41.01, '792'], ['Novi Sad', 19.83, 45.27, '688'],
  ['Paris', 2.35, 48.86, '250'], ['São Paulo', -46.63, -23.55, '076'],
  ['Hong Kong', 114.17, 22.32, '344'], ['Taipei', 121.57, 25.03, '158'],
].map(([name, longitude, latitude, region]) => ({ name, coordinates: [longitude, latitude], region, kind: 'office' }))
  .concat([
    ['Google · Mountain View', -122.08, 37.39, 'US-06'], ['Amazon · Seattle', -122.33, 47.61, 'US-53'],
    ['Walmart · Bentonville', -94.21, 36.37, 'US-05'], ['Deutsche Telekom · Bonn', 7.1, 50.74, '276'],
    ['Sky · Isleworth', -.34, 51.47, '826'],
  ].map(([name, longitude, latitude, region]) => ({ name, coordinates: [longitude, latitude], region, kind: 'customer' })))

export function createGlobalGlobe(context) {
  const projection = geoOrthographic().clipAngle(90).precision(.7)
  const path = geoPath(projection, context)
  const graticule = geoGraticule10()
  const regions = new Map(boundaries.regions.map(region => [region.id, region]))
  let started
  return (width, height, now, dark) => {
    started ??= now
    const longitude = 110 + (now - started) / 500
    const radius = Math.min(width * .42, height * .86)
    const center = [width * .78, height * .73]
    projection.rotate([-longitude, -18]).scale(radius).translate(center).clipExtent([[0, 0], [width, height]])
    context.save()
    context.beginPath()
    context.arc(...center, radius, 0, Math.PI * 2)
    context.clip()
    const ocean = context.createRadialGradient(center[0] - radius * .35, center[1] - radius * .35, radius * .08, ...center, radius)
    ocean.addColorStop(0, dark ? '#234961' : '#d3e8ee')
    ocean.addColorStop(.75, dark ? '#102b40' : '#bbd5df')
    ocean.addColorStop(1, dark ? '#071725' : '#8eadbe')
    context.fillStyle = ocean
    context.fill()
    function paint(geometry, fill, stroke, alpha, lineWidth = .7) {
      context.globalAlpha = alpha
      context.beginPath()
      path(geometry)
      if (fill) { context.fillStyle = fill; context.fill() }
      if (stroke) { context.strokeStyle = stroke; context.lineWidth = lineWidth; context.stroke() }
    }
    paint(boundaries.land, dark ? '#55929a' : '#719eaa', dark ? '#89c0c7' : '#4a7c8c', .42)
    paint(boundaries.borders, null, dark ? '#b2d0d4' : '#426f82', .36, .6)
    paint(graticule, null, dark ? '#62a3b3' : '#487f95', .24, .5)
    if (width >= 600 && height >= 160) {
      const named = new Set()
      context.font = '10px system-ui, sans-serif'
      context.fillStyle = dark ? '#b7d6dd' : '#365c70'
      context.globalAlpha = .7
      for (const [name, lon, lat] of geographyLabels) {
        if (named.has(name) || geoDistance([lon, lat], [longitude, 18]) >= Math.PI / 2) continue
        const [x, y] = projection([lon, lat])
        const size = context.measureText(name).width
        if (x - size / 2 < 0 || x + size / 2 > width || y < 12 || y > height - 8) continue
        context.fillText(name, x - size / 2, y)
        named.add(name)
      }
    }
    const visible = globalLocations.filter(location => geoDistance(location.coordinates, [longitude, 18]) < Math.PI / 2)
    for (const kind of ['office', 'customer']) {
      const candidates = visible.filter(location => location.kind === kind)
      const active = candidates[Math.floor((now - started) / 6000) % candidates.length]
      const color = kind === 'office' ? (dark ? '#64d9e8' : '#007f9a') : (dark ? '#f0b880' : '#a45d35')
      if (active) paint(regions.get(active.region), null, color, .5 + .25 * Math.sin((now - started) / 1800), 1.2)
      for (const location of candidates) {
        const [x, y] = projection(location.coordinates)
        const front = Math.cos(geoDistance(location.coordinates, [longitude, 18]))
        context.globalAlpha = Math.min(1, front * 3) * (location === active ? .95 : .5)
        context.beginPath()
        context.arc(x, y, location === active ? 3.2 : 1.8, 0, Math.PI * 2)
        context.fillStyle = color
        context.fill()
        if (location !== active || width < 600 || height < 160 || front < .2 || y < 12 || y > height - 18) continue
        const label = `${kind === 'office' ? 'Office' : 'Customer'} · ${location.name}`
        context.font = '11px system-ui, sans-serif'
        const size = context.measureText(label).width
        context.globalAlpha = .85
        context.fillText(label, Math.max(8, Math.min(width - size - 8, x + 9)), y + (kind === 'office' ? -9 : 16))
      }
    }
    context.restore()
    context.globalAlpha = 1
  }
}
