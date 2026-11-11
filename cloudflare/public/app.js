// mini-x 學習網前端（無框架、無 build）
"use strict";

// ---- 基礎 ---------------------------------------------------------------

const LANG_LABEL = { zh: "中", en: "英", fr: "法", ja: "日", ko: "韓" };
const LANG_ORDER = ["zh", "en", "fr", "ja", "ko"];
const TTS_LANG = { zh: "zh-TW", en: "en-US", fr: "fr-FR", ja: "ja-JP", ko: "ko-KR" };

const $app = document.getElementById("app");

function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&" + "amp;", "<": "&" + "lt;", ">": "&" + "gt;", '"': "&" + "quot;", "'": "&" + "#39;",
  }[c]));
}

function device() {
  let d = localStorage.getItem("mx_device");
  if (!d) {
    d = "d" + Math.random().toString(36).slice(2, 10) + Date.now().toString(36);
    localStorage.setItem("mx_device", d);
  }
  return d;
}

async function api(path, opts) {
  const res = await fetch(path, opts);
  if (!res.ok) throw new Error(`${path}: ${res.status}`);
  return res.json();
}

// ---- 設定（語言顯示 / ruby / 遮罩） --------------------------------------

const settings = {
  langs: JSON.parse(localStorage.getItem("mx_langs") || '["zh","en","fr","ja","ko"]'),
  ruby: JSON.parse(localStorage.getItem("mx_ruby") || '{"zh":true,"ja":true,"ko":true}'),
  mask: localStorage.getItem("mx_mask") === "1",
};
function saveSettings() {
  localStorage.setItem("mx_langs", JSON.stringify(settings.langs));
  localStorage.setItem("mx_ruby", JSON.stringify(settings.ruby));
  localStorage.setItem("mx_mask", settings.mask ? "1" : "0");
}

// ---- ruby 渲染 ----------------------------------------------------------

function isPunct(seg) {
  return /^[。，、！？…「」『』（）・，．,.!?;:；：~～"'\s]+$/.test(seg);
}

function rubyZh(pairs) {
  return (pairs || [])
    .map(([c, p]) => (p ? `<ruby>${esc(c)}<rt>${esc(p)}</rt></ruby>` : esc(c)))
    .join("");
}

function rubyWord(pairs) {
  // 詞與詞之間補空格；純標點不加空格
  let html = "";
  let prev = "";
  for (const [tok, r] of pairs || []) {
    if (!tok) continue;
    const body = r ? `<ruby>${esc(tok)}<rt>${esc(r)}</rt></ruby>` : esc(tok);
    if (html && !isPunct(tok) && !isPunct(prev)) html += " ";
    html += body;
    prev = tok;
  }
  return html;
}

function renderLine(lang, text, ruby, withRuby) {
  if (lang === "zh") {
    return withRuby ? rubyZh(ruby && ruby.zh) : esc(text);
  }
  if (lang === "ja") {
    return withRuby ? rubyWord(ruby && ruby.ja) : esc(text);
  }
  if (lang === "ko") {
    return withRuby ? rubyWord(ruby && ruby.ko) : esc(text);
  }
  return esc(text);
}

// ---- TTS ----------------------------------------------------------------

let voices = [];
function loadVoices() {
  voices = "speechSynthesis" in window ? speechSynthesis.getVoices() : [];
  repopulateVoiceSelects();
}
if ("speechSynthesis" in window) {
  loadVoices();
  speechSynthesis.onvoiceschanged = loadVoices;
}

// 品質差的系統音色直接扣分；神經／雲端語音加分
const BAD_VOICES = /fred|albert|zarvox|trinoids|bells|organ|deranged|hysterical|junior|ralph|agnes|kathy|bad news|whisper|bahh|boing|bubbles|cellos|jester|wobble|good news|sandy|eddy|reed|rocko|shelley|grandma|grandpa|flo|superstar|espeak|pico/i;
const GOOD_VOICES = /natural|premium|enhanced|neural|google|microsoft|samantha|alex|daniel|karen|moira|tessa|fiona|aria|jenny|guy|sonia|libby|yuna|kyoko|otoya|meijia|sinnie|yuna/i;

function voicesFor(lang) {
  const prefix = (TTS_LANG[lang] || "en-US").slice(0, 2).toLowerCase();
  return voices.filter((v) => (v.lang || "").toLowerCase().startsWith(prefix));
}

function pickVoice(lang) {
  const list = voicesFor(lang);
  if (!list.length) return null;
  const saved = localStorage.getItem("mx_voice_" + lang);
  if (saved) {
    const hit = list.find((v) => v.voiceURI === saved);
    if (hit) return hit;
  }
  const exact = (TTS_LANG[lang] || "").toLowerCase();
  const scored = list
    .map((v) => {
      let s = 0;
      const n = (v.name || "").toLowerCase();
      if ((v.lang || "").toLowerCase() === exact) s += 3;
      if (GOOD_VOICES.test(n)) s += 5;
      if (BAD_VOICES.test(n)) s -= 10;
      if (v.default) s += 1;
      return [s, v];
    })
    .sort((a, b) => b[0] - a[0]);
  return scored[0][1];
}

// Chrome/Safari 的 getVoices() 剛載入常是空的；講之前先確保清單到手
function ensureVoices(cb) {
  if (voices.length) return cb();
  voices = speechSynthesis.getVoices() || [];
  if (voices.length) {
    repopulateVoiceSelects();
    return cb();
  }
  let done = false;
  const finish = () => {
    if (done) return;
    done = true;
    speechSynthesis.onvoiceschanged = loadVoices;
    voices = speechSynthesis.getVoices() || [];
    repopulateVoiceSelects();
    cb();
  };
  speechSynthesis.onvoiceschanged = finish;
  setTimeout(finish, 500); // 清單一直不來也要講話，不能卡死
}

// 數字 → 英文單字，避免數字被非英文引擎唸成中文
const EN_ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
  "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"];
