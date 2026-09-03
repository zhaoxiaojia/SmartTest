import { describe, expect, it } from 'vitest'

import config from '../vite.config.js'

describe('Vite development server', () => {
  it('forwards API requests to the FastAPI development server', () => {
    expect(config.server.proxy['/api'].target).toBe('http://127.0.0.1:8000')
  })

  it('builds Projects as the only project page', () => {
    expect(config.build.rollupOptions.input.projects).toMatch(/projects\.html$/)
    expect(config.build.rollupOptions.input).not.toHaveProperty('confluence')
  })
})
