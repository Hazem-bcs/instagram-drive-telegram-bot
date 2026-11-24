import {test} from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {readFileSync} from 'node:fs';
import worker from '../worker/src/index.js';

test('YouTube queue preserves links, authenticates, leases, expires and completes; rejects other senders', async () => {
  const sqlite = new DatabaseSync(':memory:');
  sqlite.exec(readFileSync(new URL('../worker/migrations/001_youtube_queue.sql', import.meta.url),'utf8'));
  const db = {prepare(sql) {return {bind(...args) {
    return {first:async()=>sqlite.prepare(sql).get(...args),
            run:async()=>sqlite.prepare(sql).run(...args)};
  }};}};
  const env = {YOUTUBE_QUEUE:db,YOUTUBE_QUEUE_TOKEN:'queue-secret',TELEGRAM_WEBHOOK_SECRET:'hook-secret',
               TELEGRAM_ALLOWED_USER_ID:'123',TELEGRAM_BOT_TOKEN:'mock'};
  const originalFetch=globalThis.fetch;
  const sent=[];
  globalThis.fetch=async(url,opts)=>{
    assert.ok(String(url).includes('api.telegram.org'));
    sent.push(JSON.parse(opts.body));return new Response('{"ok":true}');
  };
  const submit = (id,user) => worker.fetch(new Request('https://example.com/telegram',{
    method:'POST',headers:{'X-Telegram-Bot-Api-Secret-Token':'hook-secret'},
    body:JSON.stringify({update_id:id,message:{from:{id:user},chat:{id:user,type:'private'},text:'https://youtu.be/nYYitW53CXI?x=1'}})
  }),env);
  const api = (path,body={},auth='queue-secret')=>worker.fetch(new Request('https://example.com/youtube/'+path,{
    method:'POST',headers:{Authorization:'Bearer '+auth,'Content-Type':'application/json'},body:JSON.stringify(body)
  }),env);
  try {
    await submit(1,456);assert.equal(sent.length,0);
    assert.equal((await api('claim',{},'bad')).status,401);
    assert.equal((await (await api('claim')).json()).job,null);
    await submit(2,123);await submit(2,123);
    let job=(await (await api('claim')).json()).job;
    assert.equal(job.id,'2');assert.equal(job.url,'https://www.youtube.com/watch?v=nYYitW53CXI');
    assert.equal((await (await api('claim')).json()).job,null);
    sqlite.exec('UPDATE youtube_jobs SET lease_until=0');
    let reclaimed=(await (await api('claim')).json()).job;
    assert.notEqual(reclaimed.lease_token,job.lease_token);
    assert.equal((await api('finish',{id:job.id,lease_token:job.lease_token,file_id:'fakeDriveId1234'})).status,409);
    assert.equal((await api('finish',{id:reclaimed.id,lease_token:reclaimed.lease_token,file_id:'fakeDriveId1234'})).status,200);
    assert.equal((await (await api('claim')).json()).job,null);
    assert.equal(sqlite.prepare('SELECT url,state FROM youtube_jobs WHERE id=?').get('2').url,'');
    assert.equal(sqlite.prepare('SELECT state FROM youtube_jobs WHERE id=?').get('2').state,'done');
    assert.ok(sent.at(-1).text.includes('drive.google.com/file/d/fakeDriveId1234/view'));
  } finally {globalThis.fetch=originalFetch;sqlite.close();}
});
