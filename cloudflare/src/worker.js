// mini-lang 網站 Worker：靜態資產 + D1 API（含 FTS5 全文檢索）
// 部署目標：Cloudflare Workers（本機用 rucloud dev 測試）

const LANGS = new Set(["zh", "en", "fr", "ja", "ko"]);
const CJK_RE = /[\u4e00-\u9fff\u3040-\u30ff\u3400-\u4dbf]/;

function json(obj, status = 200) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { "content-type": "application/json; charset=utf-8" },
  });
}

async function readBody(request) {
  try {
    return await request.json();
  } catch {
    return {};
  }
}

// ---- 查詢字串 → FTS5 MATCH 語法 ----------------------------------------
// 中文／日文：body 已逐字切開，查詢也切成字，用 phrase 保證連續
// 英／法／韓：body 是詞，查詢用 prefix（tok*），法文先去變音符號
function stripDiacritics(s) {
  // NFD 去拉丁變音符；NFC 會把韓文 Jamo 重組回音節（NFD 會拆開韓文）
  return s.normalize("NFD").replace(/[\u0300-\u036f]/g, "").normalize("NFC");
}

function cjkMatch(q) {
  const chars = [...q].filter((c) => CJK_RE.test(c));
  const latin = stripDiacritics(q.toLowerCase()).match(/[a-z0-9]+/g) || [];
  const parts = [];
  if (chars.length) parts.push(`"${chars.join(" ")}"`);
  if (latin.length) parts.push(latin.map((t) => `${t}*`).join(" AND "));
  return parts.join(" OR ");
}

function latinMatch(q) {
  const toks = stripDiacritics(q.toLowerCase()).match(/[a-z0-9가-힣]+/g) || [];
  if (!toks.length) return "";
  return toks.map((t) => `${t}*`).join(" AND ");
}

function buildMatch(q, lang) {
  if (lang === "zh" || lang === "ja") return cjkMatch(q);
  if (lang === "en" || lang === "fr" || lang === "ko") return latinMatch(q);
  // all：含 CJK 就用逐字 phrase，否則用詞前綴
  return CJK_RE.test(q) ? cjkMatch(q) : latinMatch(q);
}

// ---- API ----------------------------------------------------------------

async function apiTopics(env) {
  const { results } = await env.DB.prepare(
    `SELECT tp.id, tp.slug, tp.title_zh, tp.title_en, COUNT(t.id) AS total
     FROM topics tp LEFT JOIN turns t ON t.topic_id = tp.id
     GROUP BY tp.id ORDER BY tp.ord`
  ).all();
  return json({ topics: results });
}

async function apiLesson(env, slug) {
  const topic = await env.DB.prepare(
    "SELECT id, slug, title_zh, title_en FROM topics WHERE slug = ?1"
  ).bind(slug).first();
  if (!topic) return json({ error: "topic not found" }, 404);
  const { results } = await env.DB.prepare(
    "SELECT id, idx, speaker, zh, en, fr, ja, ko, ruby FROM turns WHERE topic_id = ?1 ORDER BY idx"
  ).bind(topic.id).all();
  for (const r of results) r.ruby = JSON.parse(r.ruby || "{}");
  return json({ topic, turns: results });
}

async function apiSearch(env, url) {
  const q = (url.searchParams.get("q") || "").trim();
  const lang = url.searchParams.get("lang") || "all";
  const topic = url.searchParams.get("topic") || "all";
  if (!q) return json({ results: [] });
  const match = buildMatch(q, lang);
  if (!match) return json({ results: [] });

  const binds = [match];
  let sql = `
    SELECT f.turn_id AS turnId, f.lang AS lang,
           t.idx, t.speaker, t.zh, t.en, t.fr, t.ja, t.ko, t.ruby,
           tp.slug, tp.title_zh, tp.title_en
    FROM turns_fts AS f
    JOIN turns t ON t.id = f.turn_id
    JOIN topics tp ON tp.id = t.topic_id
    WHERE turns_fts MATCH ?1`;
  if (lang !== "all") {
    binds.push(lang);
    sql += ` AND f.lang = ?${binds.length}`;
  }
  if (topic !== "all") {
    binds.push(topic);
    sql += ` AND tp.slug = ?${binds.length}`;
  }
  sql += " ORDER BY rank LIMIT 60";
  const { results } = await env.DB.prepare(sql).bind(...binds).all();
  for (const r of results) {
    try {
      r.ruby = JSON.parse(r.ruby || "{}");
    } catch {
      r.ruby = {};
    }
  }
  return json({ results, match });
}

async function apiVocab(env, url) {
  const lang = url.searchParams.get("lang") || "all";
  const q = (url.searchParams.get("q") || "").trim();
  const binds = [];
  let sql = "SELECT lang, term, reading FROM vocab WHERE 1=1";
  if (lang !== "all") {
    binds.push(lang);
    sql += ` AND lang = ?${binds.length}`;
  }
  if (q) {
    binds.push(`%${q}%`);
    sql += ` AND (term LIKE ?${binds.length} OR reading LIKE ?${binds.length})`;
  }
  sql += " ORDER BY lang, term LIMIT 800";
  const { results } = await env.DB.prepare(sql).bind(...binds).all();
  return json({ results });
}

