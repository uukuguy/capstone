import test from 'node:test';
import assert from 'node:assert/strict';

test('native prompt frame accepts configured capacity above old fixed frame bound', async () => {
  const {validatePromptFrame} = await import('../src/capstone_agent/resources/general-sdk.mjs');
  const text = '字'.repeat(100000);
  const line = JSON.stringify({type: 'prompt', message: text});
  const frame = validatePromptFrame(line, {input: {kind: 'text', text},
    runtimeLimits: {rpc_frame_bytes: 400000, input_text_chars: 100000}});
  assert.equal(frame.message, text);
});

test('native prompt frame applies exact bytes and Unicode input character overrides', async () => {
  const {validatePromptFrame} = await import('../src/capstone_agent/resources/general-sdk.mjs');
  const text = '🙂'.repeat(11);
  const line = JSON.stringify({type: 'prompt', message: text});
  assert.throws(() => validatePromptFrame(line, {input: {kind: 'text', text},
    runtimeLimits: {rpc_frame_bytes: Buffer.byteLength(line) - 1, input_text_chars: 20}}),
  error => error.capacity.dimension === 'rpc_frame_bytes' && error.capacity.actual === Buffer.byteLength(line));
  assert.throws(() => validatePromptFrame(line, {input: {kind: 'text', text},
    runtimeLimits: {rpc_frame_bytes: 1000, input_text_chars: 10}}),
  error => error.capacity.dimension === 'input_text_chars' && error.capacity.actual === 11 && error.capacity.limit === 10);
  assert.equal(validatePromptFrame(line, {input: {kind: 'text', text},
    runtimeLimits: {rpc_frame_bytes: Buffer.byteLength(line), input_text_chars: 11}}).message, text);
});
