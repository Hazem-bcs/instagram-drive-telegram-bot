const HEADERS = {"Content-Type":"application/json", "Cache-Control":"no-store"};
const response = (status, data) => Response.json(data, {status, headers: HEADERS});
const validVideo = id => typeof id === "string" && /^[A-Za-z0-9_-]{11}$/.test(id);
const validDrive = id => typeof id === "string" && /^[A-Za-z0-9_-]{10,150}$/.test(id);
export async function enqueueYoutube(env, url) {
  const id = new URL(url).searchParams.get("v");
  if (!validVideo(id)) throw new Error("Invalid YouTube ID");
  await env.YOUTUBE_QUEUE.prepare(
    "INSERT INTO youtube_jobs(video_id,url) VALUES (?,?) ON CONFLICT(video_id) DO NOTHING"
  ).bind(id,url).run();
  return env.YOUTUBE_QUEUE.prepare("SELECT drive_id FROM youtube_jobs WHERE video_id=?").bind(id).first();
}
export async function queueRequest(request, env, compare, notify) {
  if (!env.QUEUE_ACCESS_KEY || !env.YOUTUBE_QUEUE ||
      !compare(request.headers.get("Authorization"),"Bearer "+env.QUEUE_ACCESS_KEY))
    return response(401,{error:"unauthorized"});
  const path = new URL(request.url).pathname;
  const db = env.YOUTUBE_QUEUE;
  if (request.method === "GET" && path === "/queue/jobs") {
    const result = await db.prepare("SELECT video_id FROM youtube_jobs WHERE drive_id IS NULL AND lease_until<=unixepoch() ORDER BY created_at LIMIT 50").all();
    return response(200,{jobs:result.results});
  }
  if (request.method !== "POST") return response(405,{error:"method"});
  const text = await request.text();
  if (text.length > 4096) return response(400,{error:"invalid_body"});
  let data;
  try { data = JSON.parse(text); } catch { return response(400,{error:"invalid_json"}); }
  if (!data || !validVideo(data.video_id)) return response(400,{error:"invalid_id"});
  const id = data.video_id;
  if (path === "/queue/claim") {
    const lease = crypto.randomUUID();
    const job = await db.prepare("UPDATE youtube_jobs SET lease=?,lease_until=unixepoch()+1800 WHERE video_id=? AND drive_id IS NULL AND lease_until<=unixepoch() RETURNING video_id,url").bind(lease,id).first();
    return job ? response(200,{...job,lease}) : response(409,{error:"not_available"});
  }
  if (typeof data.lease !== "string" || !/^[a-f0-9-]{36}$/.test(data.lease))
    return response(400,{error:"invalid_lease"});
  if (path === "/queue/release") {
    const job = await db.prepare("UPDATE youtube_jobs SET lease=NULL,lease_until=0 WHERE video_id=? AND lease=? AND drive_id IS NULL RETURNING video_id").bind(id,data.lease).first();
    return response(job?200:409,{released:!!job});
  }
  if (path === "/queue/complete" && validDrive(data.drive_id)) {
    // Retain the completed Drive ID to deduplicate repeat submissions.
    const job = await db.prepare("UPDATE youtube_jobs SET drive_id=?,lease_until=0 WHERE video_id=? AND lease=? AND drive_id IS NULL RETURNING video_id").bind(data.drive_id,id,data.lease).first();
    if (!job) return response(409,{error:"not_available"});
    let notified = true;
    try { await notify(env,env.TELEGRAM_ALLOWED_USER_ID,"✅ تم حفظ فيديو YouTube في Google Drive.\n🎬 https://drive.google.com/file/d/"+data.drive_id+"/view"); } catch { notified=false; }
    return response(200,{completed:true,notified});
  }
  return response(404,{error:"not_found"});
}
