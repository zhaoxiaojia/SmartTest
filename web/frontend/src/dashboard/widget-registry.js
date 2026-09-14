export function createWidgetRegistry() {
  const definitions = new Map()
  return {
    register(definition) {
      if (!definition?.type || definitions.has(definition.type)) throw new Error(`Invalid or duplicate widget type: ${definition?.type ?? ''}`)
      definitions.set(definition.type, Object.freeze({ ...definition }))
    },
    get(type) { return definitions.get(type) },
    list() { return [...definitions.values()] },
  }
}
