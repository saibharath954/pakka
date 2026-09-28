const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const SEG = { independent_house: "Independent house", apartment: "Apartment", commercial: "Commercial", farm: "Farm" };
let current = null;

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

async function busy(btn, fn) {
  const label = btn.textContent; btn.classList.add("loading"); btn.textContent = "Thinking…";
  try { return await fn(); } catch (e) { toast(e.message, 6000); } finally { btn.classList.remove("loading"); btn.textContent = label; }
}

// Tiny markdown renderer: headings, bold, italics, bullets, paragraphs.
function md(src) {
  if (!src) return "";
  const lines = esc(src).split("\n"); let html = "", inList = false;
  const inline = (s) => s.replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/(^|\W)\*(\S.+?)\*(?=\W|$)/g, "$1<i>$2</i>").replace(/`(.+?)`/g, "<code>$1</code>");
  for (const raw of lines) {
    const l = raw.trimEnd();
    const h = l.match(/^(#{1,4})\s+(.*)/); const li = l.match(/^\s*(?:[-*•]|\d+\.)\s+(.*)/);
    if (li) { if (!inList) { html += "<ul>"; inList = true; } html += `<li>${inline(li[1])}</li>`; continue; }
    if (inList) { html += "</ul>"; inList = false; }
    if (h) html += `<h${h[1].length + 1}>${inline(h[2])}</h${h[1].length + 1}>`;
    else if (l.trim()) html += `<p>${inline(l)}</p>`;
  }
  return html + (inList ? "</ul>" : "");
}

function memList(mems, label = "memories recalled") {
  if (!mems?.length) return "";
  return `<details><summary>${mems.length} ${label}</summary>${mems.map((m) =>
    `<div class="mem"><b>${esc(m.ref)}</b> ${m.when ? `<span class="meta">${esc(m.when.slice(0, 10))} · ${esc(m.type || "")}</span><br>` : ""}${esc(m.text)}</div>`).join("")}</details>`;
}

// ---------------------------------------------------------------- leads
async function loadLeads() {
  const leads = await api("/api/leads");
  const order = { open: 0, won: 1, lost: 2 };
  leads.sort((a, b) => (order[a.status] ?? 0) - (order[b.status] ?? 0) || b.id.localeCompare(a.id));
  $("#leads").innerHTML = leads.map((l) => `
    <li data-id="${l.id}" class="${current?.id === l.id ? "sel" : ""}">
      <div><div class="lname">${esc(l.name)}</div><div class="lsub">${esc(SEG[l.segment])} · ${esc(l.locality)}</div></div>
      <span class="chip ${l.status}">${l.status}</span>
    </li>`).join("");
  $("#leads").querySelectorAll("li").forEach((li) => li.onclick = () => select(leads.find((l) => l.id === li.dataset.id)));
  if (current) current = leads.find((l) => l.id === current.id) || current;
}

function select(lead) {
  current = lead;
  document.querySelectorAll("#leads li").forEach((li) => li.classList.toggle("sel", li.dataset.id === lead.id));
  const bill = lead.monthly_bill_inr ? `Rs ${lead.monthly_bill_inr.toLocaleString("en-IN")}/month` : "—";
  $("#lead-card").innerHTML = `
    <div class="lead-title">${esc(lead.name)} <span class="chip ${lead.status}">${lead.status}</span></div>
    <div class="kv">
      <span>Segment</span><span>${esc(SEG[lead.segment])}</span>
      <span>Locality</span><span>${esc(lead.locality)}</span>
      <span>Source</span><span>${esc(lead.source)}</span>
      <span>Bill</span><span>${bill}</span>
      <span>Last message</span><span>${esc(lead.last_message || "—")}</span>
    </div>`;
  document.querySelectorAll("#brief-btn, #compare-btn, #interaction button, #outcome button").forEach((b) => b.disabled = false);
  $("#brief").innerHTML = `<span class="muted">Hindsight <code>reflect</code> over ${esc(lead.name)}'s memories only.</span>`;
  $("#draft-off").innerHTML = `<span class="muted">Stateless LLM: CRM row + last message.</span>`;
  $("#draft-on").innerHTML = `<span class="muted">Recall on this lead + outcomes from similar leads + the learned playbook.</span>`;
}

$("#add-lead-btn").onclick = () => $("#add-lead").classList.toggle("hidden");
$("#add-lead").onsubmit = async (e) => {
  e.preventDefault();
  const f = Object.fromEntries(new FormData(e.target));
  const lead = await api("/api/leads", { method: "POST", body: JSON.stringify(f) });
  e.target.reset(); e.target.classList.add("hidden");
  await loadLeads(); select(lead);
};

// ---------------------------------------------------------------- brief
$("#brief-btn").onclick = (e) => busy(e.target, async () => {
  const r = await api(`/api/leads/${current.id}/brief`);
  $("#brief").innerHTML = `<div class="md">${md(r.brief)}</div>${memList(r.memories, "memories used by reflect")}`;
});

// ---------------------------------------------------------------- retain
$("#interaction").onsubmit = async (e) => {
  e.preventDefault(); const btn = e.target.querySelector("button");
  await busy(btn, async () => {
    const f = Object.fromEntries(new FormData(e.target));
    const r = await api(`/api/leads/${current.id}/interactions`, { method: "POST", body: JSON.stringify(f) });
    $("#retain-log").innerHTML = `✓ retained with tags <code>${r.tags.join("</code> <code>")}</code>`;
    e.target.reset(); await loadLeads(); select(current); toast("Retained to Hindsight");
  });
};
$("#outcome").onsubmit = async (e) => {
  e.preventDefault(); const btn = e.target.querySelector("button");
  await busy(btn, async () => {
    const f = Object.fromEntries(new FormData(e.target));
    const r = await api(`/api/leads/${current.id}/outcomes`, { method: "POST", body: JSON.stringify(f) });
    $("#retain-log").innerHTML = `✓ outcome retained with tags <code>${r.tags.join("</code> <code>")}</code> · playbook refresh queued`;
    e.target.reset(); await loadLeads(); select(current); toast("Outcome retained; playbook will re-learn");
  });
};

// ---------------------------------------------------------------- drafts
function renderDraft(r) {
  const d = r.draft;
  return `
    <div class="msg">${esc(d.message)}</div>
    <div class="meta">approach <code>${esc(d.approach)}</code> · ${esc(d.language)} · send ${esc(d.send_at)}</div>
    ${d.reasoning?.length ? `<ul class="reasons">${d.reasoning.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}
    ${d.avoid?.length ? `<div class="meta">Deliberately avoided:</div><ul class="reasons">${d.avoid.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}
    ${memList(r.memories)}${r.playbook_used ? `<div class="meta">+ playbook mental model</div>` : ""}`;
}
$("#compare-btn").onclick = (e) => busy(e.target, async () => {
  const goal = $("#goal").value.trim();
  const q = goal ? `&goal=${encodeURIComponent(goal)}` : "";
  $("#draft-off").innerHTML = $("#draft-on").innerHTML = `<span class="muted">Drafting…</span>`;
  const [off, on] = await Promise.allSettled([
    api(`/api/leads/${current.id}/draft?memory=false${q}`, { method: "POST" }),
    api(`/api/leads/${current.id}/draft?memory=true${q}`, { method: "POST" }),
  ]);
  $("#draft-off").innerHTML = off.status === "fulfilled" ? renderDraft(off.value) : `<span class="muted">${esc(off.reason.message)}</span>`;
  $("#draft-on").innerHTML = on.status === "fulfilled" ? renderDraft(on.value) : `<span class="muted">${esc(on.reason.message)}</span>`;
});

// ---------------------------------------------------------------- due, playbook, ask
$("#due-btn").onclick = (e) => busy(e.target, async () => {
  const r = await api("/api/due");
  $("#due").innerHTML = r.items.length
    ? r.items.map((i) => `<div class="due-item"><div class="due-when">${esc(i.due)}</div><b>${esc(i.lead_name)}</b>: ${esc(i.action)}<div class="meta">${esc(i.why)}</div></div>`).join("")
    : `<div class="md">${md(r.text || "Nothing due.")}</div>`;
  $("#due").classList.remove("muted");
});

async function loadPlaybook() {
  const p = await api("/api/playbook");
  $("#playbook").innerHTML = p.content ? md(p.content) : `<span class="muted">Nothing learned yet. Load some history, then refresh.</span>`;
  $("#playbook").classList.toggle("muted", !p.content);
  $("#pb-meta").textContent = p.last_refreshed_at ? `last rewritten by Hindsight ${new Date(p.last_refreshed_at).toLocaleString()}` : "";
}
$("#pb-refresh").onclick = (e) => busy(e.target, async () => {
  await api("/api/playbook/refresh", { method: "POST" });
  toast("Refresh started. Hindsight rewrites the playbook in the background");
  setTimeout(loadPlaybook, 4000); setTimeout(loadPlaybook, 15000);
});

$("#ask").onsubmit = async (e) => {
  e.preventDefault(); const btn = e.target.querySelector("button");
  await busy(btn, async () => {
    const r = await api("/api/ask", { method: "POST", body: JSON.stringify({ question: e.target.q.value }) });
    $("#answer").innerHTML = md(r.answer) + memList(r.memories, "memories used");
  });
};

// ---------------------------------------------------------------- history replay
$("#replay-select").onchange = async (e) => {
  const v = e.target.value; e.target.value = ""; if (!v) return;
  const body = { stage1: { reset: true, until_day: -40 }, stage2: { since_day: -40, until_day: 0 }, all: { reset: true, until_day: 0 } }[v];
  if (body.reset && !confirm("This wipes the memory bank and reloads history. Continue?")) return;
  toast("Retaining history into Hindsight… (this takes a minute)", 60000);
  try {
    const r = await api("/api/replay", { method: "POST", body: JSON.stringify(body) });
    toast(`Retained ${r.retained} events. Playbook is re-learning in the background.`);
    await loadLeads(); if (current) select(current);
    setTimeout(loadPlaybook, 5000); setTimeout(loadPlaybook, 20000);
  } catch (err) { toast(err.message, 6000); }
};

// ---------------------------------------------------------------- boot
(async () => {
  const c = await api("/api/config");
  const pill = $("#mem-pill");
  pill.textContent = c.offline ? "memory: OFFLINE stand-in" : `memory: Hindsight · bank ${c.bank_id}`;
  pill.classList.toggle("live", !c.offline);
  await loadLeads(); await loadPlaybook().catch(() => {});
})();
