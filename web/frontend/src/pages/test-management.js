export function mount(root) {
  root.replaceChildren()
  return {
    async start() {},
    destroy() {},
  }
}
