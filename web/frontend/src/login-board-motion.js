// Routes traced on the shared 1672 × 941 login PCB artwork, CPU pin to endpoint pin.
const routes = [
  'M391 400 L369 403 L338 395 L310 382 L298 335 L291 318',
  'M661 316 L680 313 L694 304 L718 296 L740 291 L780 284',
]

export function boardCover(width, height, position = '50% 50%') {
  const scale = Math.max(width / 1672, height / 941)
  const [x = '50%', y = '50%'] = position.split(/\s+/)
  const fraction = value => value === 'center' ? .5 : parseFloat(value) / 100
  return { scale, x: (width - 1672 * scale) * fraction(x), y: (height - 941 * scale) * fraction(y) }
}

export function createLoginBoard(context) {
  const lines = routes.map(data => {
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path')
    path.setAttribute('d', data)
    const length = path.getTotalLength()
    return Array.from({ length: 257 }, (_, index) => path.getPointAtLength(length * index / 256))
  })
  let cachedDpr
  let sprites
  function prepare(dpr) {
    sprites = ['#00a9ed', '#6feaff', '#b4a4ff'].map(color => {
      const canvas = document.createElement('canvas')
      canvas.width = canvas.height = Math.ceil(40 * dpr)
      const paint = canvas.getContext('2d')
      const gradient = paint.createRadialGradient(20 * dpr, 20 * dpr, 0, 20 * dpr, 20 * dpr, 20 * dpr)
      gradient.addColorStop(0, '#ffffff')
      gradient.addColorStop(.12, color)
      gradient.addColorStop(.35, `${color}80`)
      gradient.addColorStop(1, `${color}00`)
      paint.fillStyle = gradient
      paint.fillRect(0, 0, canvas.width, canvas.height)
      return canvas
    })
    cachedDpr = dpr
  }
  return (mapping, now, dark, dpr, animate) => {
    if (!animate) return
    if (cachedDpr !== dpr) prepare(dpr)
    const point = (line, phase) => line[Math.round(Math.min(1, Math.max(0, phase)) * 256)]
    function pulse(location, alpha, radius, returning = false) {
      context.globalAlpha = alpha
      context.drawImage(sprites[returning ? 2 : dark ? 1 : 0], mapping.x + location.x * mapping.scale - radius, mapping.y + location.y * mapping.scale - radius, radius * 2, radius * 2)
    }
    for (const [index, line] of lines.entries()) {
      const phase = ((now + index * 4100) % 10000) / 10000
      if (phase < .12) pulse(line[0], Math.sin(phase / .12 * Math.PI), 22)
      else if (phase < .42) {
        const progress = (phase - .12) / .3
        for (let tail = 4; tail >= 0; tail--) pulse(point(line, progress - tail * .017), 1 - tail * .18, 10 - tail)
      } else if (phase < .56) pulse(line[256], Math.sin((phase - .42) / .14 * Math.PI), 25)
      else if (phase < .86) {
        const progress = 1 - (phase - .56) / .3
        for (let tail = 4; tail >= 0; tail--) pulse(point(line, progress + tail * .017), 1 - tail * .18, 10 - tail, true)
      } else if (phase < .96) pulse(line[0], Math.sin((phase - .86) / .1 * Math.PI), 22, true)
    }
    context.globalAlpha = 1
  }
}
