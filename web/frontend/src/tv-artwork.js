let nextScreen = 0
const positions = [[20, 31, 240, -5], [73, 27, 280, 4], [49, 76, 230, -2]]

export function createTvProduct(index) {
  const [x, y, width, angle] = positions[index]
  const id = `tv-screen-${++nextScreen}`
  const product = document.createElement('span')
  product.className = 'tv-product'
  product.style.cssText = `left:${x}%;top:${y}%;--tv-width:${width}px;--tv-angle:${angle}deg;--tv-period:${12 + index * 3.7}s;--tv-phase:${-index * 4.3}s`
  product.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 154" aria-hidden="true">
    <defs>
      <clipPath id="${id}"><rect x="8" y="8" width="224" height="126" rx="3"/></clipPath>
      <linearGradient id="${id}-silk" x1="0" y1="1" x2="1" y2="0"><stop stop-color="#1452d6" stop-opacity="0"/><stop offset=".22" stop-color="#3477ff"/><stop offset=".48" stop-color="#8846ef"/><stop offset=".68" stop-color="#27dfdf"/><stop offset=".82" stop-color="#ff9d56" stop-opacity=".65"/><stop offset="1" stop-color="#498be9" stop-opacity="0"/></linearGradient>
      <linearGradient id="${id}-shine" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#8cfbff" stop-opacity="0"/><stop offset=".5" stop-color="#b8f5ff" stop-opacity=".9"/><stop offset="1" stop-color="#8797ff" stop-opacity="0"/></linearGradient>
    </defs>
    <path d="M88 146l13-13h38l13 13M78 149h84" fill="none" stroke="#24364a" stroke-width="4" stroke-linecap="round"/>
    <rect x="3" y="3" width="234" height="136" rx="6" fill="#101925" stroke="#3d5066" stroke-width="1.5"/>
    <rect x="8" y="8" width="224" height="126" rx="3" fill="#091526"/>
    <g clip-path="url(#${id})">
      <path class="tv-ribbon tv-ribbon-back" d="M-50 103C26-24 67 144 141 47S237 29 301-17L302 67C225 145 199 45 128 114S24 56-50 160Z" fill="url(#${id}-silk)"/>
      <path class="tv-ribbon tv-ribbon-front" d="M-40 159C19 48 65 104 121 51S215 90 291-11L301 51C236 148 192 49 124 109S32 97-32 191Z" fill="url(#${id}-silk)"/>
      <path class="tv-highlight" d="M-25 116C36 26 76 122 138 56S225 72 278 0L280 12C220 95 191 33 139 72S53 59-20 128Z" fill="url(#${id}-shine)"/>
    </g>
    <circle cx="120" cy="137" r="1" fill="#74d3de"/>
  </svg>`
  return product
}
