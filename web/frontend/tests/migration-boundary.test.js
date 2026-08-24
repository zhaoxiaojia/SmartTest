import { readdir, readFile } from 'node:fs/promises'
import path from 'node:path'
import { describe, expect, it } from 'vitest'

const frontendRoot = path.resolve(import.meta.dirname, '..')

async function listFiles(directory) {
  const entries = await readdir(directory, { withFileTypes: true })
  const nested = await Promise.all(entries.map(async entry => {
    const resolved = path.join(directory, entry.name)
    return entry.isDirectory() ? listFiles(resolved) : [resolved]
  }))
  return nested.flat()
}

describe('stage-five migration boundary', () => {
  it('contains only the approved Home and Wi-Fi Database product surface', async () => {
    const files = await listFiles(path.join(frontendRoot, 'src'))
    const relativeFiles = files.map(file => path.relative(frontendRoot, file).replaceAll('\\', '/')).sort()
    expect(relativeFiles).toEqual([
      'src/api.js',
      'src/app.js',
      'src/dashboard.js',
      'src/main.js',
      'src/styles.css'
    ])

    const source = (await Promise.all(files.map(file => readFile(file, 'utf8')))).join('\n')
    expect(source).not.toMatch(/(?:OTA|Compatibility|Interference|Function Test|Project Progress|User Management)/i)
    expect(source).not.toMatch(/(?:\.\.\/)+core(?:\/|['"])/)
  })
})
