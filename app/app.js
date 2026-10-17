/* HL Paper Lab — vanilla JS, no framework. Data is embedded by build_app.py. */
"use strict";

const DATA = JSON.parse(document.getElementById("db").textContent);
const DB = DATA.db;
const META = DATA.meta;
const BY_ID = new Map(DB.map(r => [r.id, r]));
const CODE_ORDER = new Map(META.order.map((c, i) => [c, i]));
const SESSION_RANK = { May: 0, November: 1 };

let IMGS = null;
function imgSrc(name) {
  if (IMAGE_MODE === "inline") {
    if (!IMGS) IMGS = JSON.parse(document.getElementById("imgs").textContent);
    return IMGS[name];
  }
  return "img/" + name.replace(/\.webp$/, ".png");
}

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = s => String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmt = n => n.toLocaleString("en-GB");
const store = {
  get(k, d) { try { const v = localStorage.getItem("hlpl." + k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } },
  set(k, v) { try { localStorage.setItem("hlpl." + k, JSON.stringify(v)); } catch (e) { /* storage unavailable */ } },
};
const topicVar = t => `var(--t${t})`;
const sessionKey = r => `${r.session} ${r.year}`;
const fold = s => s.normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase();
for (const r of DB) r._hay = fold([r.desc, r.sub, r.code, r.label, r.id, r.topicName].join(" ")) + " " + [r.desc, r.sub].join(" ").toLowerCase();

const newest = (a, b) => (b.year - a.year) || (SESSION_RANK[b.session] - SESSION_RANK[a.session]) ||
  (a.paper - b.paper) || ((a.tz || 0) - (b.tz || 0)) || (a.q - b.q);

/* ======================= header ======================= */
$("#stats").textContent = `${fmt(DB.length)} questions · ${fmt(DB.reduce((s, r) => s + r.marks, 0))} marks · ${META.papers} papers`;

$("#themeBtn").addEventListener("click", () => {
  const root = document.documentElement;
  const current = root.dataset.theme || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  const next = current === "dark" ? "light" : "dark";
  root.dataset.theme = next;
  try { localStorage.setItem("hlpl.theme", next); } catch (e) {}
});

const tabs = { bank: $("#tab-bank"), exam: $("#tab-exam") };
function showTab(name) {
  for (const [k, btn] of Object.entries(tabs)) {
    const on = k === name;
    btn.setAttribute("aria-selected", on);
    btn.tabIndex = on ? 0 : -1;
    $("#" + k).hidden = !on;
  }
  if (name === "exam") renderExam();
  store.set("tab", name);
}
tabs.bank.addEventListener("click", () => showTab("bank"));
tabs.exam.addEventListener("click", () => showTab("exam"));
$(".tabs").addEventListener("keydown", e => {
  if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
    const next = tabs.bank.getAttribute("aria-selected") === "true" ? "exam" : "bank";
    showTab(next); tabs[next].focus();
  }
});
$("#railToggle").addEventListener("click", () => {
  const rail = $("#bank").hidden ? $("#examRail") : $("#bankRail");
  const open = rail.classList.toggle("open");
  $("#railToggle").setAttribute("aria-expanded", open);
});

/* ======================= filters ======================= */
const FACETS = {
  topics:   { values: Object.keys(META.topics).map(Number), get: r => r.topic, emptyMeansAll: true },
  subs:     { values: META.order.filter(c => DB.some(r => r.code === c)), get: r => r.code, emptyMeansAll: true },
  section:  { values: ["A", "B"], get: r => r.section, labels: { A: "Short (A)", B: "Long (B)" } },
  calc:     { values: ["no", "yes"], get: r => (r.calc ? "yes" : "no"), labels: { no: "No calc", yes: "Calculator" } },
  syl:      { values: ["current", "legacy"], get: r => (r.current ? "current" : "legacy"), labels: { current: "Current", legacy: "Legacy" } },
  level:    { values: ["SL", "AHL", "LEGACY"], get: r => r.level, labels: { SL: "SL", AHL: "AHL", LEGACY: "Old-only" } },
  paper:    { values: [1, 2], get: r => r.paper, labels: { 1: "Paper 1", 2: "Paper 2" } },
  sessions: { values: [...new Set([...DB].sort(newest).map(sessionKey))], get: sessionKey, emptyMeansAll: true },
};
const MARK_MIN = Math.min(...DB.map(r => r.marks)), MARK_MAX = Math.max(...DB.map(r => r.marks));