const EN_TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"];

function enNumWords(n) {
  if (n < 20) return EN_ONES[n];
  if (n < 100) return EN_TENS[Math.floor(n / 10)] + (n % 10 ? "-" + EN_ONES[n % 10] : "");
  if (n < 1000) {
    return EN_ONES[Math.floor(n / 100)] + " hundred" + (n % 100 ? " and " + enNumWords(n % 100) : "");
  }
  const th = Math.floor(n / 1000);
  return enNumWords(th) + " thousand" + (n % 1000 ? " " + enNumWords(n % 1000) : "");
}

function ttsText(lang, text) {
  if (lang === "en") return text.replace(/\d+/g, (m) => enNumWords(parseInt(m, 10)));
  return text;
}

// ---- 提示訊息 -----------------------------------------------------------

function toast(msg) {
  let t = document.getElementById("mx-toast");
  if (!t) {
    t = document.createElement("div");
    t.id = "mx-toast";
    document.body.appendChild(t);
  }
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(t._timer);
  t._timer = setTimeout(() => t.classList.remove("show"), 5000);
}

const VOICE_HINT =
  "解法：用 Microsoft Edge 開本站（內建全語言線上語音），" +
  "或在 macOS「系統設定 → 輔助使用 → 朗讀內容 → 管理聲音」安裝該語言語音後重開瀏覽器";

