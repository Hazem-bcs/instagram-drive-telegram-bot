import { test } from 'node:test';
import assert from 'node:assert/strict';
import worker, { parseInstagramUrl, parseVideoUrl, constantTimeEqual } from '../worker/src/index.js';

test('accepts public Instagram reel and removes trackers', () => {
  assert.equal(parseInstagramUrl('see https://www.instagram.com/reel/ABC_123/?igsh=tracking'), 'https://www.instagram.com/reel/ABC_123/');
  assert.equal(parseInstagramUrl('https://instagram.com/p/abc-123/'), 'https://www.instagram.com/p/abc-123/');
});
test('rejects unrelated and private/unsafe addresses', () => {
  for (const url of ['https://instagram.com.evil.com/reel/ABC/', 'http://instagram.com/reel/ABC/', 'https://www.instagram.com/stories/x/1/', 'https://youtu.be/watch']) {
    assert.equal(parseInstagramUrl(url), null);
  }
});
test('accepts video links from every supported platform', () => {
  const samples = [
    ['https://youtu.be/dQw4w9WgXcQ?t=12', 'YouTube', 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'],
    ['https://youtube.com/shorts/dQw4w9WgXcQ', 'YouTube', 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'],
    ['https://www.facebook.com/reel/123456789/', 'Facebook', 'https://www.facebook.com/reel/123456789/'],
    ['https://www.facebook.com/share/r/abcd12/', 'Facebook', 'https://www.facebook.com/share/r/abcd12/'],
    ['https://www.tiktok.com/@user/video/7345678912345678901?share_id=1', 'TikTok', 'https://www.tiktok.com/@user/video/7345678912345678901'],
    ['https://vm.tiktok.com/ZMabcd12/', 'TikTok', 'https://vm.tiktok.com/ZMabcd12/'],
    ['https://twitter.com/user/status/12345678?s=20', 'X', 'https://x.com/i/status/12345678'],
    ['https://www.reddit.com/r/videos/comments/abc123/title/', 'Reddit', 'https://www.reddit.com/comments/abc123/'],
    ['https://vimeo.com/123456789', 'Vimeo', 'https://vimeo.com/123456789'],
    ['https://clips.twitch.tv/FunnyClip123', 'Twitch', 'https://clips.twitch.tv/FunnyClip123'],
    ['https://www.twitch.tv/videos/12345', 'Twitch', 'https://www.twitch.tv/videos/12345'],
    ['https://www.dailymotion.com/video/x99abc1', 'Dailymotion', 'https://www.dailymotion.com/video/x99abc1'],
    ['https://streamable.com/abc123', 'Streamable', 'https://streamable.com/abc123'],
  ];
  for (const [input, platform, url] of samples) {
    assert.deepEqual(parseVideoUrl(input), {platform, url}, input);
  }
});
test('rejects unsafe hosts and non-video addresses', () => {
  for (const input of [
    'https://youtu.be.evil.example/dQw4w9WgXcQ', 'http://www.youtube.com/watch?v=dQw4w9WgXcQ',
    'https://youtube.com/@creator', 'https://www.youtube.com/playlist?list=abc',
    'https://127.0.0.1/', 'https://www.instagram.com@evil.com/reel/xyz/',
    'https://www.instagram.com:8080/reel/xyz/', 'https://x.com/user',
    'https://www.tiktok.com/@user/video/123#fragment',
    'https://www.reddit.com/r/videos/',
  ]) assert.equal(parseVideoUrl(input), null, input);
});

test('YouTube Shorts webhook dispatches with encrypted normalized URL', async () => {
  const oldFetch = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (url, options) => {
    calls.push({url:String(url),options});
    return String(url).includes('github.com') ? new Response(null,{status:204}) : new Response('{"ok":true}',{status:200});
  };
  try {
    const rawKey = crypto.getRandomValues(new Uint8Array(32));
    const env = {
      TELEGRAM_WEBHOOK_SECRET:'secret',TELEGRAM_ALLOWED_USER_ID:'2345678',
      TELEGRAM_BOT_TOKEN:'mock',GITHUB_OWNER:'Hazem-bcs',GITHUB_REPO:'instagram-drive-telegram-bot',
      GITHUB_TOKEN:'mock',PIPELINE_KEY:Buffer.from(rawKey).toString('base64url'),
    };
    const req = new Request('https://example.com/telegram',{
      method:'POST',headers:{'X-Telegram-Bot-Api-Secret-Token':'secret'},
      body:JSON.stringify({message:{from:{id:2345678},chat:{type:'private',id:2345678},
        text:'https://youtube.com/shorts/dQw4w9WgXcQ?si=tracker'}}),
    });
    const result = await worker.fetch(req,env);
    assert.equal(result.status,200);
    const dispatch = calls.find(c=>c.url.includes('github.com'));
    assert.ok(dispatch);
    const payload = JSON.parse(dispatch.options.body).inputs.payload;
    assert.ok(!payload.includes('youtube.com'));
    const [nonce,ciphertext] = payload.split('.');
    const key = await crypto.subtle.importKey('raw',rawKey,'AES-GCM',false,['decrypt']);
    const decoded = await crypto.subtle.decrypt(
      {name:'AES-GCM',iv:Buffer.from(nonce,'base64url')},key,Buffer.from(ciphertext,'base64url'));
    assert.deepEqual(JSON.parse(new TextDecoder().decode(decoded)),{
      url:'https://www.youtube.com/watch?v=dQw4w9WgXcQ',chat_id:'2345678',
    });
  } finally { globalThis.fetch = oldFetch; }
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

test('group bridge check only accepts the owner, named group and explicit command', async () => {
  const originalFetch = globalThis.fetch;
  const requests = [];
  globalThis.fetch = async (url, options) => {
    requests.push({url: String(url), body: JSON.parse(options.body)});
    return new Response('{"ok":true}', {status:200});
  };
  try {
    const env = { TELEGRAM_WEBHOOK_SECRET:"mock", TELEGRAM_ALLOWED_USER_ID:"123",
      TELEGRAM_BOT_TOKEN:"mock" };
    const check = (message) => worker.fetch(new Request("https://example.com/telegram",{
      method:"POST", headers:{"X-Telegram-Bot-Api-Secret-Token":"mock"},
      body:JSON.stringify({message})
    }),env);
    const message = {chat:{id:-1234,type:"supergroup",title:"Video Bridge"},
      from:{id:123,is_bot:false}, text:"/bridgecheck@hazemdownloaderbot"};
    await check({...message, from:{id:456,is_bot:false}});
    await check({...message, chat:{...message.chat,title:"Other"}});
    await check({...message, text:"https://youtube.com/watch?v=nYYitW53CXI"});
    assert.equal(requests.length,0);
    await check(message);
    assert.equal(requests.length,2);
    assert.equal(requests[0].body.text,"/help@download_it_bot");
    assert.equal(requests[0].body.chat_id,-1234);
    assert.equal(String(requests[1].body.chat_id),"123");
    await check({...message,from:{id:789,is_bot:true,username:"download_it_bot"},
      text:"help reply",reply_to_message:{from:{is_bot:true,username:"hazemdownloaderbot"},text:"/help@download_it_bot"}});
    assert.equal(requests.length,3);
    assert.equal(String(requests[2].body.chat_id),"123");
    assert.ok(requests.every(r=>r.url.includes("api.telegram.org")));
  } finally { globalThis.fetch = originalFetch; }
});
