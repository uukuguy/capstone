import {sha256} from 'js-sha256'

/** Keep artifact integrity checks available on intranet HTTP origins. */
export async function sha256Hex(bytes: Uint8Array | ArrayBuffer): Promise<string> {
  const buffer = bytes instanceof Uint8Array ? new Uint8Array(bytes).buffer : bytes
  if (!globalThis.crypto?.subtle) return sha256(buffer)
  const digest = await crypto.subtle.digest('SHA-256', buffer)
  return Array.from(new Uint8Array(digest), value => value.toString(16).padStart(2, '0')).join('')
}