function speak(text, lang) {
  if (!("speechSynthesis" in window) || typeof SpeechSynthesisUtterance === "undefined") return;
  speechSynthesis.cancel();
  ensureVoices(() => {
    const u = new SpeechSynthesisUtterance(ttsText(lang, text));
    u.lang = TTS_LANG[lang] || "en-US";
    const v = pickVoice(lang);
    if (v) {
      u.voice = v;
      u.lang = v.lang;
    } else if (voices.length && !voicesFor(lang).length) {
      toast(`此瀏覽器沒有「${LANG_LABEL[lang]}」語音，無法朗讀。${VOICE_HINT}`);
    }
    u.onerror = (e) => {
      if (e.error === "not-allowed") toast("瀏覽器封鎖了語音播放：請先點一下頁面再試");
      else if (e.error === "not-found" || e.error === "voice-unavailable") {
        toast(`找不到「${LANG_LABEL[lang]}」語音。${VOICE_HINT}`);
      } else if (voicesFor(lang).length === 0) {
        toast(`「${LANG_LABEL[lang]}」朗讀失敗（此瀏覽器缺少該語音）。${VOICE_HINT}`);
      } else {
        toast(`語音播放失敗：${e.error || "unknown"}`);
      }
    };
    u.rate = 0.95;
    speechSynthesis.speak(u);
  });
}

// ---- 路由 ---------------------------------------------------------------

function nav(highlight) {
  document.querySelectorAll(".nav a").forEach((a) => {
    a.classList.toggle("active", a.dataset.nav === highlight);
  });
}

function parseHash() {
  const raw = location.hash.slice(1) || "/";
  const [path, query] = raw.split("?");
  return { path, params: new URLSearchParams(query || "") };
}

async function route() {
  const { path, params } = parseHash();
  window.scrollTo(0, 0);
  if (path === "/" || path === "") return viewHome();
  if (path.startsWith("/book/")) return viewBook(decodeURIComponent(path.slice("/book/".length)), params);
  if (path === "/search") return viewSearch(params);
  if (path === "/vocab") return viewVocab(params);
  if (path === "/quiz") return viewQuiz(params);
  if (path === "/stats") return viewStats();
  $app.innerHTML = `<div class="empty">找不到頁面</div>`;
}

window.addEventListener("hashchange", route);

// ---- 工具列（共用） ------------------------------------------------------

function toolbarHTML(extra) {
  const langChecks = LANG_ORDER.map(
    (l) => `<label><input type="checkbox" data-lang="${l}" ${settings.langs.includes(l) ? "checked" : ""}/>${LANG_LABEL[l]}</label>`
  ).join("");
  const rubyChecks = ["zh", "ja", "ko"].map(
    (l) => `<label><input type="checkbox" data-ruby="${l}" ${settings.ruby[l] ? "checked" : ""}/>${LANG_LABEL[l]}拼音</label>`
  ).join("");
  const voiceSelects = LANG_ORDER.map((l) => {
    const saved = localStorage.getItem("mx_voice_" + l) || "";
    const list = voicesFor(l);
    const opts = list.length
      ? list.map((v) => `<option value="${esc(v.voiceURI)}" ${saved === v.voiceURI ? "selected" : ""}>${esc(v.name)}</option>`).join("")
      : `<option value="">（無可用語音）</option>`;
    const warn = list.length ? "" : " ⚠️";
    return `<label title="${TTS_LANG[l]} 發音聲音">${LANG_LABEL[l]}${warn}<select class="voicesel" data-voice="${l}"><option value="">自動</option>${opts}</select></label>`;
  }).join("");
  return `<div class="toolbar">
    <span class="grp">語言：${langChecks}</span>
    <span class="sep"></span>
    <span class="grp">拼音標注：${rubyChecks}</span>
    <span class="sep"></span>
    <label><input type="checkbox" id="maskChk" ${settings.mask ? "checked" : ""}/>遮罩回想</label>
    <span class="sep"></span>
    <span class="grp">發音聲音：${voiceSelects}</span>
    <span id="voiceWarn" class="warn"></span>
    ${extra || ""}
  </div>`;
}

function updateVoiceWarnings() {
  const el = document.getElementById("voiceWarn");
  if (!el) return;
  if (!voices.length) {
    el.textContent = "";
    return;
  }
  const missing = settings.langs.filter((l) => !voicesFor(l).length);
  el.textContent = missing.length ? `⚠️ 缺少語音：${missing.map((l) => LANG_LABEL[l]).join("、")}。${VOICE_HINT}` : "";
}

