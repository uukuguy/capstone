export interface ArtifactPreview {
  kind: 'json' | 'markdown' | 'text';
  content: string;
  truncated: boolean;
}

const PREVIEW_KINDS = new Map<string, ArtifactPreview['kind']>([
  ['application/json', 'json'],
  ['text/markdown', 'markdown'],
  ['text/plain', 'text'],
]);
const MAX_PREVIEW_BYTES = 131_072;

function previewKind(response: Response): ArtifactPreview['kind'] {
  const contentType = response.headers.get('Content-Type')?.split(';', 1)[0]?.trim().toLowerCase() ?? '';
  const kind = PREVIEW_KINDS.get(contentType);
  if (!kind) throw new Error('Artifact response type is not safe to preview.');
  return kind;
}

async function cancelBody(response: Response) {
  try {
    await response.body?.cancel();
  } catch {
    // Preserve the protocol error rather than a best-effort browser cancellation failure.
  }
}

function rangeLength(response: Response, maxBytes: number): { length: number; total: number } {
  const range = response.headers.get('Content-Range');
  const match = range?.match(/^bytes 0-(0|[1-9]\d*)\/([1-9]\d*)$/);
  if (!match) throw new Error('Artifact preview range contract is invalid.');
  const end = Number(match[1]);
  const total = Number(match[2]);
  if (!Number.isSafeInteger(end) || !Number.isSafeInteger(total) || total <= 0) {
    throw new Error('Artifact preview range contract is invalid.');
  }
  const length = Math.min(maxBytes, total);
  if (end !== length - 1) throw new Error('Artifact preview range contract is invalid.');
  const contentLength = response.headers.get('Content-Length');
  if (contentLength !== null) {
    if (!/^(0|[1-9]\d*)$/.test(contentLength) || Number(contentLength) !== length) {
      throw new Error('Artifact preview range contract is invalid.');
    }
  }
  return { length, total };
}

async function readExactRange(response: Response, expectedLength: number): Promise<Uint8Array> {
  if (!response.body) throw new Error('Artifact preview body length does not match its range.');
  const reader = response.body.getReader();
  const chunks: Uint8Array[] = [];
  let retained = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        if (retained !== expectedLength) throw new Error('Artifact preview body length does not match its range.');
        break;
      }
      if (!value || value.byteLength > expectedLength - retained) {
        throw new Error('Artifact preview body length does not match its range.');
      }
      chunks.push(value);
      retained += value.byteLength;
    }
  } catch (error) {
    try {
      await reader.cancel();
    } catch {
      // Preserve the body/range error rather than a best-effort cancellation failure.
    }
    throw error;
  } finally {
    reader.releaseLock();
  }

  const bytes = new Uint8Array(retained);
  let offset = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return bytes;
}

/** Load display-only bytes through an already-authorized artifact gateway URL. */
export async function loadSafePreview(
  url: string,
  fetcher: typeof fetch,
  maxBytes = 131_072,
): Promise<ArtifactPreview> {
  if (!Number.isSafeInteger(maxBytes) || maxBytes <= 0) throw new Error('Artifact preview byte limit must be a positive integer.');
  if (maxBytes > MAX_PREVIEW_BYTES) throw new Error(`Artifact preview byte limit must be at most ${MAX_PREVIEW_BYTES}.`);
  const response = await fetcher(url, { headers: new Headers({ Range: `bytes=0-${maxBytes - 1}` }) });
  if (response.status !== 206) {
    await cancelBody(response);
    throw new Error(`Artifact preview request failed with status ${response.status}.`);
  }
  let range: { length: number; total: number };
  let kind: ArtifactPreview['kind'];
  try {
    range = rangeLength(response, maxBytes);
    kind = previewKind(response);
  } catch (error) {
    await cancelBody(response);
    throw error;
  }
  const bytes = await readExactRange(response, range.length);
  return {
    kind,
    content: new TextDecoder().decode(bytes),
    truncated: range.total > bytes.byteLength,
  };
}
