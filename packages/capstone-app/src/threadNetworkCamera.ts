import {applicationCapacity,observeCapacity,rethrowDebugCapacity} from './applicationCapacity'
export type NetworkCamera = { x: number; y: number; width: number; height: number }

function readCameras(storageKey?: string): Record<string, NetworkCamera> {
  if (!storageKey) return {}
  try {
    const text = sessionStorage.getItem(storageKey)
    if (!text || observeCapacity(new TextEncoder().encode(text).byteLength,'ui_camera_storage_bytes','camera.restore')) return {}
    const value: unknown = JSON.parse(text)
    if (!value || typeof value !== 'object' || Array.isArray(value)) return {}
    observeCapacity(Object.keys(value).length,'ui_cache_items','camera.restore')
    return Object.fromEntries(Object.entries(value).slice(-applicationCapacity('ui_cache_items')).filter(([key, camera]) =>
      key.length <= 2048 && camera && typeof camera === 'object' && Object.keys(camera).length === 4 &&
      ['x', 'y', 'width', 'height'].every(field => typeof camera[field] === 'number' && Number.isFinite(camera[field]) && Math.abs(camera[field]) <= 1e9) &&
      camera.width > 0 && camera.height > 0))
  } catch (error) { rethrowDebugCapacity(error); return {} }
}

export function readNetworkCamera(storageKey?: string, viewKey?: string): NetworkCamera | undefined {
  const values = readCameras(storageKey)
  return viewKey && Object.hasOwn(values, viewKey) ? values[viewKey] : undefined
}

export function writeNetworkCamera(storageKey: string | undefined, viewKey: string | undefined, camera: NetworkCamera): void {
  if (!storageKey || !viewKey) return
  try {
    const values = readCameras(storageKey)
    delete values[viewKey]
    observeCapacity(Object.keys(values).length+1,'ui_cache_items','camera.persist')
    const text = JSON.stringify(Object.fromEntries([...Object.entries(values), [viewKey, camera]].slice(-applicationCapacity('ui_cache_items'))))
    if (!observeCapacity(new TextEncoder().encode(text).byteLength,'ui_camera_storage_bytes','camera.persist')) sessionStorage.setItem(storageKey, text)
  } catch (error) { rethrowDebugCapacity(error); /* View restoration must not prevent model access or history reading. */ }
}
