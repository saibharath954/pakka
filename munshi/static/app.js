/* Munshi front-end. Vanilla JS, no build step. All user/model text goes through esc() or textContent. */
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const inr = (n) => "₹" + Number(n || 0).toLocaleString("en-IN", { maximumFractionDigits: 0 });
const AVATAR = ["#0e6e5c", "#7a4fb3", "#b5542d", "#2a6fb0", "#8a6d12", "#a23a67", "#3d7a2c", "#5b5f97", "#9b3d3d", "#1f7d85"];

const S = {
  config: null, catalog: [], byCode: {}, retailers: [], byId: {}, inbox: [],
  current: null, memoryOn: true, parsed: {}, edits: {}, posted: {}, view: "inbox", metric: "auto_rate", curve: null,
};

// ------------------------------------------------------------------ helpers
function toast(msg, ms = 3200) {
  const t = $("#toast"); t.textContent = msg; t.classList.add("show");
  clearTimeout(t._h); t._h = setTimeout(() => t.classList.remove("show"), ms);
}
async function api(path, opts = {}) {
  const res = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.error || body.detail?.[0]?.msg || body.detail || res.statusText);
  return body;
}
async function busy(btn, fn, label = "Working…") {
  const old = btn.innerHTML; btn.classList.add("loading"); btn.textContent = label;
  try { return await fn(); } catch (e) { toast(e.message, 6000); } finally { btn.classList.remove("loading"); btn.innerHTML = old; }
}
function avatar(r, cls = "") {
  const i = parseInt(r.id.slice(1), 10) % AVATAR.length;
  const initials = r.name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]).join("").toUpperCase();
  return `<div class="avatar ${cls}" style="background:${AVATAR[i]}" aria-hidden="true">${esc(initials)}</div>`;
}
function timeOf(iso) { return new Date(iso).toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit", timeZone: "Asia/Kolkata" }); }
function dateOf(iso) { return iso ? new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", timeZone: "Asia/Kolkata" }) : ""; }
function md(src) {
  if (!src) return "";
  const inline = (s) => s.replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/`(.+?)`/g, "<code>$1</code>");
  let html = "", inList = false;
  for (const raw of esc(src).split("\n")) {
    const l = raw.trimEnd(), h = l.match(/^(#{1,4})\s+(.*)/), li = l.match(/^\s*(?:[-*•]|\d+\.)\s+(.*)/);
    if (li) { if (!inList) { html += "<ul>"; inList = true; } html += `<li>${inline(li[1])}</li>`; continue; }
    if (inList) { html += "</ul>"; inList = false; }
    if (h) html += `<h${Math.min(h[1].length + 2, 5)}>${inline(h[2])}</h${Math.min(h[1].length + 2, 5)}>`;
    else if (l.trim()) html += `<p>${inline(l)}</p>`;
  }
  return html + (inList ? "</ul>" : "");
}
function dots(n, max = 5) {
  return `<span class="dots" aria-label="${n} confirmations">${Array.from({ length: max }, (_, i) => `<i class="${i < n ? "f" : ""}"></i>`).join("")}</span>`;
}
const qtyHint = (sku, units) => {
  const s = S.byCode[sku]; if (!s || !units) return "";
  const cases = units / s.case_qty;
  return Number.isInteger(cases) ? `${cases} case${cases === 1 ? "" : "s"} of ${s.case_qty}` : `${units} pcs`;
};

// ------------------------------------------------------------------ views
function show(view) {
  S.view = view;
  $$(".tabs button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.view === view)));
  $$(".view").forEach((v) => (v.hidden = v.id !== `view-${view}`));
  if (view === "learning") loadLearning();
  if (view === "retailers") renderRetailerList();
  if (view === "ask") renderAskChips();
}
$$(".tabs button").forEach((b) => (b.onclick = () => show(b.dataset.view)));

// ------------------------------------------------------------------ memory switch
function setMemory(on) {
  S.memoryOn = on;
  $("#mem-on").classList.toggle("on", on); $("#mem-on").setAttribute("aria-pressed", String(on));
  $("#mem-off").classList.toggle("on", !on); $("#mem-off").setAttribute("aria-pressed", String(!on));
  $("#memory-pane").classList.toggle("dimmed", !on);
  if (S.current && S.view === "inbox") openMessage(S.current);
  toast(on ? "Memory on: Munshi uses everything it has learned" : "Memory off: Munshi only knows the item master");
}
$("#mem-on").onclick = () => setMemory(true);
$("#mem-off").onclick = () => setMemory(false);

// ------------------------------------------------------------------ inbox
async function loadInbox() {
  S.inbox = await api("/api/inbox");
  renderInbox();
}
function renderInbox() {
  const n = S.inbox.filter((m) => m.status === "new").length;
  $("#new-count").textContent = n ? String(n) : "";
  $("#inbox").innerHTML = S.inbox.map((m) => {
    const r = S.byId[m.retailer_id];
    const snip = m.text.replace(/^\[voice note\]\s*/i, "🎙 ").replace(/\n+/g, " · ");
    return `<li data-id="${m.id}" class="${S.current === m.id ? "sel" : ""}" tabindex="0">
      ${avatar(r)}
      <div style="min-width:0"><div class="li-name">${esc(r.name)}</div><div class="li-snip">${esc(snip)}</div></div>
      <div class="li-meta">${timeOf(m.received_at)}${m.status === "posted" ? `<span class="pill posted">✓ Posted</span>` : `<span class="pill new">New</span>`}</div>
    </li>`;
  }).join("");
  $$("#inbox li").forEach((li) => {
    li.onclick = () => openMessage(li.dataset.id);
    li.onkeydown = (e) => { if (e.key === "Enter") openMessage(li.dataset.id); };
  });
}

function key(id) { return `${id}:${S.memoryOn ? "on" : "off"}`; }

async function openMessage(id) {
  S.current = id;
  $$("#inbox li").forEach((li) => li.classList.toggle("sel", li.dataset.id === id));
  const msg = S.inbox.find((m) => m.id === id);
  const r = S.byId[msg.retailer_id];
  const work = $("#work");
  work.innerHTML = `<div class="ws">${head(r, msg)}${bubble(msg)}
    <div class="readout"><div class="readout-h"><div class="summary"><span class="pill neutral">Reading the order…</span></div></div>
    <div style="padding:16px;display:grid;gap:10px"><div class="skeleton" style="width:70%"></div><div class="skeleton" style="width:55%"></div><div class="skeleton" style="width:62%"></div></div></div></div>`;
  renderMemoryPane(r.id);
  if (S.posted[id]) return renderPosted(id);
  if (msg.status === "posted") {
    work.querySelector(".readout").outerHTML = `<div class="posted-card"><div class="big">✓ Posted as ${esc(msg.order_no)}</div><p class="muted">${inr(msg.total)} · already in Tally export</p></div>`;
    return;
  }
  try {
    if (!S.parsed[key(id)]) S.parsed[key(id)] = await api(`/api/inbox/${id}/parse?memory=${S.memoryOn}`, { method: "POST" });
    if (S.current !== id) return;
    S.edits[key(id)] = S.parsed[key(id)].lines.map((l) => ({ ...l, suggested: l.sku, fixed: false }));
    renderWork(id);
  } catch (e) {
    work.querySelector(".readout").innerHTML = `<div class="banner off">Could not read this order: ${esc(e.message)}</div>`;
  }
}
function head(r, msg) {
  return `<div class="ws-head">${avatar(r)}<div><div class="ws-title">${esc(r.name)}</div>
    <div class="ws-sub">${esc(r.area)} · ${esc(r.owner)} · ${esc(r.style)}</div></div></div>`;
}
function bubble(msg) {
  return `<div class="chat"><div class="bubble">${esc(msg.text)}<span class="bubble-time">${timeOf(msg.received_at)}</span></div></div>`;
}

function statusOf(l) { return l.fixed ? "fixed" : l.status; }
function whyText(l) {
  if (l.fixed) return `<span>Set by you. Munshi will remember this.</span>`;
  if (l.basis === "memory") return `<span class="ev">${dots(l.confirmations)}</span><span>Learned: you confirmed <q>${esc(l.phrase)}</q> ${l.confirmations}× for this shop</span>`;
  if (l.basis === "memory-once") return `<span class="ev">${dots(l.confirmations)}</span><span>Seen once. Check it; one more confirmation and it auto-accepts</span>`;
  if (l.basis === "repeat") return `<span>↻ ${esc(l.note)}</span>`;
  if (l.basis === "catalog") return `<span>Matches the item master</span>`;
  if (l.basis === "conflict") return `<span>⚠ ${esc(l.note)}</span>`;
  if (l.basis === "guess") return `<span>Best guess from the item master. Please check.</span>`;
  return `<span>${esc(l.note || "Munshi doesn't know this yet. Pick the product.")}</span>`;
}

function renderWork(id) {
  const p = S.parsed[key(id)], lines = S.edits[key(id)];
  const msg = S.inbox.find((m) => m.id === id), r = S.byId[msg.retailer_id];
  const auto = lines.filter((l) => statusOf(l) === "auto").length;
  const review = lines.filter((l) => l.status === "review" && !l.fixed).length;
  const unknown = lines.filter((l) => !l.sku).length;
  const total = lines.reduce((s, l) => s + (l.sku ? S.byCode[l.sku].price * l.units : 0), 0);
  const ready = lines.length > 0 && lines.every((l) => l.sku && l.units > 0);
  const banners = [];
  if (!p.use_memory) banners.push(`<div class="banner off">🧠 Memory is <b>off</b>. Munshi only has the item master and the message, like any stateless LLM.</div>`);
  if (p.repeat) banners.push(`<div class="banner repeat">↻ “Same as last time” resolved from memory: order <b>${esc(p.repeat.order_no)}</b> on ${esc(p.repeat.date)}</div>`);
  $("#work").innerHTML = `<div class="ws">${head(r, msg)}${bubble(msg)}
    <div class="readout">
      <div class="readout-h">
        <div class="summary">
          ${auto ? `<span class="pill auto">✓ ${auto} auto</span>` : ""}
          ${review ? `<span class="pill review">? ${review} to check</span>` : ""}
          ${unknown ? `<span class="pill unknown">✕ ${unknown} unknown</span>` : ""}
        </div>
        <div class="xs muted">${p.use_memory ? `${p.stats.memories_recalled} memories recalled` : "no memory"} · parser: ${esc(p.parser)}</div>
      </div>
      ${banners.join("")}
      <ul class="lines">${lines.map((l, i) => lineRow(l, i)).join("")}</ul>
      <div class="readout-f">
        <div><div class="xs muted">Order value (dealer price)</div><div class="total">${inr(total)}</div></div>
        <div class="row">
          <span class="xs muted">${ready ? "" : "Pick a product for every line to confirm"}</span>
          <button class="btn big" id="confirm-btn" ${ready ? "" : "disabled"}>Confirm &amp; post to Tally</button>
        </div>
      </div>
    </div></div>`;
  $$(".sku-btn").forEach((b) => (b.onclick = () => openPicker(b, Number(b.dataset.i))));
  $$(".qty-edit input").forEach((inp) => (inp.onchange = () => {
    const l = lines[Number(inp.dataset.i)]; l.units = Math.max(0, parseInt(inp.value || "0", 10)); l.fixed = l.fixed || l.status !== "auto";
    renderWork(id);
  }));
  $$(".ok-btn").forEach((b) => (b.onclick = () => { const l = lines[Number(b.dataset.i)]; l.fixed = true; renderWork(id); }));
  $("#confirm-btn").onclick = (e) => confirmOrder(id, e.target);
  highlightVocab(lines.map((l) => l.phrase));
}
function lineRow(l, i) {
  const st = statusOf(l), s = l.sku ? S.byCode[l.sku] : null;
  const icon = { auto: "✓", review: "?", unknown: "✕", fixed: "✓" }[st];
  const phrase = l.basis === "repeat" ? `<span class="muted">from last order</span>` : `<q>${esc(l.phrase)}</q>`;
  const qtyRaw = l.basis === "repeat" ? "" : `<span class="qty">${l.qty} ${esc(l.unit)}</span>`;
  const amt = s ? inr(s.price * l.units) : "—";
  const okBtn = st === "review" && l.sku ? `<button class="btn ghost sm ok-btn" data-i="${i}" title="Looks right">✓ Right</button>` : "";
  return `<li class="line ${st}">
    <span class="st ${st}" aria-label="${st}">${icon}</span>
    <div class="phrase">${phrase}${qtyRaw}</div>
    <span class="arrow">→</span>
    <button class="sku-btn ${s ? "" : "empty"}" data-i="${i}" aria-label="Change product">${s ? `<span class="nm">${esc(s.name)}</span><span class="cd">${esc(s.code)}</span>` : "Pick product…"}</button>
    <div class="qty-edit"><input type="number" min="0" value="${l.units}" data-i="${i}" aria-label="Quantity in pieces"><span>${esc(qtyHint(l.sku, l.units) || "pcs")}</span></div>
    <div class="amt">${amt}</div>
    <div class="why">${whyText(l)} ${okBtn}</div>
  </li>`;
}

// ------------------------------------------------------------------ product picker
let pickerTarget = null, pickerIdx = 0;
function openPicker(btn, i) {
  pickerTarget = i; pickerIdx = 0;
  const pk = $("#picker"), rect = btn.getBoundingClientRect();
  pk.hidden = false;
  pk.style.left = `${Math.min(rect.left, window.innerWidth - 380)}px`;
  pk.style.top = `${Math.min(rect.bottom + 6, window.innerHeight - 350)}px`;
  $("#picker-q").value = ""; renderPicker(); $("#picker-q").focus();
}
function pickerItems() {
  const q = $("#picker-q").value.toLowerCase().split(/\s+/).filter(Boolean);
  return S.catalog.filter((s) => q.every((w) => (s.name + " " + s.code).toLowerCase().includes(w))).slice(0, 40);
}
function renderPicker() {
  const items = pickerItems();
  $("#picker-list").innerHTML = items.map((s, j) => `<li data-code="${s.code}" class="${j === pickerIdx ? "act" : ""}"><span>${esc(s.name)}</span><span class="cd">${esc(s.code)}</span></li>`).join("") || `<li class="muted">No match</li>`;
  $$("#picker-list li[data-code]").forEach((li) => (li.onclick = () => pick(li.dataset.code)));
}
function pick(code) {
  const lines = S.edits[key(S.current)], l = lines[pickerTarget];
  if (l.sku !== code) {
    const qtyUnits = l.unit === "case" ? l.qty * S.byCode[code].case_qty : l.unit === "dozen" ? l.qty * 12 : (l.qty || l.units);
    l.units = l.basis === "repeat" ? l.units : qtyUnits;
  }
  l.sku = code; l.fixed = true; closePicker(); renderWork(S.current);
}
function closePicker() { $("#picker").hidden = true; pickerTarget = null; }
$("#picker-q").oninput = () => { pickerIdx = 0; renderPicker(); };
$("#picker-q").onkeydown = (e) => {
  const items = pickerItems();
  if (e.key === "ArrowDown") { pickerIdx = Math.min(pickerIdx + 1, items.length - 1); renderPicker(); e.preventDefault(); }
  if (e.key === "ArrowUp") { pickerIdx = Math.max(pickerIdx - 1, 0); renderPicker(); e.preventDefault(); }
  if (e.key === "Enter" && items[pickerIdx]) { pick(items[pickerIdx].code); e.preventDefault(); }
  if (e.key === "Escape") closePicker();
};
document.addEventListener("mousedown", (e) => { if (!$("#picker").hidden && !e.target.closest("#picker") && !e.target.closest(".sku-btn")) closePicker(); });

// ------------------------------------------------------------------ confirm = the learning step
async function confirmOrder(id, btn) {
  const lines = S.edits[key(id)].filter((l) => l.sku && l.units > 0).map((l) => ({
    phrase: l.basis === "repeat" ? null : l.phrase, sku: l.sku, units: l.units, basis: l.basis, suggested: l.suggested,
  }));
  await busy(btn, async () => {
    const order = await api(`/api/inbox/${id}/confirm`, { method: "POST", body: JSON.stringify({ lines }) });
    S.posted[id] = order;
    Object.keys(S.parsed).forEach((k) => { if (k.startsWith(id + ":")) delete S.parsed[k]; });
    const m = S.inbox.find((x) => x.id === id); m.status = "posted"; m.order_no = order.order_no; m.total = order.total;
    renderInbox(); renderPosted(id);
    const r = S.byId[m.retailer_id]; renderMemoryPane(r.id);
    toast(`Posted ${order.order_no}. ${order.retained.length} facts retained to Hindsight`);
  }, "Posting…");
}
function renderPosted(id) {
  const o = S.posted[id], msg = S.inbox.find((m) => m.id === id), r = S.byId[msg.retailer_id];
  const learned = o.retained.slice(1);
  $("#work").innerHTML = `<div class="ws">${head(r, msg)}${bubble(msg)}
    <div class="posted-card">
      <div class="row" style="justify-content:space-between">
        <div><div class="big">✓ ${esc(o.order_no)} posted</div><div class="muted">${o.lines.length} lines · ${inr(o.total)} · Sales Order voucher ready for Tally</div></div>
        <div class="row"><a class="btn ghost" href="/api/orders/${encodeURIComponent(o.order_no)}.xml" download>⬇ Tally XML</a><button class="btn" id="next-btn">Next order →</button></div>
      </div>
      <h3 style="margin-top:16px">Retained to Hindsight</h3>
      <p class="xs muted">Tagged <code>retailer:${esc(r.id)}</code>. Each confirmation is one more piece of evidence; a nickname auto-accepts once it has two.</p>
      <ul class="learned">${learned.length ? learned.map((t) => `<li>${esc(t)}</li>`).join("") : `<li>Nothing new: every line was already known. The order itself was retained for “same as last time”.</li>`}</ul>
    </div></div>`;
  $("#next-btn").onclick = nextOrder;
}
function nextOrder() {
  const next = S.inbox.find((m) => m.status === "new");
  if (next) openMessage(next.id); else toast("Inbox clear 🎉");
}

// ------------------------------------------------------------------ memory pane
async function renderMemoryPane(rid) {
  const pane = $("#memory-pane .mp-body");
  pane.classList.remove("muted", "small");
  pane.innerHTML = `<div class="skeleton" style="width:60%"></div><div class="skeleton" style="width:80%"></div>`;
  try {
    const d = await api(`/api/retailers/${rid}`);
    if (!S.current || S.inbox.find((m) => m.id === S.current)?.retailer_id !== rid) return;
    pane.innerHTML = memoryHtml(d, true);
    const lines = S.edits[key(S.current)]; if (lines) highlightVocab(lines.map((l) => l.phrase));
    bindDictRefresh(pane, rid);
  } catch (e) { pane.innerHTML = `<p class="muted small">${esc(e.message)}</p>`; }
}
function memoryHtml(d, compact) {
  const r = d.retailer;
  const vocab = d.vocabulary.length
    ? `<table class="vocab">${d.vocabulary.map((v) => `<tr data-phrase="${esc(v.phrase)}"><td class="p">“${esc(v.phrase)}”</td>
        <td class="s">${esc(v.name)}<span class="cd">${esc(v.sku)}${v.conflicts.length ? " · ⚠ was also " + esc(v.conflicts.join(", ")) : ""}</span></td>
        <td style="text-align:right;white-space:nowrap">${dots(v.confirmations)}<div class="xs muted">${v.status === "auto" ? "auto" : "learning"}</div></td></tr>`).join("")}</table>`
    : `<p class="small muted">No nicknames learned yet. Confirm an order from ${esc(r.name)} and they appear here.</p>`;
  const dict = d.dictionary?.content
    ? `<div class="dict md">${md(d.dictionary.content)}</div><div class="xs muted" style="margin-top:4px">Hindsight mental model · refreshed ${d.dictionary.last_refreshed_at ? dateOf(d.dictionary.last_refreshed_at) : "—"}</div>`
    : `<p class="small muted">Hindsight writes this after it consolidates a few orders.</p>`;
  const orders = d.orders.length
    ? `<ul class="orders">${d.orders.map((o) => `<li><b>${esc(o.date)}</b> · ${esc(o.order_no)}<div class="muted">${esc(o.lines)}</div></li>`).join("")}</ul>`
    : `<p class="small muted">No confirmed orders yet.</p>`;
  return `
    ${compact ? `<div class="row">${avatar(r)}<div><b>${esc(r.name)}</b><div class="xs muted">${esc(r.area)} · ${esc(r.style)}</div></div></div>` : ""}
    <div class="mp-section"><h3>Learned vocabulary · ${d.vocabulary.length}</h3>${vocab}</div>
    <div class="mp-section"><div class="row" style="justify-content:space-between"><h3>Ordering dictionary</h3><button class="btn ghost sm dict-refresh">Refresh</button></div>${dict}</div>
    <div class="mp-section"><h3>Recent orders</h3>${orders}</div>`;
}
function bindDictRefresh(root, rid) {
  const b = $(".dict-refresh", root);
  if (b) b.onclick = () => busy(b, async () => { await api(`/api/retailers/${rid}/dictionary/refresh`, { method: "POST" }); toast("Hindsight is rewriting the dictionary. Check back in a few seconds"); });
}
function highlightVocab(phrases) {
  const set = new Set(phrases.map((p) => (p || "").toLowerCase()));
  $$("#memory-pane .vocab tr").forEach((tr) => tr.classList.toggle("hit", set.has(tr.dataset.phrase)));
}

// ------------------------------------------------------------------ new message modal
const EXAMPLES = {
  R01: ["blue wala 1 cartoon, tel 2 cartoon", "same as last time, plus maggi 1 cartoon extra"],
  R06: ["blue wala 1 box, green wala 1 box", "parle bada 1 box, kurkure 2 box"],
  R02: ["red paste 1 box, sabbu 1 box, 3 roses chinna 1 box"],
  R03: ["RL250 - 1cs\nSEQ1 - 1cs\nCG200 - 1cs"],
  R07: ["green sabun 1 peti, bathroom wala 12 pc"],
  R10: ["maggi bada 1 peti, surf 1 peti, wheel 1 peti"],
};
$("#new-msg-btn").onclick = () => {
  $("#nm-retailer").innerHTML = S.retailers.map((r) => `<option value="${r.id}">${esc(r.name)} · ${esc(r.area)}</option>`).join("");
  renderExamples(); $("#new-msg-modal").hidden = false; $("#new-msg-form textarea").focus();
};
$("#nm-retailer").onchange = renderExamples;
function renderExamples() {
  const ex = EXAMPLES[$("#nm-retailer").value] || [];
  $("#nm-examples").innerHTML = ex.map((t) => `<button type="button" class="chip">${esc(t.replace(/\n/g, " · "))}</button>`).join("");
  $$("#nm-examples .chip").forEach((c, i) => (c.onclick = () => ($("#new-msg-form textarea").value = ex[i])));
}
$$("[data-close]").forEach((b) => (b.onclick = () => (b.closest(".modal").hidden = true)));
$("#new-msg-form").onsubmit = async (e) => {
  e.preventDefault();
  const f = Object.fromEntries(new FormData(e.target));
  const msg = await api("/api/inbox", { method: "POST", body: JSON.stringify(f) });
  $("#new-msg-modal").hidden = true; e.target.reset();
  await loadInbox(); openMessage(msg.id);
};

// ------------------------------------------------------------------ learning curve
async function loadLearning() {
  const d = await api("/api/learning");
  S.curve = d.curve; S.curveSample = d.sample;
  renderReplayState(d.replay);
  if (!d.curve) {
    $("#kpis").innerHTML = ""; $("#chart").innerHTML = `<div class="empty-state"><h3>No replay yet</h3><p>Click <b>Run replay</b> to push eight weeks of orders through Hindsight and measure the curve.</p></div>`;
    return;
  }
  renderKpis(); renderChart();
}
function renderKpis() {
  const w = S.curve.with_memory, o = S.curve.without_memory, tw = S.curve.totals.with_memory, to = S.curve.totals.without_memory;
  const first = w[0], last = w[w.length - 1];
  const pct = (x) => Math.round(x * 100);
  $("#kpis").innerHTML = `
    <div class="kpi"><div class="k-label">Lines auto-accepted, week 8</div><div class="k-val">${pct(last.auto_rate)}%</div><div class="k-foot">from ${pct(first.auto_rate)}% in week 1 · without memory: ${pct(o[o.length - 1].auto_rate)}%</div></div>
    <div class="kpi"><div class="k-label">Orders with zero operator touches, week 8</div><div class="k-val">${last.touchless}<small>/${last.messages}</small></div><div class="k-foot">week 1: ${first.touchless}/${first.messages} · without memory: ${o[o.length - 1].touchless}/${o[o.length - 1].messages}</div></div>
    <div class="kpi"><div class="k-label">Wrong auto-accepts, all 8 weeks</div><div class="k-val">${tw.auto_wrong} <small>vs ${to.auto_wrong} without</small></div><div class="k-foot">Nicknames need 2 confirmations before auto-accept</div></div>
    <div class="kpi"><div class="k-label">Operator touches saved</div><div class="k-val">${to.touched - tw.touched}</div><div class="k-foot">${tw.touched} lines needed a human with memory, ${to.touched} without</div></div>`;
}
function renderChart() {
  const metric = S.metric, root = $("#chart");
  const w = S.curve.with_memory, o = S.curve.without_memory;
  const meta = `${S.curveSample ? "Sample run bundled with the repo (offline memory stand-in). " : ""}Mode: ${esc(S.curve.mode)} · parser: ${esc(S.curve.parser)} · ${esc(S.curve.gate)} · generated ${esc(S.curve.generated_at)}`;
  $("#curve-meta").textContent = meta;
  if (metric === "table") {
    $("#legend").innerHTML = "";
    root.innerHTML = `<table class="data-table"><thead><tr><th>Week</th><th>Orders</th><th>Lines</th><th>Auto ✓ (memory)</th><th>Auto ✓ (no memory)</th><th>Touchless (memory)</th><th>Touchless (no memory)</th><th>Wrong auto (memory)</th><th>Wrong auto (no memory)</th></tr></thead><tbody>
      ${w.map((x, i) => `<tr><td>Week ${x.week}</td><td>${x.messages}</td><td>${x.lines}</td><td>${x.auto_correct} (${Math.round(x.auto_rate * 100)}%)</td><td>${o[i].auto_correct} (${Math.round(o[i].auto_rate * 100)}%)</td><td>${x.touchless}</td><td>${o[i].touchless}</td><td>${x.auto_wrong}</td><td>${o[i].auto_wrong}</td></tr>`).join("")}
    </tbody></table>`;
    return;
  }
  $("#chart-title").textContent = metric === "auto_rate" ? "Order lines auto-accepted correctly" : "Orders posted with zero operator touches";
  $("#chart-sub").textContent = metric === "auto_rate"
    ? "Share of each week's lines Munshi filled in with the right product and quantity and did not need the operator for."
    : "Share of each week's orders where every line was right and nothing needed a human.";
  const W = Math.max(root.clientWidth, 320), H = 320, m = { t: 16, r: 150, b: 34, l: 44 };
  const iw = W - m.l - m.r, ih = H - m.t - m.b;
  const x = (i) => m.l + (i / (w.length - 1)) * iw, y = (v) => m.t + ih - v * ih;
  const path = (arr) => arr.map((d, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(d[metric]).toFixed(1)}`).join("");
  const grid = [0, .25, .5, .75, 1].map((v) => `<line class="gridline" x1="${m.l}" x2="${m.l + iw}" y1="${y(v)}" y2="${y(v)}"/><text class="axis-text" x="${m.l - 8}" y="${y(v) + 4}" text-anchor="end">${v * 100}%</text>`).join("");
  const xt = w.map((d, i) => `<text class="axis-text" x="${x(i)}" y="${H - 10}" text-anchor="middle">W${d.week}</text>`).join("");
  const lastW = w[w.length - 1][metric], lastO = o[o.length - 1][metric];
  let ly1 = y(lastW), ly2 = y(lastO); if (Math.abs(ly1 - ly2) < 18) { ly2 = ly1 + 18; }
  root.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Weekly ${metric === "auto_rate" ? "auto-accept rate" : "touchless order rate"}, with and without memory">
    ${grid}${xt}
    <path class="series s2" d="${path(o)}"/><path class="series s1" d="${path(w)}"/>
    ${o.map((d, i) => `<circle class="m2" cx="${x(i)}" cy="${y(d[metric])}" r="4"/>`).join("")}
    ${w.map((d, i) => `<circle class="m1" cx="${x(i)}" cy="${y(d[metric])}" r="4"/>`).join("")}
    <text class="dlabel" x="${x(w.length - 1) + 10}" y="${ly1 + 4}">With memory ${Math.round(lastW * 100)}%</text>
    <text class="dlabel" x="${x(o.length - 1) + 10}" y="${ly2 + 4}">Without ${Math.round(lastO * 100)}%</text>
    <line class="hair" id="hair" x1="0" x2="0" y1="${m.t}" y2="${m.t + ih}" visibility="hidden"/>
    <rect id="hit" x="${m.l}" y="${m.t}" width="${iw}" height="${ih}" fill="transparent"/>
  </svg><div class="tip" id="tip" hidden></div>`;
  $("#legend").innerHTML = `<span><span class="sw s1"></span>With Hindsight memory</span><span><span class="sw s2"></span>Without memory</span>`;
  const svg = $("svg", root), hit = $("#hit", root), hair = $("#hair", root), tip = $("#tip", root);
  const move = (evt) => {
    const pt = svg.getBoundingClientRect(), sx = (evt.clientX - pt.left) * (W / pt.width);
    const i = Math.max(0, Math.min(w.length - 1, Math.round(((sx - m.l) / iw) * (w.length - 1))));
    hair.setAttribute("x1", x(i)); hair.setAttribute("x2", x(i)); hair.setAttribute("visibility", "visible");
    const a = w[i], b = o[i];
    tip.hidden = false;
    const topY = y(Math.max(a[metric], b[metric]));
    tip.style.left = `${Math.min(Math.max((x(i) / W) * pt.width, 100), pt.width - 100)}px`;
    tip.style.top = `${((topY < 90 ? y(Math.min(a[metric], b[metric])) + 96 : topY) / H) * pt.height}px`;
    const lbl = metric === "auto_rate" ? (d) => `${Math.round(d.auto_rate * 100)}% <span class="muted">(${d.auto_correct}/${d.lines})</span>` : (d) => `${Math.round(d.touchless_rate * 100)}% <span class="muted">(${d.touchless}/${d.messages})</span>`;
    tip.innerHTML = `<div class="t-h">Week ${a.week}</div><div class="t-r"><span><span class="sw s1"></span>With memory</span><b>${lbl(a)}</b></div><div class="t-r"><span><span class="sw s2"></span>Without</span><b>${lbl(b)}</b></div>`;
  };
  hit.onpointermove = move; hit.onpointerdown = move;
  hit.onpointerleave = () => { tip.hidden = true; hair.setAttribute("visibility", "hidden"); };
}
$$(".seg-opt").forEach((b) => (b.onclick = () => {
  $$(".seg-opt").forEach((x) => x.classList.toggle("on", x === b)); S.metric = b.dataset.metric; if (S.curve) renderChart();
}));
window.addEventListener("resize", () => { if (S.view === "learning" && S.curve) renderChart(); });
$("#run-replay").onclick = async () => {
  if (!confirm("This wipes the memory bank and replays 96 orders through it (twice: with and without memory). With Hindsight Cloud it takes several minutes. Continue?")) return;
  const st = await api("/api/learning/run", { method: "POST" }); renderReplayState(st); pollReplay();
};
function renderReplayState(st) {
  const box = $("#replay-progress");
  if (!st || (!st.running && !st.error)) { box.hidden = true; $("#run-replay").disabled = false; return; }
  box.hidden = false; $("#run-replay").disabled = !!st.running;
  const pct = st.total ? (st.done / st.total) * 50 + (st.phase === "with" ? 50 : 0) : 0;
  $(".bar span", box).style.width = `${pct}%`;
  $("#replay-text").textContent = st.error ? `Error: ${st.error}` : `${st.phase === "with" ? "With memory" : "Without memory"}: ${st.done}/${st.total} orders`;
}
async function pollReplay() {
  const d = await api("/api/learning"); renderReplayState(d.replay);
  if (d.replay.running) return setTimeout(pollReplay, 1500);
  if (!d.replay.error) { toast("Replay finished"); S.parsed = {}; loadLearning(); loadInbox(); }
}

// ------------------------------------------------------------------ retailers view
function renderRetailerList() {
  $("#retailer-list").innerHTML = S.retailers.map((r) => `<li data-id="${r.id}">${avatar(r)}<div><div class="li-name">${esc(r.name)}</div><div class="li-snip">${esc(r.area)} · ${esc(r.style)}</div></div><div></div></li>`).join("");
  $$("#retailer-list li").forEach((li) => (li.onclick = async () => {
    $$("#retailer-list li").forEach((x) => x.classList.toggle("sel", x === li));
    const det = $("#retailer-detail");
    det.innerHTML = `<div class="rd"><div class="skeleton" style="width:40%"></div></div>`;
    const d = await api(`/api/retailers/${li.dataset.id}`);
    const r = d.retailer;
    det.innerHTML = `<div class="rd">
      <div class="rd-head">${avatar(r)}<div><div class="ws-title">${esc(r.name)}</div><div class="ws-sub">${esc(r.area)} · ${esc(r.owner)} · writes in ${esc(r.style)}</div></div></div>
      <div class="card">${memoryHtml({ ...d, orders: [] }, false).split('<div class="mp-section"><h3>Recent orders')[0]}</div>
      <div class="card"><div class="mp-section"><h3>Recent orders</h3>${d.orders.length ? `<ul class="orders">${d.orders.map((o) => `<li><b>${esc(o.date)}</b> · ${esc(o.order_no)}<div class="muted">${esc(o.lines)}</div></li>`).join("")}</ul>` : `<p class="small muted">No confirmed orders yet.</p>`}</div></div>
    </div>`;
    bindDictRefresh(det, r.id);
  }));
}

// ------------------------------------------------------------------ ask
const QUESTIONS = ["What does “blue wala” mean for each shop?", "Which retailers are overdue for their usual order?", "Which nicknames did the operator have to correct?", "What does Venkat Provisions' usual list contain?"];
function renderAskChips() {
  $("#ask-chips").innerHTML = QUESTIONS.map((q) => `<button type="button" class="chip">${esc(q)}</button>`).join("");
  $$("#ask-chips .chip").forEach((c, i) => (c.onclick = () => { $("#ask-form input").value = QUESTIONS[i]; $("#ask-form").requestSubmit(); }));
}
$("#ask-form").onsubmit = async (e) => {
  e.preventDefault();
  const q = e.target.q.value.trim(); if (!q) return;
  const card = document.createElement("div"); card.className = "answer";
  card.innerHTML = `<div class="q">${esc(q)}</div><div class="skeleton" style="width:70%"></div>`;
  $("#answers").prepend(card);
  try {
    const r = await api("/api/ask", { method: "POST", body: JSON.stringify({ question: q }) });
    card.innerHTML = `<div class="q">${esc(q)}</div><div class="md">${md(r.answer)}</div>${r.memories.length ? `<details class="xs"><summary class="muted">${r.memories.length} memories used</summary>${r.memories.map((m) => `<div class="mem-item"><span class="when">${esc(dateOf(m.when))} · ${esc(m.type || "")}</span><br>${esc(m.text)}</div>`).join("")}</details>` : ""}`;
  } catch (err) { card.innerHTML = `<div class="q">${esc(q)}</div><p class="muted">${esc(err.message)}</p>`; }
};
$("#insights-btn").onclick = (e) => busy(e.target, async () => {
  const r = await api("/api/insights");
  const icon = { overdue: "⏰", pattern: "📈", risk: "⚠️" };
  $("#insights").innerHTML = r.items.length
    ? r.items.map((i) => `<div class="insight"><span class="ic">${icon[i.kind] || "•"}</span><div><b>${esc(i.retailer)}: ${esc(i.headline)}</b><p>${esc(i.detail)}</p></div></div>`).join("")
    : `<div class="answer md">${md(r.text || "Nothing stands out yet.")}</div>`;
}, "Reflecting…");

// ------------------------------------------------------------------ keyboard
document.addEventListener("keydown", (e) => {
  if (e.target.matches("input, textarea, select") || !$("#picker").hidden) return;
  if (S.view !== "inbox") return;
  if (e.key === "m" || e.key === "M") setMemory(!S.memoryOn);
  if (e.key === "ArrowDown" || e.key === "ArrowUp" || e.key === "j" || e.key === "k") {
    const i = S.inbox.findIndex((m) => m.id === S.current), d = e.key === "ArrowDown" || e.key === "j" ? 1 : -1;
    const n = S.inbox[Math.max(0, Math.min(S.inbox.length - 1, i + d))]; if (n) openMessage(n.id); e.preventDefault();
  }
  if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { const b = $("#confirm-btn"); if (b && !b.disabled) b.click(); }
});

// ------------------------------------------------------------------ boot
(async () => {
  try {
    const [cfg, cat, rets] = await Promise.all([api("/api/config"), api("/api/catalog"), api("/api/retailers")]);
    S.config = cfg; S.catalog = cat; S.byCode = Object.fromEntries(cat.map((s) => [s.code, s]));
    S.retailers = rets; S.byId = Object.fromEntries(rets.map((r) => [r.id, r]));
    $("#company").textContent = `${cfg.company} · ${cfg.city}`;
    const conn = $("#conn");
    conn.classList.add(cfg.offline ? "offline" : "live");
    $("#conn-text").textContent = cfg.offline ? "Offline stand-in" : `Hindsight · ${cfg.bank_id}`;
    conn.title = cfg.offline ? "MUNSHI_OFFLINE=1: keyword stand-in, not Hindsight" : `Connected to Hindsight bank ${cfg.bank_id}; parser: ${cfg.parser}`;
    await loadInbox();
    const first = S.inbox.find((m) => m.status === "new") || S.inbox[0];
    if (first) openMessage(first.id);
  } catch (e) { toast(`Could not start: ${e.message}`, 8000); }
})();
