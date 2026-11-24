/** Telegram webhook -> encrypted GitHub workflow_dispatch. Runs on Cloudflare Workers. */
const TELEGRAM_API = "https://api.telegram.org";
const URL_RE = /https?:\/\/[^\s<>"']+/i;
const VALID_ID = /^[A-Za-z0-9_-]+$/;
const ALLOWED_HOSTS = Object.freeze({
  Instagram: ["instagram.com", "www.instagram.com", "m.instagram.com"],
  YouTube: ["youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be"],
  Facebook: ["facebook.com", "www.facebook.com", "m.facebook.com", "mbasic.facebook.com", "fb.watch"],
  TikTok: ["tiktok.com", "www.tiktok.com", "m.tiktok.com", "vm.tiktok.com", "vt.tiktok.com"],
  X: ["x.com", "www.x.com", "twitter.com", "www.twitter.com", "mobile.twitter.com"],
  Reddit: ["reddit.com", "www.reddit.com", "old.reddit.com", "new.reddit.com", "redd.it", "v.redd.it"],
  Vimeo: ["vimeo.com", "www.vimeo.com", "player.vimeo.com"],
  Twitch: ["twitch.tv", "www.twitch.tv", "m.twitch.tv", "clips.twitch.tv"],
  Dailymotion: ["dailymotion.com", "www.dailymotion.com", "dai.ly"],
  Streamable: ["streamable.com", "www.streamable.com"],
});

function base64Url(bytes) {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}
function decodeBase64Url(s) {
  const normalized = s.replace(/-/g, "+").replace(/_/g, "/");
  const binary = atob(normalized + "=".repeat((4 - (normalized.length % 4)) % 4));
  return Uint8Array.from(binary, c => c.charCodeAt(0));
}

/** Only supported public video URL shapes are permitted. Never follow arbitrary links. */
export function parseVideoUrl(text) {
  if (typeof text !== "string" || text.length > 3500) return null;
  const raw = text.match(URL_RE)?.[0]?.replace(/[),.!؟،\]}>]+$/, "");
  if (!raw) return null;
  let u;
  try { u = new URL(raw); } catch { return null; }
  if (u.protocol !== "https:" || u.username || u.password || u.port || u.hash) return null;
  const host = u.hostname.toLowerCase();
  const platform = Object.entries(ALLOWED_HOSTS).find(([, hosts]) => hosts.includes(host))?.[0];
  if (!platform) return null;
  const path = u.pathname;
  let match;
  let url;
  switch (platform) {
    case "Instagram":
      match = path.match(/^\/(reel|reels|p|tv)\/([A-Za-z0-9_-]+)\/?$/i);
      if (match) url = `https://www.instagram.com/${match[1].toLowerCase()}/${match[2]}/`;
      break;
    case "YouTube": {
      let videoId;
      if (host === "youtu.be") videoId = path.match(/^\/([A-Za-z0-9_-]{11})\/?$/)?.[1];
      else if (path === "/watch") videoId = u.searchParams.get("v");
      else videoId = path.match(/^\/(?:shorts|live|embed)\/([A-Za-z0-9_-]{11})\/?$/)?.[1];
      if (videoId && /^[A-Za-z0-9_-]{11}$/.test(videoId)) url = `https://www.youtube.com/watch?v=${videoId}`;
      break;
    }
    case "Facebook":
      if (host === "fb.watch") {
        match = path.match(/^\/([A-Za-z0-9_-]+)\/?$/);
        if (match) url = `https://fb.watch/${match[1]}/`;
      } else if (path === "/watch") {
        const id = u.searchParams.get("v");
        if (id && /^\d+$/.test(id)) url = `https://www.facebook.com/watch/?v=${id}`;
      } else {
        match = path.match(/^\/(?:reel|videos)\/(\d+)\/?$/i)
          || path.match(/^\/[A-Za-z0-9._-]+\/videos\/(\d+)\/?$/i);
        if (match) url = `https://www.facebook.com/reel/${match[1]}/`;
        else {
          match = path.match(/^\/share\/(r|v)\/([A-Za-z0-9_-]+)\/?$/i);
          if (match) url = `https://www.facebook.com/share/${match[1].toLowerCase()}/${match[2]}/`;
        }
      }
      break;
    case "TikTok":
      if (host === "vm.tiktok.com" || host === "vt.tiktok.com") {
        match = path.match(/^\/([A-Za-z0-9_-]+)\/?$/);
        if (match) url = `https://${host}/${match[1]}/`;
      } else {
        match = path.match(/^\/@([A-Za-z0-9._-]+)\/video\/(\d+)\/?$/);
        if (match) url = `https://www.tiktok.com/@${match[1]}/video/${match[2]}`;
        else {
          match = path.match(/^\/t\/([A-Za-z0-9_-]+)\/?$/);
          if (match) url = `https://www.tiktok.com/t/${match[1]}/`;
        }
      }
      break;
    case "X":
      match = path.match(/^\/(?:[A-Za-z0-9_]+|i)\/status\/(\d+)\/?$/i)
        || path.match(/^\/i\/web\/status\/(\d+)\/?$/i);
      if (match) url = `https://x.com/i/status/${match[1]}`;
      break;
    case "Reddit":
      if (host === "redd.it" || host === "v.redd.it") {
        match = path.match(/^\/([A-Za-z0-9]+)\/?$/);
        if (match) url = `https://${host}/${match[1]}/`;
      } else {
        match = path.match(/^\/(?:r\/[A-Za-z0-9_]+\/)?comments\/([A-Za-z0-9]+)(?:\/[^?#]*)?\/?$/);
        if (match) url = `https://www.reddit.com/comments/${match[1]}/`;
      }
      break;
    case "Vimeo":
      match = path.match(/^\/(\d+)\/?$/)
        || path.match(/^\/(?:channels\/[A-Za-z0-9_-]+|groups\/[A-Za-z0-9_-]+\/videos|video|album\/\d+\/video)\/(\d+)\/?$/);
      if (match) url = `https://vimeo.com/${match[2] || match[1]}`;
      break;
    case "Twitch":
      if (host === "clips.twitch.tv") {
        match = path.match(/^\/([A-Za-z0-9_-]+)\/?$/);
        if (match) url = `https://clips.twitch.tv/${match[1]}`;
      } else {
        match = path.match(/^\/videos\/(\d+)\/?$/);
        if (match) url = `https://www.twitch.tv/videos/${match[1]}`;
        else {
          match = path.match(/^\/([A-Za-z0-9_]+)\/clip\/([A-Za-z0-9_-]+)\/?$/i);
          if (match) url = `https://www.twitch.tv/${match[1]}/clip/${match[2]}`;
        }
      }
      break;
    case "Dailymotion":
      match = path.match(/^\/(?:video\/)?([A-Za-z0-9]+)\/?$/);
      if (match) url = `https://www.dailymotion.com/video/${match[1]}`;
      break;
    case "Streamable":
      match = path.match(/^\/([A-Za-z0-9]+)\/?$/);
      if (match) url = `https://streamable.com/${match[1]}`;
      break;
  }
  return url ? { url, platform } : null;
}

// Retained for integrations depending on the old helper.
export function parseInstagramUrl(text) {
  const parsed = parseVideoUrl(text);
  return parsed?.platform === "Instagram" ? parsed.url : null;
}

export function constantTimeEqual(a, b) {
  if (typeof a !== "string" || typeof b !== "string") return false;
  let different = a.length ^ b.length;
  const n = Math.max(a.length, b.length);
  for (let i = 0; i < n; i++) different |= (a.charCodeAt(i) || 0) ^ (b.charCodeAt(i) || 0);
  return different === 0;
}

async function encryptDispatch(data, keyBase64url) {
  const secret = decodeBase64Url(keyBase64url);
  if (secret.length !== 32) throw new Error("PIPELINE_KEY must decode to 32 bytes");
  const key = await crypto.subtle.importKey("raw", secret, "AES-GCM", false, ["encrypt"]);
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const bytes = new TextEncoder().encode(JSON.stringify(data));
  const ciphertext = new Uint8Array(await crypto.subtle.encrypt({ name: "AES-GCM", iv }, key, bytes));
  return `${base64Url(iv)}.${base64Url(ciphertext)}`;
}

async function sendTelegram(env, chatId, message) {
  const response = await fetch(`${TELEGRAM_API}/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chat_id: chatId, text: message, disable_web_page_preview: true }),
  });
  if (!response.ok) throw new Error(`Telegram API status ${response.status}`);
}

async function dispatchGitHub(env, payload) {
  const repo = `${encodeURIComponent(env.GITHUB_OWNER)}/${encodeURIComponent(env.GITHUB_REPO)}`;
  const res = await fetch(`https://api.github.com/repos/${repo}/actions/workflows/transfer.yml/dispatches`, {
    method: "POST",
    headers: {
      "Accept": "application/vnd.github+json",
      "Authorization": `Bearer ${env.GITHUB_TOKEN}`,
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "instagram-drive-telegram-bot",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ ref: "main", inputs: { payload } }),
  });
  if (res.status !== 204) throw new Error(`GitHub dispatch status ${res.status}`);
}