function repopulateVoiceSelects() {
  $app.querySelectorAll("select.voicesel").forEach((sel) => {
    const lang = sel.dataset.voice;
    const saved = localStorage.getItem("mx_voice_" + lang) || "";
    const list = voicesFor(lang);
    sel.innerHTML =
      `<option value="">自動</option>` +
      (list.length
        ? list.map((v) => `<option value="${esc(v.voiceURI)}" ${saved === v.voiceURI ? "selected" : ""}>${esc(v.name)}</option>`).join("")
        : `<option value="">（無可用語音）</option>`);
    sel.value = saved;
  });
  updateVoiceWarnings();
}

function bindToolbar(onChange) {
  $app.querySelectorAll(".toolbar input[data-lang]").forEach((c) => {
    c.addEventListener("change", () => {
      const l = c.dataset.lang;
      if (c.checked) {
        if (!settings.langs.includes(l)) settings.langs.push(l);
      } else {
        settings.langs = settings.langs.filter((x) => x !== l);
      }
      saveSettings();
      updateVoiceWarnings();
      onChange && onChange();
    });
  });
  $app.querySelectorAll(".toolbar input[data-ruby]").forEach((c) => {
    c.addEventListener("change", () => {
      settings.ruby[c.dataset.ruby] = c.checked;
      saveSettings();
      onChange && onChange();
    });
  });
  const m = document.getElementById("maskChk");
  if (m) {
    m.addEventListener("change", () => {
      settings.mask = m.checked;
      saveSettings();
      onChange && onChange();
    });
  }
  $app.querySelectorAll("select.voicesel").forEach((sel) => {
    sel.addEventListener("change", () => {
      if (sel.value) localStorage.setItem("mx_voice_" + sel.dataset.voice, sel.value);
      else localStorage.removeItem("mx_voice_" + sel.dataset.voice);
    });
  });
}

// ---- 首頁 ---------------------------------------------------------------

async function viewHome() {
  nav("home");
  $app.innerHTML = `<div class="spin">載入中…</div>`;
  const [topics, stats] = await Promise.all([
    api("/api/topics"),
    api("/api/stats?device=" + encodeURIComponent(device())),
  ]);
  const starMap = Object.fromEntries(stats.topics.map((t) => [t.slug, t.starred || 0]));
  const totalMap = Object.fromEntries(stats.topics.map((t) => [t.slug, t.total]));
  $app.innerHTML = `
    <h1>用小字集學會五種語言</h1>
    <p class="muted">每個主題都是中／英／法／日／韓五語平行的迷你對話。點開一本書，開始閱讀；句子可以朗讀、標星、遮罩回想。</p>
    <div class="cards">
      ${topics.topics
        .map((t) => {
          const total = totalMap[t.slug] || 0;
          const starred = starMap[t.slug] || 0;
          const pct = total ? Math.round((starred / total) * 100) : 0;
          return `<div class="card" data-slug="${esc(t.slug)}">
            <div class="t">${esc(t.title_zh)} <span class="s">${esc(t.title_en)}</span></div>
            <div class="s">${total} 句 · 已標星 ${starred}</div>
            <div class="bar"><i style="width:${pct}%"></i></div>
          </div>`;
        })
        .join("")}
    </div>`;
  $app.querySelectorAll(".card").forEach((c) => {
    c.addEventListener("click", () => (location.hash = "#/book/" + c.dataset.slug));
  });
}

// ---- 閱讀頁 ---------------------------------------------------------------

let starred = new Set();

