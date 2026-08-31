export function createDownloadButton({
  element,
  prepare,
  navigate = url => globalThis.location.assign(url),
  artifactUrl,
  onSessionExpired = () => {},
}) {
  let busy = false
  let disposed = false

  async function download() {
    if (disposed || busy || element.disabled) return
    busy = true
    element.disabled = true
    element.dataset.downloadState = 'preparing'
    try {
      const artifact = await prepare()
      if (disposed) return
      navigate(artifactUrl(artifact.id))
      element.dataset.downloadState = 'ready'
    } catch (error) {
      if (disposed) return
      element.dataset.downloadState = 'error'
      if (error?.status === 401) onSessionExpired(error)
    } finally {
      busy = false
      element.disabled = disposed
    }
  }

  element.addEventListener('click', download)
  return { element, download, destroy() { disposed = true; element.disabled = true; element.removeEventListener('click', download) } }
}
