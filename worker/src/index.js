/** Telegram webhook -> encrypted GitHub workflow_dispatch. Runs on Cloudflare Workers. */
const TELEGRAM_API = "https://api.telegram.org";

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

export function parseInstagramUrl(text) {
  if (typeof text !== "string" || text.length > 3500) return null;
  const raw = text.match(/https?:\/\/[^\s<>"']+/i)?.[0]?.replace(/[),.!؟،]+$/, "");
  if (!raw) return null;
  try {
    const url = new URL(raw);
    if (url.protocol !== "https:") return null;
    if (!["instagram.com", "www.instagram.com", "m.instagram.com"].includes(url.hostname.toLowerCase())) return null;
    const match = url.pathname.match(/^\/(reel|reels|p|tv)\/([A-Za-z0-9_-]+)\/?$/i);
    if (!match) return null;
    return `https://www.instagram.com/${match[1].toLowerCase()}/${match[2]}/`;
  } catch { return null; }
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
    if (!message || message.chat?.type !== "private") return new Response("ok");
    // Never run a job for somebody else's Telegram account.
    if (String(message.from?.id) !== String(env.TELEGRAM_ALLOWED_USER_ID) ||
        String(message.chat?.id) !== String(env.TELEGRAM_ALLOWED_USER_ID)) return new Response("ok");
    const chatId = message.chat.id;
    const text = message.text || message.caption || "";
    if (text.trim() === "/start" || text.trim() === "/help") {
      await sendTelegram(env, chatId, "أرسل رابط Reel عام من Instagram وسأحفظ الفيديو في Google Drive وأعيد لك الرابط. الروابط الخاصة قد لا تعمل.");
      return new Response("ok");
    }
    const url = parseInstagramUrl(text);
    if (!url) {
      await sendTelegram(env, chatId, "أرسل رابط Instagram صالحاً من نوع /reel/ أو /p/ أو /tv/.");
      return new Response("ok");
    }
    try {
      const payload = await encryptDispatch({ url, chat_id: String(chatId) }, env.PIPELINE_KEY);
      await dispatchGitHub(env, payload);
      await sendTelegram(env, chatId, "✅ استلمت الرابط. بدأت مهمة الحفظ، وسأرسل رابط Google Drive بعد اكتمالها.");
    } catch (err) {
      // Avoid exposing auth tokens or private data in logs/messages.
      console.error("Dispatch/notification failed:", err?.name || "Error");
      try { await sendTelegram(env, chatId, "تعذّر بدء المهمة. تحقق من إعدادات Cloudflare وGitHub."); } catch { /* ignore */ }
    }
    return new Response("ok");
  },
};
