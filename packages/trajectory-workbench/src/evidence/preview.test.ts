import { describe, expect, it, vi } from 'vitest';
import { loadSafePreview } from './preview';

function prefixResponse(
  body: string,
  contentRange: string,
  contentType = 'application/json; charset=utf-8',
  contentLength = String(new TextEncoder().encode(body).byteLength),
) {
  return new Response(body, {
    status: 206,
    headers: {
      'Content-Type': contentType,
      'Content-Range': contentRange,
      'Content-Length': contentLength,
    },
  });
}

describe('loadSafePreview', () => {
  it('requests and retains an exact bounded JSON prefix', async () => {
    const payload = '{"result":"abcdefghijklmnopqrstuvwxyz"}';
    const prefix = payload.slice(0, 16);
    const fetcher = vi.fn<typeof fetch>(async (_url, init) => {
      expect(new Headers(init?.headers).get('Range')).toBe('bytes=0-15');
      return prefixResponse(prefix, `bytes 0-15/${payload.length}`);
    });

    const preview = await loadSafePreview('/api/runs/analysis-test/artifacts/evidence:one', fetcher, 16);

    expect(preview).toEqual({ kind: 'json', content: prefix, truncated: true });
    expect(new TextEncoder().encode(preview.content)).toHaveLength(16);
  });

  it.each([
    ['text/markdown; charset=utf-8', 'markdown'],
    ['text/plain', 'text'],
  ] as const)('accepts the fixed safe %s media type', async (contentType, kind) => {
    const preview = await loadSafePreview('/artifact', async () => prefixResponse(
      'safe text', 'bytes 0-8/9', contentType,
    ));

    expect(preview).toEqual({ kind, content: 'safe text', truncated: false });
  });

  it('rejects a successful full-body response before reading it', async () => {
    let reads = 0;
    let cancelled = false;
    const response = {
      status: 200,
      ok: true,
      headers: new Headers({ 'Content-Type': 'text/plain' }),
      body: {
        async cancel() { cancelled = true; },
        getReader: () => ({
          async read() {
            reads += 1;
            return { done: true, value: undefined };
          },
          async cancel() { cancelled = true; },
          releaseLock() {},
        }),
      },
    } as unknown as Response;
    const fetcher = vi.fn<typeof fetch>(async () => response);

    await expect(loadSafePreview('/artifact', fetcher)).rejects.toThrow('status 200');

    expect(reads).toBe(0);
    expect(cancelled).toBe(true);
  });

  it.each([
    ['missing content range', null, '4'],
    ['wrong start', 'bytes 1-3/4', '3'],
    ['wrong end', 'bytes 0-2/4', '3'],
    ['zero total', 'bytes 0-0/0', '1'],
    ['mismatched content length', 'bytes 0-3/4', '3'],
  ])('rejects a %s range contract before previewing', async (_name, contentRange, contentLength) => {
    const headers: Record<string, string> = {
      'Content-Type': 'text/plain',
      'Content-Length': contentLength,
    };
    if (contentRange) headers['Content-Range'] = contentRange;

    await expect(loadSafePreview('/artifact', async () => new Response('safe', {
      status: 206,
      headers,
    }))).rejects.toThrow('range');
  });

  it('rejects an incomplete ranged body and cancels it', async () => {
    await expect(loadSafePreview('/artifact', async () => prefixResponse(
      'abc', 'bytes 0-3/4', 'text/plain', '4',
    ))).rejects.toThrow('body length');
  });

  it('rejects and cancels a ranged body that exceeds its declared length', async () => {
    let cancelled = false;
    const response = {
      status: 206,
      headers: new Headers({
        'Content-Type': 'text/plain',
        'Content-Range': 'bytes 0-3/4',
        'Content-Length': '4',
      }),
      body: {
        getReader: () => ({
          async read() { return { done: false, value: new TextEncoder().encode('extra') }; },
          async cancel() { cancelled = true; },
          releaseLock() {},
        }),
      },
    } as unknown as Response;

    await expect(loadSafePreview('/artifact', async () => response)).rejects.toThrow('body length');

    expect(cancelled).toBe(true);
  });

  it('rejects executable or unexpected response media types', async () => {
    await expect(loadSafePreview('/artifact', async () => prefixResponse(
      '<script />', 'bytes 0-9/10', 'text/html', '10',
    ))).rejects.toThrow('not safe to preview');
  });

  it('rejects an unsuccessful artifact response without exposing its body', async () => {
    await expect(loadSafePreview('/artifact', async () => new Response('private diagnostic', {
      status: 403,
      headers: { 'Content-Type': 'text/plain' },
    }))).rejects.toThrow('Artifact preview request failed with status 403');
  });

  it('treats an empty artifact range response as unavailable', async () => {
    await expect(loadSafePreview('/artifact', async () => new Response('', {
      status: 416,
      headers: { 'Content-Range': 'bytes */0' },
    }))).rejects.toThrow('status 416');
  });

  it('rejects preview limits above the gateway maximum before fetching', async () => {
    const fetcher = vi.fn<typeof fetch>();

    await expect(loadSafePreview('/artifact', fetcher, 131_073)).rejects.toThrow('at most 131072');

    expect(fetcher).not.toHaveBeenCalled();
  });
});
