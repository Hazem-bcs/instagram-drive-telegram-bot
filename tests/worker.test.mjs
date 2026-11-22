import { test } from 'node:test';
import assert from 'node:assert/strict';
import worker, { parseInstagramUrl, constantTimeEqual } from '../worker/src/index.js';

test('accepts public Instagram reel and removes trackers', () => {
  assert.equal(parseInstagramUrl('see https://www.instagram.com/reel/ABC_123/?igsh=tracking'), 'https://www.instagram.com/reel/ABC_123/');
  assert.equal(parseInstagramUrl('https://instagram.com/p/abc-123/'), 'https://www.instagram.com/p/abc-123/');
});
test('rejects unrelated and private/unsafe addresses', () => {
  for (const url of ['https://instagram.com.evil.com/reel/ABC/', 'http://instagram.com/reel/ABC/', 'https://www.instagram.com/stories/x/1/', 'https://youtu.be/watch']) {
    assert.equal(parseInstagramUrl(url), null);
  }
});
test('compares webhook secrets', () => {
  assert.equal(constantTimeEqual('a1', 'a1'), true);
  assert.equal(constantTimeEqual('a1', 'a2'), false);
  assert.equal(constantTimeEqual('a', 'ab'), false);
});
test('health endpoint works without secrets', async () => {
  const result = await worker.fetch(new Request('https://example.com/health'), {});
  assert.equal(result.status, 200);
  assert.equal(await result.text(), 'ok');
});
test('webhook without valid secret is rejected', async () => {
  const result = await worker.fetch(new Request('https://example.com/telegram', {method:'POST', body:'{}'}), {TELEGRAM_WEBHOOK_SECRET:'secret'});
  assert.equal(result.status, 401);
});

test('authorized Telegram update dispatches encrypted payload, not plaintext link', async () => {
  const oldFetch = globalThis.fetch;
  const captured = [];
  globalThis.fetch = async (url, options) => {
    captured.push({ url: String(url), options });
    if (String(url).includes('api.github.com')) return new Response(null, { status: 204 });
    if (String(url).includes('api.telegram.org')) return new Response('{"ok":true}', { status: 200 });
    throw new Error('unexpected network endpoint');
  };
  try {
    const rawKey = crypto.getRandomValues(new Uint8Array(32));
    const key = Buffer.from(rawKey).toString('base64url');
    const env = {
      TELEGRAM_WEBHOOK_SECRET: 'webhook-secret', TELEGRAM_ALLOWED_USER_ID: '1234567',
      TELEGRAM_BOT_TOKEN: 'mock-token', GITHUB_OWNER: 'Hazem-bcs', GITHUB_REPO: 'instagram-drive-telegram-bot',
      GITHUB_TOKEN: 'mock-gh-token', PIPELINE_KEY: key,
    };
    const request = new Request('https://example.com/telegram', {
      method: 'POST',
      headers: { 'X-Telegram-Bot-Api-Secret-Token': 'webhook-secret' },
      body: JSON.stringify({ message: { from: { id: 1234567 }, chat: { type: 'private', id: 1234567 },
        text: 'https://instagram.com/reel/Test123/?igsh=tracking' } }),
    });
    const response = await worker.fetch(request, env);
    assert.equal(response.status, 200);
    assert.equal(captured.length, 2);
    const dispatch = captured.find(c => c.url.includes('api.github.com'));
    const payload = JSON.parse(dispatch.options.body).inputs.payload;
    assert.equal(payload.includes('instagram.com'), false);
    assert.equal(payload.includes('1234567'), false);
    const [iv, ciphertext] = payload.split('.');
    const cryptoKey = await crypto.subtle.importKey('raw', rawKey, 'AES-GCM', false, ['decrypt']);
    const plaintext = await crypto.subtle.decrypt({name:'AES-GCM',iv:Buffer.from(iv,'base64url')},
      cryptoKey, Buffer.from(ciphertext,'base64url'));
    assert.deepEqual(JSON.parse(new TextDecoder().decode(plaintext)), {
      url: 'https://www.instagram.com/reel/Test123/', chat_id:'1234567',
    });
  } finally {
    globalThis.fetch = oldFetch;
  }
});
