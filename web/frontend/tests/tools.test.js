// @vitest-environment jsdom
import { beforeEach, describe, expect, it } from 'vitest'
import { createTools } from '../src/tools.js'

describe('Tools page', () => {
  beforeEach(() => { document.body.innerHTML = '<main></main>' })

  it('shows only the scheduled review business', async () => {
    const page = createTools({ root: document.querySelector('main') })
    await page.start()

    expect(document.querySelector('[data-jira-filter]')).toBeNull()
    expect(document.querySelector('[data-jira-review]')).toBeNull()
    expect(document.querySelector('[data-confluence-review]')).toBeNull()
    expect(document.querySelectorAll('.settings-section')).toHaveLength(1)
    expect(document.body.textContent).toContain('定期审查邮件')
    expect(document.querySelector('a[href="/audit-email.html"]')).not.toBeNull()
  })
})