function defaultFilters() {
  const f = { q: "", mmin: MARK_MIN, mmax: MARK_MAX, officialOnly: false };
  for (const [k, def] of Object.entries(FACETS)) f[k] = new Set(def.emptyMeansAll ? [] : def.values);
  return f;
}
let F = defaultFilters();
let sortMode = store.get("sort", "newest");
let shuffleOrder = null;

function passes(r, except) {
  for (const [k, def] of Object.entries(FACETS)) {
    if (k === except) continue;
    const set = F[k];
    if (def.emptyMeansAll && set.size === 0) continue;
    if (!set.has(def.get(r))) return false;
  }
  if (except !== "marks" && (r.marks < F.mmin || r.marks > F.mmax)) return false;
  if (except !== "official" && F.officialOnly && r.msAuthored) return false;
  if (F.q) {
    for (const tok of F.qTokens) if (!r._hay.includes(tok)) return false;
  }
  return true;
}

function facetCounts(key) {
  const c = new Map();
  const get = FACETS[key].get;
  for (const r of DB) if (passes(r, key)) c.set(get(r), (c.get(get(r)) || 0) + 1);
  return c;
}

function buildFacetUI() {
  // topics
  $("#f-topics").innerHTML = FACETS.topics.values.map(t => `
    <label class="opt" data-v="${t}"><input type="checkbox" data-facet="topics" value="${t}">
      <span class="dot" style="background:${topicVar(t)}"></span>
      <span class="lbl">${t}&nbsp; ${esc(META.topics[t])}</span><span class="count num"></span></label>`).join("");
  // segmented multi-selects
  for (const k of ["section", "calc", "syl", "level", "paper"]) {
    const def = FACETS[k];
    $("#f-" + k).innerHTML = def.values.map(v => `
      <label title="${esc(def.labels[v])}"><input type="checkbox" data-facet="${k}" value="${v}" checked>${esc(def.labels[v])} <span class="count num"></span></label>`).join("");
  }
  // sessions
  $("#f-sessions").innerHTML = FACETS.sessions.values.map(s => `
    <label class="opt" data-v="${esc(s)}"><input type="checkbox" data-facet="sessions" value="${esc(s)}">
      <span class="lbl">${esc(s)}</span><span class="count num"></span></label>`).join("");
  $("#mmin").value = F.mmin; $("#mmax").value = F.mmax;
  $("#mmin").min = $("#mmax").min = MARK_MIN; $("#mmin").max = $("#mmax").max = MARK_MAX;
  const nAuth = DB.filter(r => r.msAuthored).length;
  $("#officialHint").textContent = `Hides the ${nAuth} questions whose mark scheme was worked for this compilation (shown amber).`;
}

function renderSubs() {
  // sub-topics shown for the selected topics (all topics when none selected)
  const counts = facetCounts("subs");
  const topics = F.topics.size ? [...F.topics].sort() : FACETS.topics.values;
  let html = "";
  for (const t of topics) {
    const codes = FACETS.subs.values.filter(c => DB.find(r => r.code === c).topic === t);
    html += `<div class="group-h"><span class="dot" style="background:${topicVar(t)}"></span>${esc(META.topics[t])}</div>`;
    html += codes.map(c => {
      const n = counts.get(c) || 0;
      return `<label class="opt${n ? "" : " zero"}"><input type="checkbox" data-facet="subs" value="${esc(c)}"${F.subs.has(c) ? " checked" : ""}>
        <span class="code num">${esc(c.replace("LEGACY", "OLD"))}</span><span class="lbl">${esc(META.syllabus[c])}</span><span class="count num">${n}</span></label>`;
    }).join("");
  }
  const box = $("#f-subs"), top = box.scrollTop;
  box.innerHTML = html;
  box.scrollTop = top;
}

function syncFacetUI() {
  for (const k of ["topics", "sessions", "section", "calc", "syl", "level", "paper"]) {
    const counts = facetCounts(k);
    for (const inp of $$(`input[data-facet="${k}"]`)) {
      const v = typeof FACETS[k].values[0] === "number" ? Number(inp.value) : inp.value;
      inp.checked = F[k].has(v);
      const n = counts.get(v) || 0;
      const lab = inp.closest("label");
      lab.querySelector(".count").textContent = FACETS[k].emptyMeansAll ? n : `${n}`;
      lab.classList.toggle("zero", n === 0);
    }
  }
  renderSubs();
  $("#officialOnly").checked = F.officialOnly;
  $("#q").value = F.q;
}

