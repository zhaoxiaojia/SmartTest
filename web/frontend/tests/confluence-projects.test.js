// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { createConfluenceProjects } from '../src/confluence-projects.js'

const payload = {
  state: 'partial_success', snapshotTime: '2026-08-26T12:00:00Z',
  counts: { stale: 1, failed: 0, inactive: 2 }, discrepancies: ['Unexpected Owner'],
  facets: [
    { key: '__product_space__', label: 'Product Space', labels: ['Product Space'], options: [{ value: 'DOPL', label: 'China Operator Business' }, { value: 'TV', label: 'TV Business' }] },
    { key: 'support mode', label: 'Support Mode', labels: ['Support Mode'], options: ['A', 'B'] },
    { key: 'unexpected owner', label: 'Unexpected Owner', labels: ['Unexpected Owner'], options: ['Alice'] }
  ],
  projects: [{ project_id: 'A-1', name: 'Apollo', space_key: 'DOPL', status: 'stale', fields: { 'support mode': 'B' } }],
  ownerHierarchy: [{ role: 'Major FAE QA', people: [{ name: 'Coco', identity: 'u-1', projects: [
    { project_id: 'A-1', name: 'Apollo', space_key: 'DOPL', status: 'stale', fields: { 'support mode': 'B' } }
  ] }] }, { role: 'FAE QA', people: [] }, { role: 'QA Reviewer', people: [] }]
}
const fixedFacets = [
  ['__product_space__', 'Product Space'], ['page', 'Page'], ['date of commercial approval', 'Date of Commercial approval'],
  ['project id', 'Project ID'], ['odm', 'ODM'], ['oem/operator', 'OEM/Operator'], ['key part number', 'Key Part Number'],
  ['project status', 'Project Status'], ['current stage', 'Current Stage'], ['major pm', 'Major PM'], ['project owner', 'Project Owner'],
  ['support mode', 'Support Mode'], ['launch os', 'Launch OS'], ['date of kick off', 'Date of Kick Off'],
  ['planned closure', 'planned closure'], ['actual closure', 'actual closure'], ['mp time', 'MP Time'], ['launch time', 'Launch Time'],
  ['next target', 'Next Target'], ['next target date', 'Next Target Date'], ['sum', 'Sum']
].map(([key, label]) => ({ key, label, labels: [label], options: [] }))

