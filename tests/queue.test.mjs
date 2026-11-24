import { test } from "node:test";
import assert from "node:assert/strict";
import { DatabaseSync } from "node:sqlite";
import { readFileSync } from "node:fs";
import worker, { constantTimeEqual } from "../worker/src/index.js";
import { enqueueYoutube, queueRequest } from "../worker/src/youtube_queue.js";
function db() {
  const sqlite = new DatabaseSync(":memory:");
  sqlite.exec(readFileSync(new URL("../migrations/0001_youtube_queue.sql",import.meta.url),"utf8"));
  return {prepare(sql){ return {bind(...args){return {
    async first(){return sqlite.prepare(sql).get(...args) ?? null},
    async run(){return sqlite.prepare(sql).run(...args)},
    async all(){return {results:sqlite.prepare(sql).all(...args)}}
  }},async all(){return {results:sqlite.prepare(sql).all()}}}}};
}
test("queue requires authentication, leases jobs once, releases and deduplicates completed videos",async()=>{
  const env={YOUTUBE_QUEUE:db(),QUEUE_ACCESS_KEY:"test",TELEGRAM_ALLOWED_USER_ID:"123"};
  const notices=[];
  const notify=async(...args)=>notices.push(args);
  const request=(path,data,auth="Bearer test")=>queueRequest(new Request("https://example.com/queue/"+path,{headers:{Authorization:auth},method:data===undefined?"GET":"POST",body:data===undefined?undefined:JSON.stringify(data)}),env,constantTimeEqual,notify);
  const url="https://www.youtube.com/watch?v=dQw4w9WgXcQ", video_id="dQw4w9WgXcQ";
  assert.equal((await request("jobs",undefined,"Bearer wrong")).status,401);
  await enqueueYoutube(env,url);
  await enqueueYoutube(env,url);
  assert.equal((await (await request("jobs")).json()).jobs.length,1);
  const claimed=await (await request("claim",{video_id})).json();
  assert.equal(claimed.url,url);
  assert.equal((await request("claim",{video_id})).status,409);
  assert.equal((await request("release",{video_id,lease:"00000000-0000-0000-0000-000000000000"})).status,409);
  assert.equal((await request("release",{video_id,lease:claimed.lease})).status,200);
  const claimed2=await (await request("claim",{video_id})).json();
  const drive_id="example_drive_id";
  assert.equal((await request("complete",{video_id,lease:claimed2.lease,drive_id})).status,200);
  assert.equal(notices.length,1);
  assert.equal((await enqueueYoutube(env,url)).drive_id,drive_id);
  assert.equal((await (await request("jobs")).json()).jobs.length,0);
});
test("owner YouTube messages queue only when feature enabled, and never dispatch GitHub",async()=>{
  const original=globalThis.fetch;
  const calls=[];
  globalThis.fetch=async(url,options)=>{calls.push(String(url));return new Response('{"ok":true}',{status:200})};
  try{
    const env={YOUTUBE_QUEUE:db(),YOUTUBE_QUEUE_ENABLED:"true",QUEUE_ACCESS_KEY:"test",TELEGRAM_WEBHOOK_SECRET:"secret",TELEGRAM_ALLOWED_USER_ID:"123",TELEGRAM_BOT_TOKEN:"mock"};
    const message={chat:{id:123,type:"private"},from:{id:123},text:"https://youtu.be/dQw4w9WgXcQ"};
    const send=msg=>worker.fetch(new Request("https://example.com/telegram",{method:"POST",headers:{"X-Telegram-Bot-Api-Secret-Token":"secret"},body:JSON.stringify({message:msg})}),env);
    await send({...message,from:{id:456}});
    assert.equal((await env.YOUTUBE_QUEUE.prepare("SELECT * FROM youtube_jobs").all()).results.length,0);
    await send(message);
    assert.equal((await env.YOUTUBE_QUEUE.prepare("SELECT * FROM youtube_jobs").all()).results.length,1);
    assert.equal(calls.length,1);
    assert.ok(calls[0].includes("api.telegram.org"));
  }finally{globalThis.fetch=original}
});