document.addEventListener("change", e => {
  const inp = e.target;
  if (!inp.dataset || !inp.dataset.facet) return;
  const k = inp.dataset.facet;
  const v = typeof FACETS[k].values[0] === "number" ? Number(inp.value) : inp.value;
  inp.checked ? F[k].add(v) : F[k].delete(v);
  if (k === "topics") {                         // drop sub-topic picks outside the chosen topics
    for (const c of [...F.subs]) if (F.topics.size && !F.topics.has(BY_CODE_TOPIC.get(c))) F.subs.delete(c);
  }
  update();
});
const BY_CODE_TOPIC = new Map(DB.map(r => [r.code, r.topic]));
for (const btn of $$("[data-clear]")) btn.addEventListener("click", () => { F[btn.dataset.clear].clear(); update(); });
for (const id of ["mmin", "mmax"]) $("#" + id).addEventListener("input", () => {
  const a = Number($("#mmin").value) || MARK_MIN, b = Number($("#mmax").value) || MARK_MAX;
  F.mmin = Math.min(a, b); F.mmax = Math.max(a, b);
  update(false);
});
$("#officialOnly").addEventListener("change", e => { F.officialOnly = e.target.checked; update(); });
$("#resetFilters").addEventListener("click", () => {
  F = defaultFilters(); $("#mmin").value = F.mmin; $("#mmax").value = F.mmax; update();
});
let qTimer;
$("#q").addEventListener("input", e => {
  clearTimeout(qTimer);
  qTimer = setTimeout(() => { setQuery(e.target.value); update(false); }, 90);
});
function setQuery(s) {
  F.q = s.trim();
  F.qTokens = fold(F.q).split(/\s+/).filter(Boolean);
}
$("#sort").value = sortMode;
$("#sort").addEventListener("change", e => {
  sortMode = e.target.value; store.set("sort", sortMode);
  if (sortMode === "shuffle") shuffleOrder = null;
  renderList();
});

/* ======================= list ======================= */
let VISIBLE = [];

function sorted(rows) {
  const r = [...rows];
  switch (sortMode) {
    case "oldest": return r.sort((a, b) => newest(b, a));
    case "syllabus": return r.sort((a, b) => (a.topic - b.topic) || (CODE_ORDER.get(a.code) - CODE_ORDER.get(b.code)) || newest(a, b));
    case "marksAsc": return r.sort((a, b) => (a.marks - b.marks) || newest(a, b));
    case "marksDesc": return r.sort((a, b) => (b.marks - a.marks) || newest(a, b));
    case "paper": return r.sort((a, b) => (a.paper - b.paper) || newest(a, b));
    case "shuffle": {
      if (!shuffleOrder) { shuffleOrder = new Map(shuffle(DB.map(x => x.id)).map((id, i) => [id, i])); }
      return r.sort((a, b) => shuffleOrder.get(a.id) - shuffleOrder.get(b.id));
    }
    default: return r.sort(newest);
  }
}

const ICON_PLUS = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>';
const ICON_CHECK = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="m5 12 5 5L20 7"/></svg>';

function renderList() {
  VISIBLE = sorted(DB.filter(r => passes(r)));
  const marks = VISIBLE.reduce((s, r) => s + r.marks, 0);
  $("#resultCount").innerHTML = `<b class="num">${fmt(VISIBLE.length)}</b> question${VISIBLE.length === 1 ? "" : "s"} · <b class="num">${fmt(marks)}</b> marks`;
  if (!VISIBLE.length) {
    $("#list").innerHTML = `<div class="empty">No questions match these filters. <button class="link-btn" onclick="document.getElementById('resetFilters').click()">Reset filters</button></div>`;
    return;
  }
  $("#list").innerHTML = VISIBLE.map((r, i) => {
    const inExam = EXAM.has(r.id);
    return `<div class="row" role="listitem" tabindex="0" data-i="${i}" data-id="${esc(r.id)}" style="--tc:${topicVar(r.topic)}">
      <span class="code-pill num">${esc(r.code.replace("LEGACY", "OLD"))}</span>
      <span class="desc"><span class="d">${esc(r.desc)}</span><span class="s">${esc(r.sub)}</span></span>
      <span class="src">${esc(r.label)} · Q${r.q}<span class="tags">${r.calc ? '<span class="tag">GDC</span>' : '<span class="tag">No GDC</span>'}${r.current ? "" : '<span class="tag">Legacy</span>'}${r.msAuthored ? '<span class="tag amber">Unofficial MS</span>' : ""}</span></span>
      <span class="marks num">${r.marks}</span>
      <button class="add-btn" data-add="${esc(r.id)}" aria-pressed="${inExam}" aria-label="${inExam ? "Remove from" : "Add to"} mock exam" title="${inExam ? "In mock exam — click to remove" : "Add to mock exam"}">${inExam ? ICON_CHECK : ICON_PLUS}</button>
    </div>`;
  }).join("");
}