describe('Confluence project facts', () => {
  beforeEach(() => { document.body.innerHTML = '<div id="app"></div>'; localStorage.clear() })

  it('renders dynamic facets and project results without report or download UI', async () => {
    const api = { getProjectFacts: vi.fn().mockResolvedValue(payload) }
    await createConfluenceProjects({ root: document.querySelector('#app'), api }).start()
    expect(document.body.textContent).toContain('Unexpected Owner')
    expect(document.body.textContent).toContain('Product Space')
    expect(document.body.textContent).toContain('Apollo')
    expect(document.body.textContent).toContain('Major FAE QA')
    expect(document.body.textContent).toContain('Coco')
    expect(document.body.textContent).toContain('Some project facts are stale or failed')
    expect(document.querySelector('[name="reportType"]')).toBeNull()
    expect(document.querySelector('.report-directory')).toBeNull()
    expect(document.querySelector('[data-download]')).toBeNull()
    expect(document.body.textContent).not.toContain('Open in Confluence')
  })

  it('consumes the Core owner hierarchy and renders expandable role/person/project levels', async () => {
    const api = { getProjectFacts: vi.fn().mockResolvedValue(payload) }
    await createConfluenceProjects({ root: document.querySelector('#app'), api }).start()
    expect(document.querySelectorAll('details.owner-role').length).toBe(3)
    expect(document.querySelector('details.owner-person summary').textContent).toContain('Coco')
    expect(document.querySelector('details.owner-project summary').textContent).toContain('Apollo')
  })

  it('keeps seven common filters and persists optional filter enablement', async () => {
    const complete = { ...payload, facets: [
      { key: '__product_space__', label: 'Product Space', options: ['DOPL'] },
      { key: 'date of commercial approval', label: 'Date of Commercial approval', options: [2025, 2026] },
      { key: 'project id', label: 'Project ID', options: ['A-1'] },
      { key: 'project status', label: 'Project Status', options: ['NORMAL'] },
      { key: 'current stage', label: 'Current Stage', options: ['Stage 1'] },
      { key: 'project owner', label: 'Project Owner', options: ['Alice'] },
      { key: 'support mode', label: 'Support Mode', options: ['A'] },
      { key: 'odm', label: 'ODM', options: ['ODM-X'] }
    ] }
    const api = { getProjectFacts: vi.fn().mockResolvedValue(complete) }
    await createConfluenceProjects({ root: document.querySelector('#app'), api }).start()
    expect([...document.querySelectorAll('[data-main-facets] > label')].map(row => row.firstChild.textContent)).toEqual([
      'Product Space', 'Date of Commercial approval', 'Project ID', 'Project Status', 'Current Stage', 'Project Owner', 'Support Mode'
    ])
    document.querySelector('[data-more-facets] input[value="odm"]').click()
    expect(document.querySelector('[name="field.odm"]')).toBeTruthy()
    expect(JSON.parse(localStorage.getItem('smarttest-confluence-more-filters'))).toEqual(['odm'])
    document.querySelector('[data-more-facets] input[value="odm"]').click()
    expect(document.querySelector('[name="field.odm"]')).toBeNull()
  })

  it('disables Apply while the local snapshot is loading', async () => {
    let resolve
    const api = { getProjectFacts: vi.fn(() => new Promise(done => { resolve = done })) }
    const started = createConfluenceProjects({ root: document.querySelector('#app'), api }).start()
    expect(document.querySelector('[type="submit"]').disabled).toBe(true)
    resolve(payload); await started
    expect(document.querySelector('[type="submit"]').disabled).toBe(false)
  })

  it('keeps every business control disabled and shows loading options without a local cache', async () => {
    const empty = {
      ...payload,
      state: 'no_snapshot', snapshotTime: null, projects: [], ownerHierarchy: [],
      facets: payload.facets.map(facet => ({ ...facet, options: [] }))
    }
    const api = { getProjectFacts: vi.fn().mockResolvedValue(empty) }
    await createConfluenceProjects({ root: document.querySelector('#app'), api }).start()
    expect(document.querySelector('[data-audit]').disabled).toBe(true)
    expect(document.querySelector('[type="submit"]').disabled).toBe(true)
    expect(document.querySelector('[data-reset]').disabled).toBe(true)
    expect(document.querySelector('[name="search"]').disabled).toBe(true)
    expect([...document.querySelectorAll('[data-main-facets] select')].every(item => item.disabled)).toBe(true)
    expect([...document.querySelectorAll('[data-main-facets] .multi-select__control')].every(item => item.disabled)).toBe(true)
    expect([...document.querySelectorAll('[data-main-facets] .multi-select__summary')].every(item => item.textContent === 'Loading…')).toBe(true)
    expect([...document.querySelectorAll('[data-more-facets] input')].every(item => item.disabled)).toBe(true)
  })

  it('renders all seven common filters from the immediate loading payload then polls to ready', async () => {
    const loading = { ...payload, state: 'loading', snapshotTime: null, projects: [], ownerHierarchy: [], facets: fixedFacets }
    const api = { getProjectFacts: vi.fn().mockResolvedValueOnce(loading).mockResolvedValueOnce(payload) }
    const pollDelay = vi.fn().mockResolvedValue()
    const component = createConfluenceProjects({ root: document.querySelector('#app'), api, pollDelay, maxPolls: 3 })
    await component.start()
    expect([...document.querySelectorAll('[data-main-facets] label')].map(row => row.firstChild.textContent)).toEqual([
      'Product Space', 'Date of Commercial approval', 'Project ID', 'Project Status', 'Current Stage', 'Project Owner', 'Support Mode'
    ])
    expect([...document.querySelectorAll('[data-main-facets] select')].every(item => item.disabled)).toBe(true)
    expect([...document.querySelectorAll('[data-main-facets] .multi-select__summary')].every(item => item.textContent === 'Loading…')).toBe(true)
    expect(document.querySelector('[role="status"]').textContent).toContain('Loading')
    await vi.waitFor(() => expect(api.getProjectFacts).toHaveBeenCalledTimes(2))
    await vi.waitFor(() => expect(document.querySelector('[type="submit"]').disabled).toBe(false))
  })

  it('stops polling on failed state and when the component is destroyed', async () => {
    const loading = { ...payload, state: 'loading', snapshotTime: null, projects: [], ownerHierarchy: [], facets: fixedFacets }
    const failed = { ...loading, state: 'failed' }
    const api = { getProjectFacts: vi.fn().mockResolvedValueOnce(loading).mockResolvedValueOnce(failed) }
    const component = createConfluenceProjects({ root: document.querySelector('#app'), api, pollDelay: () => Promise.resolve(), maxPolls: 5 })
    await component.start()
    await vi.waitFor(() => expect(document.querySelector('[role="status"]').textContent).toContain('failed'))
    expect(api.getProjectFacts).toHaveBeenCalledTimes(2)
    component.destroy()
    await Promise.resolve()
    expect(api.getProjectFacts).toHaveBeenCalledTimes(2)
  })

  it('uses the shared styled checkbox class for optional filters', async () => {
    const api = { getProjectFacts: vi.fn().mockResolvedValue(payload) }
    await createConfluenceProjects({ root: document.querySelector('#app'), api }).start()
    expect(document.querySelector('[data-more-facets] input').classList).toContain('form-check-input')
    expect(document.querySelector('[data-more-facets]').classList).toContain('more-filter-options')
  })

  it('submits every selected field facet and project/person search', async () => {
    const api = { getProjectFacts: vi.fn().mockResolvedValue(payload) }
    await createConfluenceProjects({ root: document.querySelector('#app'), api }).start()
    const form = document.querySelector('form')
    document.querySelector('[data-more-facets] input[value="unexpected owner"]').click()
    const productSpaceControl = form.elements['field.__product_space__']
    form.elements['field.unexpected owner'].value = 'Alice'
    form.elements['field.__product_space__'].value = 'DOPL'
    form.elements.search.value = 'Coco'
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
    await vi.waitFor(() => expect(api.getProjectFacts).toHaveBeenCalledTimes(2))
    expect(form.elements['field.__product_space__']).toBe(productSpaceControl)
    expect(api.getProjectFacts.mock.calls[1][0]).toEqual({ fields: { '__product_space__': ['DOPL'], 'unexpected owner': ['Alice'] }, search: 'Coco' })
  })

  it('shows Product Space labels while submitting keys and supports select all and clear', async () => {
    const api = { getProjectFacts: vi.fn().mockResolvedValue(payload) }
    await createConfluenceProjects({ root: document.querySelector('#app'), api }).start()
    const select = document.querySelector('[name="field.__product_space__"]')
    const multi = select.nextElementSibling
    expect([...select.options].map(option => option.textContent)).toEqual(['China Operator Business', 'TV Business'])
    multi.querySelector('.multi-select__control').click()
    multi.querySelector('[data-select-all]').click()
    expect(api.getProjectFacts).toHaveBeenCalledTimes(1)
    expect(multi.querySelector('.multi-select__tags').textContent).toContain('China Operator Business+1')
    multi.querySelector('.multi-select__control').click()
    multi.querySelector('[data-clear]').click()
    expect(api.getProjectFacts).toHaveBeenCalledTimes(1)
    expect(multi.querySelector('.multi-select__summary').textContent).toBe('All Product Space')
  })

  it('keeps snapshot facets fixed while Apply updates only downstream results', async () => {
    const filtered = { ...payload, facets: [{ key: '__product_space__', label: 'Product Space', options: [] }],
      projects: [], ownerHierarchy: [] }
    const api = { getProjectFacts: vi.fn().mockResolvedValueOnce(payload).mockResolvedValueOnce(filtered) }
    await createConfluenceProjects({ root: document.querySelector('#app'), api }).start()
    const select = document.querySelector('[name="field.__product_space__"]')
    select.options[0].selected = true
    select.dispatchEvent(new Event('change', { bubbles: true }))
    expect(api.getProjectFacts).toHaveBeenCalledTimes(1)
    expect([...select.options].map(option => option.value)).toEqual(['DOPL', 'TV'])
    document.querySelector('form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
    await vi.waitFor(() => expect(api.getProjectFacts).toHaveBeenCalledTimes(2))
    expect([...select.options].map(option => option.value)).toEqual(['DOPL', 'TV'])
    expect(document.querySelector('[data-projects]').textContent).toContain('No matching projects')
  })

  it('Reset clears local values without replacing snapshot facets', async () => {
    const api = { getProjectFacts: vi.fn().mockResolvedValue(payload) }
    await createConfluenceProjects({ root: document.querySelector('#app'), api }).start()
    const select = document.querySelector('[name="field.__product_space__"]')
    select.options[0].selected = true
    document.querySelector('[name="search"]').value = 'Coco'
    document.querySelector('[data-reset]').click()
    await vi.waitFor(() => expect(api.getProjectFacts).toHaveBeenCalledTimes(2))
    expect([...select.selectedOptions]).toEqual([])
    expect(document.querySelector('[name="search"]').value).toBe('')
    expect([...select.options].map(option => option.value)).toEqual(['DOPL', 'TV'])
  })

  it('shows the complete Core Product Space names without a search control', async () => {
    const productSpaces = [
      { value: 'DOPL', label: 'China Operator Business' },
      { value: 'SDPL', label: 'Smart Device Business' },
      { value: 'TV', label: 'TV Business' },
      { value: 'OOPL', label: 'Global Operator & STB Business' }
    ]
    const facets = payload.facets.map(facet => facet.key === '__product_space__'
      ? { ...facet, options: productSpaces }
      : facet)
    const api = { getProjectFacts: vi.fn().mockResolvedValue({ ...payload, facets }) }

    await createConfluenceProjects({ root: document.querySelector('#app'), api }).start()

    const multi = document.querySelector('[name="field.__product_space__"]').nextElementSibling
    expect(multi.querySelector('input[type="search"]')).toBeNull()
    expect([...multi.querySelectorAll('.multi-select__option span')].map(node => node.textContent)).toEqual(productSpaces.map(item => item.label))
  })

  it('keeps audit as an independent explicitly blocked action without a Web credential owner', async () => {
    const api = { getProjectFacts: vi.fn().mockResolvedValue(payload) }
    await createConfluenceProjects({ root: document.querySelector('#app'), api }).start()
    document.querySelector('[data-audit]').click()
    expect(document.querySelector('[data-audit-status]').textContent).toContain('Client runtime credential')
    expect(api.getProjectFacts).toHaveBeenCalledTimes(1)
  })

  it.each([
    ['no_snapshot', 'No local project snapshot'],
    ['schema_error', 'Local project snapshot is unreadable'],
    ['partial_success', 'Some project facts are stale or failed']
  ])('renders %s state', async (state, message) => {
    const api = { getProjectFacts: vi.fn().mockResolvedValue({ ...payload, state, projects: [] }) }
    await createConfluenceProjects({ root: document.querySelector('#app'), api }).start()
    expect(document.querySelector('[role="status"]').textContent).toContain(message)
  })
})
