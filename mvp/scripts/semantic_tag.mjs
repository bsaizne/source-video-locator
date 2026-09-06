#!/usr/bin/env node
// semantic_tag.mjs — 批量视觉语义标签（复用 vision-subagent 的方舟配置）
import { readFile } from 'node:fs/promises';
import { readFileSync, writeFileSync } from 'node:fs';
import { extname } from 'node:path';

const CONFIG = JSON.parse(readFileSync('D:/deepseek harnees/vision-subagent/vision-mcp-config.json', 'utf8'));
const MANIFEST = 'D:/claudework/benchmark/work/semantic_probe/manifest.json';
const OUT = 'D:/claudework/benchmark/work/semantic_probe/labels.json';

const base = CONFIG.base, key = CONFIG.apiKey, model = CONFIG.model;
const only = process.argv[2] || null;   // 可选: 只处理某 id,如 n01

const PROMPT = '这是视频中的一帧画面。请只输出一个 JSON 对象（不要多余文字），字段：' +
  '{"scene":"场景类别(如室内/室外/森林/街道/夜晚/白天/水下/天空等)","subject":"主体描述(20字内)",' +
  '"face":"无/单人/多人/模糊","objects":["关键物体1","关键物体2"],"text":"画面中可见文字或无"}';

async function tagImage(p) {
  const buf = await readFile(p);
  const ext = extname(p).toLowerCase();
  const mime = { '.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg' }[ext] || 'image/png';
  const dataUrl = 'data:' + mime + ';base64,' + buf.toString('base64');
  const res = await fetch(base + '/chat/completions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key },
    body: JSON.stringify({ model, messages: [{ role:'user', content:[
      { type:'text', text: PROMPT },
      { type:'image_url', image_url:{ url: dataUrl } },
    ]}], max_tokens: 400 }),
  });
  if (!res.ok) throw new Error('HTTP ' + res.status + ': ' + (await res.text()).slice(0,300));
  const data = await res.json();
  return data?.choices?.[0]?.message?.content || '';
}

const manifest = JSON.parse(readFileSync(MANIFEST, 'utf8'));
const items = only ? manifest.filter(m => m.id === only) : manifest;
const labels = [];
for (const m of items) {
  try {
    const raw = await tagImage(m.path);
    // 提取 JSON 部分
    const j = raw.match(/{[sS]*}/);
    let obj = null;
    if (j) { try { obj = JSON.parse(j[0]); } catch { obj = { raw: raw.slice(0, 200) }; } }
    labels.push({ id: m.id, side: m.side, frame: m.frame, video: m.video, time: m.time, label: obj || raw.slice(0,200) });
    console.log('OK', m.id, m.side + m.frame, '=>', JSON.stringify(obj || raw.slice(0,120)));
  } catch (e) {
    labels.push({ id: m.id, side: m.side, frame: m.frame, error: String(e.message) });
    console.log('ERR', m.id, m.side + m.frame, e.message);
  }
}
if (!only) writeFileSync(OUT, JSON.stringify(labels, null, 1), 'utf8');