async function viewBook(slug, params) {
  nav("home");
  $app.innerHTML = `<div class="spin">載入中…</div>`;
  const [data, prog] = await Promise.all([
    api("/api/lesson/" + encodeURIComponent(slug)),
    api("/api/progress?device=" + encodeURIComponent(device())),
  ]);
  starred = new Set(prog.progress.filter((p) => p.stars).map((p) => p.turnId));

  const draw = () => {
    const turnsHTML = data.turns
      .map((t) => {
        const lines = LANG_ORDER.filter((l) => settings.langs.includes(l))
          .map((l) => {
            const masked = settings.mask && l !== "zh";
            return `<div class="line ${masked ? "masked" : ""}" data-lang="${l}" data-text="${esc(t[l])}">
              <span class="tag">${LANG_LABEL[l]}</span><span class="body">${renderLine(l, t[l], t.ruby, settings.ruby[l])}</span>
            </div>`;
          })
          .join("");
        return `<div class="turn" id="turn-${t.id}" data-turn="${t.id}">
          <span class="who">${esc(t.speaker)}</span>
          <span class="ops"><button class="star ${starred.has(t.id) ? "starred" : ""}" title="標星">★</button></span>
          ${lines}
        </div>`;
      })
      .join("");
    $app.innerHTML = `
      <h1>${esc(data.topic.title_zh)} <span class="muted">${esc(data.topic.title_en)}</span></h1>
      ${toolbarHTML(`<span class="muted">${data.turns.length} 句</span>`)}
      <div id="turns">${turnsHTML}</div>
      <div class="searchrow">
        <button class="primary" id="prevTopic">上一課</button>
        <button class="primary" id="nextTopic">下一課</button>
      </div>`;
    bindTurns(data);
    bindToolbar(draw);
    bindTopicNav(data.topic.slug);
    jumpToTurn(params.get("turn"));
  };
  draw();
}

function bindTopicNav(slug) {
  const go = async (dir) => {
    const { topics } = await api("/api/topics");
    const i = topics.findIndex((t) => t.slug === slug);
    const next = topics[i + dir];
    if (next) location.hash = "#/book/" + next.slug;
  };
  const prev = document.getElementById("prevTopic");
  const next = document.getElementById("nextTopic");
  if (prev) prev.addEventListener("click", () => go(-1));
  if (next) next.addEventListener("click", () => go(1));
}

function bindTurns(data) {
  const byId = Object.fromEntries(data.turns.map((t) => [t.id, t]));
  $app.querySelectorAll(".line").forEach((line) => {
    line.addEventListener("click", (e) => {
      const lang = line.dataset.lang;
      const turnEl = line.closest(".turn");
      const t = byId[turnEl.dataset.turn];
      if (line.classList.contains("masked") && !line.classList.contains("revealed")) {
        line.classList.add("revealed");
        return;
      }
      speak(t[lang], lang);
    });
  });
  $app.querySelectorAll(".star").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const turnId = parseInt(btn.closest(".turn").dataset.turn, 10);
      const on = !starred.has(turnId);
      if (on) starred.add(turnId); else starred.delete(turnId);
      btn.classList.toggle("starred", on);
      await api("/api/progress", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ device: device(), turnId, stars: on }),
      });
    });
  });
  document.onkeydown = (e) => {
    if (e.target.tagName === "INPUT" || e.target.tagName === "SELECT") return;
    if (e.key === "ArrowDown" || e.key === "j") {
      const turns = [...$app.querySelectorAll(".turn")];
      const cur = turns.find((t) => t.getBoundingClientRect().top > 40);
      if (cur && cur.scrollIntoView) cur.scrollIntoView({ behavior: "smooth", block: "start" });
    }
    if (e.key === "ArrowUp" || e.key === "k") {
      const turns = [...$app.querySelectorAll(".turn")].reverse();
      const cur = turns.find((t) => t.getBoundingClientRect().top < 0);
      if (cur && cur.scrollIntoView) cur.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  };
}

function jumpToTurn(turnId) {
  if (!turnId) return;
  const el = document.getElementById("turn-" + turnId);
  if (el) {
    if (el.scrollIntoView) el.scrollIntoView({ block: "center" });
    el.classList.add("flash");
    setTimeout(() => el.classList.remove("flash"), 1800);
  }
}

// ---- 搜尋頁 ---------------------------------------------------------------