$("#list").addEventListener("click", e => {
  const add = e.target.closest("[data-add]");
  if (add) { e.stopPropagation(); toggleExam(add.dataset.add); return; }
  const row = e.target.closest(".row");
  if (row) openReader(Number(row.dataset.i), row);
});
$("#list").addEventListener("keydown", e => {
  const row = e.target.closest(".row");
  if (!row || e.target !== row) return;
  if (e.key === "Enter" || e.key === " ") { e.preventDefault(); openReader(Number(row.dataset.i), row); }
  if (e.key === "ArrowDown") { e.preventDefault(); row.nextElementSibling && row.nextElementSibling.focus(); }
  if (e.key === "ArrowUp") { e.preventDefault(); row.previousElementSibling && row.previousElementSibling.focus(); }
  if (e.key === "a") toggleExam(row.dataset.id);
});

function update(rebuildCounts = true) {
  syncFacetUI();
  shuffleOrder = sortMode === "shuffle" ? shuffleOrder : null;
  renderList();
}

/* ======================= reader ======================= */
let RD = { list: [], i: 0, ret: null, ms: false };

function openReader(i, returnFocus, list = VISIBLE) {
  RD = { list, i, ret: returnFocus || document.activeElement, ms: false };
  $("#reader").hidden = false;
  document.body.style.overflow = "hidden";
  renderReader();
  $("#rdClose").focus();
}
function closeReader() {
  $("#reader").hidden = true;
  document.body.style.overflow = "";
  const id = RD.list[RD.i] && RD.list[RD.i].id;
  const row = id && $(`.row[data-id="${CSS.escape(id)}"]`);
  (row || RD.ret || document.body).focus && (row || RD.ret).focus();
}
function renderReader() {
  const r = RD.list[RD.i];
  $("#rdTitle").textContent = `${r.label} — Question ${r.q}`;
  $("#rdMeta").innerHTML = `<span style="color:${topicVar(r.topic)};font-weight:600">${esc(r.code)}</span> ${esc(r.sub)} · <span class="num">${r.marks}</span> marks · ${r.calc ? "calculator" : "no calculator"} · Section ${r.section}`;
  $("#rdPos").textContent = `${RD.i + 1} / ${RD.list.length}`;
  $("#rdPrev").disabled = RD.i === 0;
  $("#rdNext").disabled = RD.i === RD.list.length - 1;
  const inExam = EXAM.has(r.id);
  $("#rdAdd").innerHTML = inExam ? `${ICON_CHECK} In exam` : `${ICON_PLUS} Add to exam`;
  $("#rdAdd").setAttribute("aria-pressed", inExam);
  const au = r.msAuthored;
  $("#rdBody").innerHTML = `
    <p class="desc-line">${esc(r.desc)}</p>
    <div class="sheet-card">${r.qi.map(f => `<img src="${imgSrc(f)}" alt="Question ${r.q}, ${esc(r.label)}">`).join("")}</div>
    <button class="btn ms-toggle ${au ? "amber" : "primary"}" id="msBtn" aria-expanded="${RD.ms}" aria-controls="msArea">
      ${RD.ms ? (au ? "Hide worked solution" : "Hide mark scheme") : (au ? "Show worked solution" : "Show mark scheme")}</button>
    <div id="msArea" ${RD.ms ? "" : "hidden"}>
      ${au ? `<div class="ms-head amber" role="note">Unofficial worked solution — written for this compilation and verified with sympy, but not an IB document. The IB mark scheme for ${esc(r.label)} was not available.</div>`
           : `<div class="ms-head">Mark scheme</div>`}
      <div class="sheet-card ms-card${au ? " amber" : ""}">${RD.ms ? r.mi.map(f => `<img src="${imgSrc(f)}" alt="Mark scheme for question ${r.q}">`).join("") : ""}</div>
    </div>
    <p class="kbd-hint"><kbd>←</kbd> <kbd>→</kbd> previous / next · <kbd>M</kbd> mark scheme · <kbd>A</kbd> add to exam · <kbd>Esc</kbd> close</p>`;
  $("#rdBody").scrollTop = 0;
  $("#msBtn").addEventListener("click", toggleMs);
}
function toggleMs() {
  RD.ms = !RD.ms;
  const top = $("#rdBody").scrollTop;
  renderReader();
  $("#rdBody").scrollTop = top;
  $("#msBtn").focus();
  if (RD.ms) $("#msArea").scrollIntoView({ behavior: "smooth", block: "start" });
}
function stepReader(d) {
  const j = RD.i + d;
  if (j < 0 || j >= RD.list.length) return;
  RD.i = j; RD.ms = false; renderReader();
}
$("#rdPrev").addEventListener("click", () => stepReader(-1));
$("#rdNext").addEventListener("click", () => stepReader(1));
$("#rdClose").addEventListener("click", closeReader);
$("#rdAdd").addEventListener("click", () => { toggleExam(RD.list[RD.i].id); renderReader(); });
$("#reader").addEventListener("click", e => { if (e.target.id === "reader") closeReader(); });
document.addEventListener("keydown", e => {
  if (!$("#reader").hidden) {
    if (e.key === "Escape") { e.preventDefault(); closeReader(); return; }
    if (e.target.matches("input, select, textarea")) return;
    if (e.key === "ArrowRight") { e.preventDefault(); stepReader(1); }
    else if (e.key === "ArrowLeft") { e.preventDefault(); stepReader(-1); }
    else if (e.key === "m" || e.key === "M") toggleMs();
    else if (e.key === "a" || e.key === "A") { toggleExam(RD.list[RD.i].id); renderReader(); }
    else if (e.key === "Tab") {                       // keep focus inside the dialog
      const f = $$("#reader button:not([disabled]), #reader [href], #reader [tabindex]:not([tabindex='-1'])");
      if (!f.length) return;
      const first = f[0], last = f[f.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    }
    return;
  }
  if (e.key === "/" && !e.target.matches("input, select, textarea")) {
    e.preventDefault(); showTab("bank"); $("#q").focus();
  }
});

/* ======================= mock exam ======================= */
const EXAM = new Map();                         // id -> true, insertion order kept
for (const id of store.get("exam", [])) if (BY_ID.has(id)) EXAM.set(id, true);
let EX = Object.assign({ topics: [1, 2, 3, 4, 5], target: 110, style: "any", current: true, official: false },
                       store.get("examSettings", {}));
let lastTarget = store.get("lastTarget", null);

function saveExam() {
  store.set("exam", [...EXAM.keys()]);
  const n = EXAM.size;
  $("#examBadge").hidden = n === 0;
  $("#examBadge").textContent = n;
}
function toggleExam(id) {
  EXAM.has(id) ? EXAM.delete(id) : EXAM.set(id, true);
  saveExam();
  const btn = $(`[data-add="${CSS.escape(id)}"]`);
  if (btn) {
    const on = EXAM.has(id);
    btn.setAttribute("aria-pressed", on);
    btn.innerHTML = on ? ICON_CHECK : ICON_PLUS;
    btn.title = on ? "In mock exam — click to remove" : "Add to mock exam";
    btn.setAttribute("aria-label", (on ? "Remove from" : "Add to") + " mock exam");
  }
  if (!$("#exam").hidden) renderExam();
}

function buildExamUI() {
  $("#ex-topics").innerHTML = Object.entries(META.topics).map(([t, name]) => {
    const n = DB.filter(r => r.topic === Number(t)).length;
    return `<label class="opt"><input type="checkbox" class="ex-topic" value="${t}"${EX.topics.includes(Number(t)) ? " checked" : ""}>
      <span class="dot" style="background:${topicVar(t)}"></span><span class="lbl">${esc(name)}</span><span class="count num">${n}</span></label>`;
  }).join("");
  setTarget(EX.target);
  $(`input[name="exstyle"][value="${EX.style}"]`).checked = true;
  $("#exCurrent").checked = EX.current;
  $("#exOfficial").checked = EX.official;
}
function saveSettings() { store.set("examSettings", EX); }
function setTarget(v) {
  v = Math.max(10, Math.min(330, Math.round(Number(v) || 110)));
  EX.target = v;
  $("#exTarget").value = v; $("#exTargetRange").value = v;
  for (const b of $$("#exPresets button")) b.setAttribute("aria-pressed", Number(b.dataset.v) === v);
  saveSettings();
  renderExamSummary();
}
$("#exTargetRange").addEventListener("input", e => setTarget(e.target.value));
$("#exTarget").addEventListener("change", e => setTarget(e.target.value));
for (const b of $$("#exPresets button")) b.addEventListener("click", () => setTarget(b.dataset.v));
document.addEventListener("change", e => {
  if (e.target.classList.contains("ex-topic")) {
    EX.topics = $$(".ex-topic:checked").map(x => Number(x.value)); saveSettings();
  } else if (e.target.name === "exstyle") { EX.style = e.target.value; saveSettings(); }
  else if (e.target.id === "exCurrent") { EX.current = e.target.checked; saveSettings(); }
  else if (e.target.id === "exOfficial") { EX.official = e.target.checked; saveSettings(); }
});
$("#exAllTopics").addEventListener("click", () => { for (const x of $$(".ex-topic")) x.checked = true; EX.topics = [1, 2, 3, 4, 5]; saveSettings(); });

function shuffle(a) {
  for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; }
  return a;
}
function interleaveByTopic(rows) {
  // shuffle each topic, then deal round-robin so a DP that prefers early items stays balanced
  const groups = new Map();
  for (const r of shuffle([...rows])) { if (!groups.has(r.topic)) groups.set(r.topic, []); groups.get(r.topic).push(r); }
  const lists = shuffle([...groups.values()]), out = [];
  for (let i = 0; lists.some(l => i < l.length); i++) for (const l of lists) if (i < l.length) out.push(l[i]);
  return out;
}
function subsetClosest(items, goal) {
  // 0/1 subset-sum over marks: reachable totals, keep the first item that reached each total
  const from = new Int32Array(goal + 26).fill(-1), prev = new Int32Array(goal + 26).fill(-1);
  const reach = new Uint8Array(goal + 26); reach[0] = 1;
  const cap = goal + 25;
  items.forEach((r, idx) => {
    for (let s = cap; s >= r.marks; s--) {
      if (!reach[s] && reach[s - r.marks]) { reach[s] = 1; from[s] = idx; prev[s] = s - r.marks; }
    }
  });
  let best = 0;
  for (let s = 0; s <= cap; s++) if (reach[s] && Math.abs(s - goal) < Math.abs(best - goal)) best = s;
  const pick = [];
  for (let s = best; s > 0; s = prev[s]) pick.push(items[from[s]]);
  return pick;
}
function generatePaper() {
  const T = EX.target;
  const pool = DB.filter(r => EX.topics.includes(r.topic) &&
    (EX.style === "any" || (EX.style === "p1" ? !r.calc : r.calc)) &&
    (!EX.current || r.current) && (!EX.official || !r.msAuthored));
  if (!EX.topics.length) { $("#genHint").textContent = "Choose at least one topic."; return; }
  if (!pool.length) { $("#genHint").textContent = "No questions match these settings."; return; }
  const poolMarks = pool.reduce((s, r) => s + r.marks, 0);
  let best = null;
  for (let attempt = 0; attempt < 80; attempt++) {
    const A = interleaveByTopic(pool.filter(r => r.section === "A"));
    const B = interleaveByTopic(pool.filter(r => r.section === "B"));
    // like a real HL paper, roughly half the marks are extended response (none for short targets)
    const bGoal = T >= 45 ? Math.round(T * (0.42 + Math.random() * 0.14)) : 0;
    const picked = [];
    let sumB = 0;
    for (const r of B) if (sumB + r.marks <= bGoal) { picked.push(r); sumB += r.marks; }
    let rest = subsetClosest(A, T - sumB);
    let chosen = picked.concat(rest);
    let total = chosen.reduce((s, r) => s + r.marks, 0);
    if (total !== T) {                                  // fall back to the whole pool for the remainder
      const used = new Set(picked.map(r => r.id));
      rest = subsetClosest(interleaveByTopic(pool.filter(r => !used.has(r.id))), T - sumB);
      const alt = picked.concat(rest), altTotal = alt.reduce((s, r) => s + r.marks, 0);
      if (Math.abs(altTotal - T) < Math.abs(total - T)) { chosen = alt; total = altTotal; }
    }
    const topicsCovered = new Set(chosen.map(r => r.topic)).size;
    const score = Math.abs(total - T) * 100 - topicsCovered;
    if (!best || score < best.score) best = { chosen, total, score };
    if (total === T && topicsCovered >= Math.min(EX.topics.length, chosen.length) && attempt > 4) break;
  }
  EXAM.clear();
  for (const r of best.chosen) EXAM.set(r.id, true);
  lastTarget = T; store.set("lastTarget", T);
  saveExam();
  $("#genHint").textContent = poolMarks < T
    ? `Only ${poolMarks} marks of questions match these settings.`
    : `Picked ${best.chosen.length} questions from ${pool.length} matching.`;
  renderExam();
  if (VISIBLE.length) renderList();
}
$("#generate").addEventListener("click", generatePaper);
$("#exClear").addEventListener("click", () => { EXAM.clear(); saveExam(); renderExam(); renderList(); });

