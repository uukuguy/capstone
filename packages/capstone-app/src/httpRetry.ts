const READ_ATTEMPTS = 12

function waitForRetry(ms: number, signal?: AbortSignal | null): Promise<void> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => { signal?.removeEventListener('abort', abort); resolve() }, ms)
    function abort() { clearTimeout(timer); reject(new DOMException('Aborted', 'AbortError')) }
    if (signal?.aborted) abort()
    else signal?.addEventListener('abort', abort, { once: true })
  })
}

/** Recover bounded cold starts for reads. Writes retain their own retry contract. */
export async function fetchWithReadRetry(url: string, init: RequestInit = {}, fetcher: typeof fetch = fetch,
                                         readAttempts: number = READ_ATTEMPTS): Promise<Response> {
  const read = !init.method || init.method.toUpperCase() === 'GET'
  const attempts = read ? readAttempts : 1
  for (let attempt = 0; attempt < attempts; attempt++) {
    init.signal?.throwIfAborted()
    let response: Response
    try { response = await fetcher.call(globalThis, url, init) }
    catch (cause) {
      if (!read || attempt + 1 === attempts || !(cause instanceof TypeError)) throw cause
      await waitForRetry(Math.min(400 * 2 ** attempt, 5000), init.signal)
      continue
    }
    if (read && [502, 503, 504].includes(response.status) && attempt + 1 < attempts) {
      await response.body?.cancel()
      await waitForRetry(Math.min(400 * 2 ** attempt, 5000), init.signal)
      continue
    }
    return response
  }
  throw new Error('读取请求未完成')
}