async function viewSearch(params) {
  nav("search");
  const q = params.get("q") || "";
  const lang = params.get("lang") || "all";
  const topic = params.get("topic") || "all";
  const { topics } = await api("/api/topics");

  const langChecks = LANG_ORDER.map(
    (l) => `<label><input type="checkbox" data-lang="${l}" ${settings.langs.includes(l) ? "checked" : ""}/>${LANG_LABEL[l]}</label>`
  ).join("");
  const rubyChecks = ["zh", "ja", "ko"].map(
    (l) => `<label><input type="checkbox" data-ruby="${l}" ${settings.ruby[l] ? "checked" : ""}/>${LANG_LABEL[l]}拼音</label>`
  ).join("");

  $app.innerHTML = `
    <h1>全文檢索</h1>
    <form class="searchrow" id="sform">
      <input type="text" name="q" placeholder="搜尋任一語言的句子，例如：生日 / birthday / うみ / 바다" value="${esc(q)}"/>
      <select name="lang">
        <option value="all">全部語言</option>
        ${LANG_ORDER.map((l) => `<option value="${l}" ${lang === l ? "selected" : ""}>${LANG_LABEL[l]}</option>`).join("")}
      </select>
      <select name="topic">
        <option value="all">全部主題</option>
        ${topics.map((t) => `<option value="${esc(t.slug)}" ${topic === t.slug ? "selected" : ""}>${esc(t.title_zh)}</option>`).join("")}
      </select>
      <button class="primary">搜尋</button>
    </form>
    <div class="toolbar">
      <span class="grp">顯示語言：${langChecks}</span>
      <span class="sep"></span>
      <span class="grp">拼音標注：${rubyChecks}</span>
      <span class="muted">（點任一句可發音）</span>
    </div>
    <div id="results"><div class="empty">輸入關鍵字開始搜尋</div></div>`;

  let last = null;
  function drawResults() {
    const box = document.getElementById("results");
    if (!last) return;
    if (!last.length) {
      box.innerHTML = `<div class="empty">沒有找到「${esc(q)}」</div>`;
      return;
    }
    box.innerHTML = last
      .map((r) => {
        // 命中的語言一定顯示，其餘依使用者勾選
        const langs = [...new Set([r.lang, ...settings.langs])];
        const lines = langs
          .map((l) => {
            const isHit = l === r.lang;
            const withRuby = !!settings.ruby[l];
            const body = isHit && !withRuby ? highlight(r[l] || "", q) : renderLine(l, r[l] || "", r.ruby, withRuby);
            return `<div class="line sline ${isHit ? "hitline" : ""}" data-lang="${l}" data-text="${esc(r[l] || "")}">
              <span class="tag">${LANG_LABEL[l]}</span><span class="body">${body}</span>
            </div>`;
          })
          .join("");
        return `<div class="result" data-slug="${esc(r.slug)}" data-turn="${r.turnId}">
          <div class="meta"><b>${LANG_LABEL[r.lang]}</b> · ${esc(r.title_zh)} · 第 ${r.idx} 句 · ${esc(r.speaker)}
            <a class="open" href="#/book/${esc(r.slug)}?turn=${r.turnId}">前往該課 ↗</a></div>
          ${lines}
        </div>`;
      })
      .join("");
    box.querySelectorAll(".line.sline").forEach((line) => {
      line.addEventListener("click", (e) => {
        if (e.target.closest("a")) return;
        speak(line.dataset.text, line.dataset.lang);
      });
    });
  }

  bindToolbar(drawResults);

  const form = document.getElementById("sform");
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const fd = new FormData(form);
    const p = new URLSearchParams();
    p.set("q", fd.get("q"));
    p.set("lang", fd.get("lang"));
    p.set("topic", fd.get("topic"));
    location.hash = "#/search?" + p.toString();
  });

  if (q) {
    const box = document.getElementById("results");
    box.innerHTML = `<div class="spin">搜尋中…</div>`;
    const data = await api(`/api/search?q=${encodeURIComponent(q)}&lang=${encodeURIComponent(lang)}&topic=${encodeURIComponent(topic)}`);
    last = data.results;
    drawResults();
  }
}

