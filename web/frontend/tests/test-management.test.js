// @vitest-environment jsdom
import { beforeEach, describe, expect, it } from 'vitest'

import { mount } from '../src/pages/test-management.js'

describe('Test Management page', () => {
  beforeEach(() => { document.body.innerHTML = '<main><p>old content</p></main>' })

  it('keeps the page content empty', async () => {
    const root = document.querySelector('main')
    const page = mount(root)
    await page.start()

    expect(root.childElementCount).toBe(0)
    expect(root.textContent).toBe('')
  })
})