function examOrder() {
  // real-paper arrangement: short Section A questions ascending by marks, then Section B
  const rows = [...EXAM.keys()].map(id => BY_ID.get(id));
  const by = (a, b) => (a.marks - b.marks) || newest(a, b);
  return { A: rows.filter(r => r.section === "A").sort(by), B: rows.filter(r => r.section === "B").sort(by) };
}
function timeText(mins) {
  const h = Math.floor(mins / 60), m = mins % 60;
  return [h ? `${h} hour${h > 1 ? "s" : ""}` : "", m ? `${m} minute${m > 1 ? "s" : ""}` : ""].filter(Boolean).join(" ");
}
function renderExamSummary() {
  const { A, B } = examOrder();
  const total = [...A, ...B].reduce((s, r) => s + r.marks, 0);
  const target = lastTarget || EX.target;
  $("#exTotal").innerHTML = `${total} <small>marks · ${A.length + B.length} questions${total ? " · " + timeText(total) : ""}</small>`;
  const fit = $("#exFit");
  if (!total) { fit.hidden = true; return; }
  fit.hidden = false;
  const d = total - target;
  fit.className = "fit " + (d === 0 ? "ok" : "off");
  fit.textContent = d === 0 ? `on target (${target})` : `${Math.abs(d)} ${d > 0 ? "over" : "under"} target ${target}`;
}
function renderExam() {
  renderExamSummary();
  const { A, B } = examOrder();
  const all = [...A, ...B];
  const total = all.reduce((s, r) => s + r.marks, 0);
  $("#printPaper").disabled = $("#printPaperMs").disabled = $("#exClear").disabled = !all.length;
  if (!all.length) {
    $("#selList").innerHTML = `<div class="empty">No questions yet. Choose topics and a target, then <b>Generate paper</b> — or add questions from the bank with <b>+</b>.</div>`;
    $("#paperWrap").innerHTML = "";
    return;
  }
  let run = 0, n = 0;
  const rowHtml = r => {
    n++; run += r.marks;
    return `<div class="sel-row" style="--tc:${topicVar(r.topic)}">
      <span class="n num">${n}.</span>
      <span class="d" data-open="${esc(r.id)}" tabindex="0" role="button" title="${esc(r.sub)}"><span class="code-pill num" style="margin-right:8px">${esc(r.code.replace("LEGACY", "OLD"))}</span>${esc(r.desc)}</span>
      <span class="src">${esc(r.label)} · Q${r.q}${r.msAuthored ? ' <span class="tag amber">Unofficial MS</span>' : ""}</span>
      <span class="marks num" title="running total ${run}">${r.marks}</span>
      <button class="drop" data-drop="${esc(r.id)}" aria-label="Remove question ${n} from the exam" title="Remove">×</button>
    </div>`;
  };
  $("#selList").innerHTML =
    (A.length ? `<div class="sel-sec">Section A · short response · ${A.reduce((s, r) => s + r.marks, 0)} marks</div>` + A.map(rowHtml).join("") : "") +
    (B.length ? `<div class="sel-sec">Section B · extended response · ${B.reduce((s, r) => s + r.marks, 0)} marks</div>` + B.map(rowHtml).join("") : "");
  renderPaper(A, B, total);
}
$("#selList").addEventListener("click", e => {
  const drop = e.target.closest("[data-drop]");
  if (drop) { toggleExam(drop.dataset.drop); renderList(); return; }
  const open = e.target.closest("[data-open]");
  if (open) { const { A, B } = examOrder(); const list = [...A, ...B]; openReader(list.findIndex(r => r.id === open.dataset.open), open, list); }
});
$("#selList").addEventListener("keydown", e => {
  if ((e.key === "Enter" || e.key === " ") && e.target.dataset.open) { e.preventDefault(); e.target.click(); }
});

