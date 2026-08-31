// @vitest-environment jsdom
import { beforeEach, expect, it, vi } from 'vitest'

import { createDownloadButton } from '../src/download-button.js'

beforeEach(() => { document.body.innerHTML = '<button id="download">Download</button>' })

it('never navigates or reenables an old-account download after disposal', async () => {
  let release
  const navigate = vi.fn()
  const button = createDownloadButton({ element: document.querySelector('#download'),
    prepare: () => new Promise(resolve => { release = resolve }), navigate, artifactUrl: id => id })
  const pending = button.download()
  button.destroy()
  release({ id: 'old-account' })
  await pending
  expect(navigate).not.toHaveBeenCalled()
  expect(button.element.disabled).toBe(true)
})

it('prevents repeated export clicks and opens only the unified artifact URL', async () => {
  let release
  const prepare = vi.fn(() => new Promise(resolve => { release = resolve }))
  const navigate = vi.fn()
  const button = createDownloadButton({
    element: document.querySelector('#download'), prepare, navigate,
    artifactUrl: id => '/api/downloads/' + id
  })

  button.element.click()
  button.element.click()
  expect(prepare).toHaveBeenCalledOnce()
  expect(button.element.disabled).toBe(true)
  release({ id: 'd1', fileName: 'report.xlsx' })
  await vi.waitFor(() => expect(navigate).toHaveBeenCalledWith('/api/downloads/d1'))
  expect(button.element.disabled).toBe(false)
})

it('reports session expiry through the common handler', async () => {
  const expired = vi.fn()
  const button = createDownloadButton({
    element: document.querySelector('#download'),
    prepare: vi.fn().mockRejectedValue({ status: 401 }),
    navigate: vi.fn(), artifactUrl: vi.fn(), onSessionExpired: expired,
  })

  button.element.click()
  await vi.waitFor(() => expect(expired).toHaveBeenCalledOnce())
  expect(button.element.dataset.downloadState).toBe('error')
})