async function apiQuiz(env, url) {
  const from = url.searchParams.get("from") || "zh";
  const to = url.searchParams.get("to") || "en";
  const topic = url.searchParams.get("topic") || "all";
  const n = Math.min(Math.max(parseInt(url.searchParams.get("n") || "8", 10), 1), 20);
  if (!LANGS.has(from) || !LANGS.has(to) || from === to) {
    return json({ error: "from/to 必須是 zh en fr ja ko 且不同" }, 400);
  }
  const col = (l) => (l === "zh" ? "zh" : l === "en" ? "en" : l === "fr" ? "fr" : l === "ja" ? "ja" : "ko");
  const binds = [];
  let sql = `SELECT id, ${col(from)} AS q, ${col(to)} AS a FROM turns`;
  if (topic !== "all") {
    binds.push(topic);
    sql += ` WHERE topic_id = (SELECT id FROM topics WHERE slug = ?1)`;
  }
  sql += ` ORDER BY RANDOM() LIMIT ${n * 6}`;
  const { results } = await env.DB.prepare(sql).bind(...binds).all();

  const questions = [];
  let i = 0;
  while (i < results.length && questions.length < n) {
    const correct = results[i];
    if (!correct.a) { i++; continue; }
    const opts = [correct.a];
    let j = i + 1;
    while (j < results.length && opts.length < 4) {
      const a = results[j].a;
      if (a && !opts.includes(a)) opts.push(a);
      j++;
    }
    if (opts.length === 4) {
      const order = opts.map((text, k) => ({ text, k })).sort(() => Math.random() - 0.5);
      questions.push({
        turnId: correct.id,
        q: correct.q,
        options: order.map((o) => o.text),
        answer: order.findIndex((o) => o.k === 0),
      });
      i = j;
    } else {
      i++;
    }
  }
  return json({ from, to, questions });
}

async function apiProgressGet(env, url) {
  const device = url.searchParams.get("device") || "";
  if (!device) return json({ progress: [] });
  const { results } = await env.DB.prepare(
    "SELECT turn_id AS turnId, stars FROM progress WHERE device = ?1"
  ).bind(device).all();
  return json({ progress: results });
}

async function apiProgressPost(env, request) {
  const body = await readBody(request);
  const device = String(body.device || "").slice(0, 64);
  const turnId = parseInt(body.turnId, 10);
  const stars = body.stars ? 1 : 0;
  if (!device || !turnId) return json({ error: "device 與 turnId 必填" }, 400);
  await env.DB.prepare(
    `INSERT INTO progress(device, turn_id, stars, ts) VALUES(?1, ?2, ?3, ?4)
     ON CONFLICT(device, turn_id) DO UPDATE SET stars = excluded.stars, ts = excluded.ts`
  ).bind(device, turnId, stars, Date.now()).run();
  return json({ ok: true });
}

async function apiQuizLogPost(env, request) {
  const body = await readBody(request);
  const device = String(body.device || "").slice(0, 64);
  const turnId = parseInt(body.turnId, 10);
  const correct = body.correct ? 1 : 0;
  if (!device || !turnId) return json({ error: "device 與 turnId 必填" }, 400);
  await env.DB.prepare(
    "INSERT INTO quiz_log(device, turn_id, correct, ts) VALUES(?1, ?2, ?3, ?4)"
  ).bind(device, turnId, correct, Date.now()).run();
  return json({ ok: true });
}

async function apiStats(env, url) {
  const device = url.searchParams.get("device") || "";
  const { results } = await env.DB.prepare(
    `SELECT tp.slug, tp.title_zh, tp.title_en,
            COUNT(t.id) AS total,
            SUM(CASE WHEN p.stars > 0 THEN 1 ELSE 0 END) AS starred
     FROM topics tp
     LEFT JOIN turns t ON t.topic_id = tp.id
     LEFT JOIN progress p ON p.turn_id = t.id AND p.device = ?1
     GROUP BY tp.id ORDER BY tp.ord`
  ).bind(device).all();
  const quiz = (await env.DB.prepare(
    "SELECT COUNT(*) AS total, SUM(correct) AS correct FROM quiz_log WHERE device = ?1"
  ).bind(device).first()) || { total: 0, correct: 0 };
  return json({ topics: results, quiz });
}

// ---- 路由 ----------------------------------------------------------------

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname;

    if (path.startsWith("/api/")) {
      try {
        if (path === "/api/topics" && request.method === "GET") return await apiTopics(env);
        if (path.startsWith("/api/lesson/") && request.method === "GET")
          return await apiLesson(env, decodeURIComponent(path.slice("/api/lesson/".length)));
        if (path === "/api/search" && request.method === "GET") return await apiSearch(env, url);
        if (path === "/api/vocab" && request.method === "GET") return await apiVocab(env, url);
        if (path === "/api/quiz" && request.method === "GET") return await apiQuiz(env, url);
        if (path === "/api/progress" && request.method === "GET") return await apiProgressGet(env, url);
        if (path === "/api/progress" && request.method === "POST") return await apiProgressPost(env, request);
        if (path === "/api/quizlog" && request.method === "POST") return await apiQuizLogPost(env, request);
        if (path === "/api/stats" && request.method === "GET") return await apiStats(env, url);
        return json({ error: "not found" }, 404);
      } catch (e) {
        return json({ error: String(e && e.message || e) }, 500);
      }
    }

    // 其餘走靜態資產（public/）
    return env.ASSETS.fetch(request);
  },
};