export default {
  async fetch(request, env) {
    const path = new URL(request.url).pathname;
    if (request.method === "GET" && path === "/health") return new Response("ok", { status: 200 });
    if (request.method !== "POST" || path !== "/telegram") return new Response("Not found", { status: 404 });
    if (!env.TELEGRAM_WEBHOOK_SECRET || !constantTimeEqual(request.headers.get("X-Telegram-Bot-Api-Secret-Token"), env.TELEGRAM_WEBHOOK_SECRET)) {
      return new Response("Unauthorized", { status: 401 });
    }
    let update;
    try { update = await request.json(); } catch { return new Response("Bad JSON", { status: 400 }); }
    const message = update?.message;
    if (!message) return new Response("ok");
    // Owner-initiated compatibility check only. Never dispatch group uploads.
    if (["group", "supergroup"].includes(message.chat?.type)) {
      if (message.chat?.title !== "Video Bridge") return new Response("ok");
      const sender = message.from;
      const reply = message.reply_to_message;
      if (String(sender?.id) === String(env.TELEGRAM_ALLOWED_USER_ID) &&
          !sender?.is_bot &&
          /^\/bridgecheck@hazemdownloaderbot$/i.test((message.text || "").trim())) {
        try {
          await sendTelegram(env, message.chat.id, "/help@download_it_bot");
          await sendTelegram(env, env.TELEGRAM_ALLOWED_USER_ID,
            "✅ وصلت إلى مجموعة Video Bridge وأرسلت أمر المساعدة الرسمي إلى Download IT. إذا ظهر رد في المجموعة، فالتواصل ممكن.");
        } catch {
          try { await sendTelegram(env, env.TELEGRAM_ALLOWED_USER_ID,
            "تعذّر إرسال اختبار التواصل إلى المجموعة."); } catch { /* ignore */ }
        }
      } else if (sender?.is_bot && sender.username?.toLowerCase() === "download_it_bot" &&
          reply?.from?.is_bot && reply.from.username?.toLowerCase() === "hazemdownloaderbot" &&
          reply?.text === "/help@download_it_bot") {
        try { await sendTelegram(env, env.TELEGRAM_ALLOWED_USER_ID,
          "✅ استلمت رداً مباشراً من Download IT داخل Video Bridge. نجح اختبار التواصل بين البوتين."); } catch { /* ignore */ }
      }
      return new Response("ok");
    }
    if (message.chat?.type !== "private") return new Response("ok");
    if (String(message.from?.id) !== String(env.TELEGRAM_ALLOWED_USER_ID) ||
        String(message.chat?.id) !== String(env.TELEGRAM_ALLOWED_USER_ID)) return new Response("ok");
    const chatId = message.chat.id;
    const text = message.text || message.caption || "";
    if (text.trim() === "/start" || text.trim() === "/help") {
      await sendTelegram(env, chatId, "🎬 أرسل رابط فيديو عام من Instagram أو YouTube/Shorts أو Facebook أو TikTok أو X أو Reddit أو Vimeo أو Twitch، وسأحفظه في Google Drive. أدعم أيضاً Dailymotion وStreamable. الحد الأقصى 250MB، والروابط الخاصة أو المحمية قد لا تعمل.");
      return new Response("ok");
    }
    const media = parseVideoUrl(text);
    if (!media) {
      await sendTelegram(env, chatId, "❌ الرابط غير مدعوم. أرسل رابط فيديو عام بصيغة HTTPS من Instagram أو YouTube أو Facebook أو TikTok أو X أو Reddit أو Vimeo أو Twitch (أو Dailymotion وStreamable). لا أدعم البث المباشر أو الروابط الخاصة.");
      return new Response("ok");
    }
    try {
      const payload = await encryptDispatch({ url: media.url, chat_id: String(chatId) }, env.PIPELINE_KEY);
      await dispatchGitHub(env, payload);
      await sendTelegram(env, chatId, `✅ استلمت رابط ${media.platform}. بدأت مهمة التنزيل والحفظ في Google Drive، وسأرسل الرابط عند الانتهاء.`);
    } catch (err) {
      console.error("Dispatch/notification failed:", err?.name || "Error");
      try { await sendTelegram(env, chatId, "تعذّر بدء المهمة. تحقق من إعدادات Cloudflare وGitHub."); } catch { /* ignore */ }
    }
    return new Response("ok");
  },
};