function highlight(text, q) {
  const i = text.indexOf(q);
  if (i < 0) return esc(text);
  return esc(text.slice(0, i)) + "<mark>" + esc(q) + "</mark>" + esc(text.slice(i + q.length));
}

// ---- 詞表頁 ---------------------------------------------------------------

async function viewVocab(params) {
  nav("vocab");
  const lang = params.get("lang") || "zh";
  const q = params.get("q") || "";
  $app.innerHTML = `
    <h1>小詞彙集</h1>
    <p class="muted">每種語言只使用一個很小的字集／詞集。點任一詞可以直接搜尋含該詞的句子。</p>
    <div class="tabs">
      ${LANG_ORDER.map((l) => `<button data-l="${l}" class="${lang === l ? "active" : ""}">${LANG_LABEL[l]}</button>`).join("")}
    </div>
    <form class="searchrow" id="vform">
      <input type="text" name="q" placeholder="篩選詞或讀音…" value="${esc(q)}"/>
      <button class="primary">篩選</button>
    </form>
    <div id="vlist"><div class="spin">載入中…</div></div>`;

  $app.querySelectorAll(".tabs button").forEach((b) => {
    b.addEventListener("click", () => {
      location.hash = `#/vocab?lang=${b.dataset.l}&q=${encodeURIComponent(q)}`;
    });
  });
  document.getElementById("vform").addEventListener("submit", (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    location.hash = `#/vocab?lang=${lang}&q=${encodeURIComponent(fd.get("q") || "")}`;
  });

  const data = await api(`/api/vocab?lang=${encodeURIComponent(lang)}&q=${encodeURIComponent(q)}`);
  const rows = data.results
    .map((v) => `<tr data-term="${esc(v.term)}" data-lang="${v.lang}"><td>${esc(v.term)}</td><td>${esc(v.reading)}</td></tr>`)
    .join("");
  document.getElementById("vlist").innerHTML = `
    <table class="vt"><thead><tr><th>詞</th><th>${lang === "zh" ? "拼音" : lang === "ja" || lang === "ko" ? "羅馬拼音" : "—"}</th></tr></thead>
    <tbody>${rows || `<tr><td colspan="2" class="empty">沒有資料</td></tr>`}</tbody></table>`;
  document.querySelectorAll("#vlist tr[data-term]").forEach((tr) => {
    tr.addEventListener("click", () => {
      location.hash = `#/search?q=${encodeURIComponent(tr.dataset.term)}&lang=${tr.dataset.lang}&topic=all`;
    });
  });
}

// ---- 測驗頁 ---------------------------------------------------------------