function renderPaper(A, B, total) {
  const all = [...A, ...B];
  const calcs = new Set(all.map(r => r.calc));
  const mixed = calcs.size > 1, anyCalc = calcs.has(true);
  const topics = [...new Set(all.map(r => r.topic))].sort().map(t => META.topics[t]);
  const today = new Date().toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" });
  const calcLine = mixed
    ? "A graphic display calculator is required for questions marked GDC. You are not permitted access to any calculator for the other questions."
    : anyCalc ? "A graphic display calculator is required for this paper."
              : "You are not permitted access to any calculator for this paper.";
  let n = 0;
  const q = r => {
    n++;
    return `<article class="pq">
      <div class="pq-num">${n}.</div>
      <div class="pq-body">${r.qi.map(f => `<div class="clip"><img src="${imgSrc(f)}" alt="Question ${n}"></div>`).join("")}</div>
      <div class="pq-src">${esc(r.label)} · Q${r.q}${mixed && r.calc ? '<span class="gdc">GDC</span>' : ""}</div>
    </article>`;
  };
  const secA = A.length ? `<section class="sheet sec-a">
      <h3 class="sec-title">Section A</h3>
      <p class="sec-instr">Answer all questions. Answers must be supported by working and/or explanations.</p>
      ${A.map(q).join("")}</section>` : "";
  const secB = B.length ? `<section class="sheet sec-b">
      <h3 class="sec-title">Section B</h3>
      <p class="sec-instr">Answer all questions. Please start each question on a new page.</p>
      ${B.map(q).join("")}</section>` : "";
  n = 0;
  const ms = all.map(r => {
    n++;
    return `<div class="msq${r.msAuthored ? " amber" : ""}">
      <h5>Question ${n} <span>— ${esc(r.label)} · Q${r.q} · ${r.marks} marks</span>${r.msAuthored ? '<span class="unof">UNOFFICIAL — worked for this compilation, not an IB document</span>' : ""}</h5>
      ${r.mi.map(f => `<img src="${imgSrc(f)}" alt="Mark scheme for question ${n}">`).join("")}</div>`;
  }).join("");
  $("#paperWrap").innerHTML = `
    <div class="paper-label">Paper preview</div>
    <section class="sheet cover">
      <div class="kicker">Mock examination · compiled from IB past papers</div>
      <h2>Mathematics: analysis and approaches</h2>
      <p class="lvl">Higher level</p>
      <p class="paper-name">Mock paper — ${esc(today)}</p>
      <div class="rule"></div>
      <dl class="facts">
        <div><dt>Maximum mark</dt><dd>${total} marks</dd></div>
        <div><dt>Suggested time</dt><dd>${timeText(total)}</dd></div>
        <div><dt>Questions</dt><dd>${all.length}</dd></div>
      </dl>
      <p class="topics"><b>Topics:</b> ${topics.map(esc).join(", ")}</p>
      <div class="instructions">
        <h4>Instructions to candidates</h4>
        <ul>
          <li>Do not open this examination paper until instructed to do so.</li>
          <li>${calcLine}</li>
          ${A.length ? "<li>Section A: answer all questions. Answers must be written within the answer boxes provided.</li>" : ""}
          ${B.length ? "<li>Section B: answer all questions in the answer booklet provided.</li>" : ""}
          <li>Unless otherwise stated in the question, all numerical answers should be given exactly or correct to three significant figures.</li>
          <li>A clean copy of the <i>mathematics: analysis and approaches</i> formula booklet is required for this paper.</li>
          <li>The maximum mark for this examination paper is <b>[${total} marks]</b>.</li>
        </ul>
      </div>
      <p class="foot">Questions © International Baccalaureate Organization, reproduced for personal revision. Each question shows its original source below it.</p>
    </section>
    ${secA}${secB}
    <section class="sheet ms-sheet">
      <h3 class="sec-title">Mark scheme</h3>
      <p class="sec-instr">Question numbers refer to this mock paper. Amber entries are unofficial worked solutions, not IB mark schemes.</p>
      ${ms}
    </section>`;
}

function printPaper(withMs) {
  if (!EXAM.size) return;
  showTab("exam");
  document.body.classList.toggle("print-ms", withMs);
  setTimeout(() => window.print(), 30);
}
$("#printPaper").addEventListener("click", () => printPaper(false));
$("#printPaperMs").addEventListener("click", () => printPaper(true));
window.addEventListener("afterprint", () => document.body.classList.remove("print-ms"));

/* ======================= boot ======================= */
setQuery("");
buildFacetUI();
buildExamUI();
saveExam();
update();
showTab(store.get("tab", "bank") === "exam" ? "exam" : "bank");