async function viewQuiz(params) {
  nav("quiz");
  const from = params.get("from") || "zh";
  const to = params.get("to") || "en";
  const topic = params.get("topic") || "all";
  const { topics } = await api("/api/topics");
  const sel = (name, cur, opts) =>
    `<select name="${name}">${opts.map((l) => `<option value="${l[0]}" ${cur === l[0] ? "selected" : ""}>${l[1]}</option>`).join("")}</select>`;
  $app.innerHTML = `
    <h1>句子測驗</h1>
    <form class="searchrow" id="qform">
      ${sel("from", from, LANG_ORDER.map((l) => [l, "從 " + LANG_LABEL[l]]))}
      ${sel("to", to, LANG_ORDER.map((l) => [l, "到 " + LANG_LABEL[l]]))}
      ${sel("topic", topic, [["all", "全部主題"], ...topics.map((t) => [t.slug, t.title_zh])])}
      <button class="primary">開始測驗</button>
    </form>
    <div id="qarea"></div>`;

  document.getElementById("qform").addEventListener("submit", (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const p = new URLSearchParams();
    p.set("from", fd.get("from")); p.set("to", fd.get("to")); p.set("topic", fd.get("topic"));
    location.hash = "#/quiz?" + p.toString();
  });

  if (from === to) {
    document.getElementById("qarea").innerHTML = `<div class="empty">從 和 到 不能是同一種語言</div>`;
    return;
  }
  const area = document.getElementById("qarea");
  area.innerHTML = `<div class="spin">出題中…</div>`;
  const data = await api(`/api/quiz?from=${from}&to=${to}&topic=${encodeURIComponent(topic)}&n=8`);
  if (!data.questions.length) {
    area.innerHTML = `<div class="empty">題目不足，換個組合試試</div>`;
    return;
  }
  let qi = 0, correctCount = 0;
  const renderQ = () => {
    const q = data.questions[qi];
    area.innerHTML = `
      <div class="muted">第 ${qi + 1} / ${data.questions.length} 題 · 從${LANG_LABEL[from]}選出對應的${LANG_LABEL[to]}</div>
      <div class="qcard">
        <div class="q">${renderLine(from, q.q, null, false)}</div>
        <div class="opts">${q.options.map((o, i) => `<button data-i="${i}">${renderLine(to, o, null, false)}</button>`).join("")}</div>
      </div>
      <button class="primary" id="nextQ" style="visibility:hidden">下一題</button>`;
    area.querySelectorAll(".opts button").forEach((b) => {
      b.addEventListener("click", async () => {
        const pick = parseInt(b.dataset.i, 10);
        const ok = pick === q.answer;
        area.querySelectorAll(".opts button").forEach((x, i) => {
          x.disabled = true;
          if (i === q.answer) x.classList.add("correct");
          else if (i === pick) x.classList.add("wrong");
        });
        if (ok) correctCount++;
        speak(q.options[q.answer], to);
        api("/api/quizlog", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ device: device(), turnId: q.turnId, correct: ok }),
        }).catch(() => {});
        document.getElementById("nextQ").style.visibility = "visible";
        document.getElementById("nextQ").textContent = qi + 1 < data.questions.length ? "下一題" : "看結果";
      });
    });
    document.getElementById("nextQ").addEventListener("click", () => {
      qi++;
      if (qi < data.questions.length) renderQ();
      else {
        area.innerHTML = `<div class="qcard"><div class="score">得分：${correctCount} / ${data.questions.length}</div>
          <p class="muted">成績已記錄，可在「進度」頁查看。</p>
          <button class="primary" onclick="location.reload()">再測一次</button></div>`;
      }
    });
  };
  renderQ();
}

// ---- 進度頁 ---------------------------------------------------------------

async function viewStats() {
  nav("stats");
  $app.innerHTML = `<div class="spin">載入中…</div>`;
  const stats = await api("/api/stats?device=" + encodeURIComponent(device()));
  const acc = stats.quiz.total ? Math.round((stats.quiz.correct / stats.quiz.total) * 100) : null;
  $app.innerHTML = `
    <h1>學習進度</h1>
    <p class="muted">標星句子代表「已經會了」。測驗成績也會累積在這裡。</p>
    ${stats.topics
      .map((t) => {
        const pct = t.total ? Math.round(((t.starred || 0) / t.total) * 100) : 0;
        return `<div class="statrow">
          <span class="name">${esc(t.title_zh)} <span class="muted">${esc(t.title_en)}</span></span>
          <div class="bar"><i style="width:${pct}%"></i></div>
          <span class="nums">${t.starred || 0}/${t.total}</span>
        </div>`;
      })
      .join("")}
    <h2>測驗</h2>
    <p class="muted">${stats.quiz.total ? `累積答題 ${stats.quiz.total} 次，正確率 ${acc}%。` : "還沒有測驗紀錄。"}</p>`;
}

// ---- 主題切換 -----------------------------------------------------------

document.getElementById("themeBtn").addEventListener("click", () => {
  const cur = document.documentElement.dataset.theme === "dark" ? "" : "dark";
  document.documentElement.dataset.theme = cur;
  localStorage.setItem("mx_theme", cur);
});
if (localStorage.getItem("mx_theme")) {
  document.documentElement.dataset.theme = localStorage.getItem("mx_theme");
}

route();
