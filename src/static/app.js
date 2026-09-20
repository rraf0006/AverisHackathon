// ShipCheck dashboard — plain JS, no build step.
const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const CAT = {
  BL_COMPARISON: ["Check BL", "pill-brand"], SI_REQUEST: ["New SI", "pill-info"],
  INVOICE_QUERY: ["Invoice", "pill-grey"], GENERAL: ["General", "pill-grey"], SPAM: ["Spam", "pill-grey"],
};
const STATUS = {
  OK: ["✓ Matches", "pill-ok"], MISMATCH: ["✗ Doesn't match", "pill-bad"],
  NEEDS_REVIEW: ["! Needs a person", "pill-amber"], WAITING_FOR_BL: ["⏳ Waiting for BL", "pill-grey"],
  NOT_CHECKED: ["", ""],
};
const REASON = {
  wrong_doc_type: "Wrong document attached", missing_attachment: "A document is missing",
  unreadable: "Can't read a file", missing_value: "A field is blank", processing_error: "Something went wrong",
};
const BY = { rule: "sorted by rules", llm: "sorted by AI", rule_low_confidence: "not sure — please check" };

const state = { cfg: null, rows: [], sel: null, cat: null, status: null, ai: false, q: "", view: "inbox" };

async function api(path, opts = {}) {
  const r = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
  return r.json();
}
const catPill = (c) => (CAT[c] ? `<span class="pill ${CAT[c][1]}">${CAT[c][0]}</span>` : "");
const statusPill = (s) => (STATUS[s] && STATUS[s][0] ? `<span class="pill ${STATUS[s][1]}">${STATUS[s][0]}</span>` : "");

// stat-card icons (inline so there is no icon-font dependency)
const _sv = (d) => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${d}</svg>`;
const ICON = {
  mail: _sv('<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/>'),
  check: _sv('<path d="M20 6 9 17l-5-5"/>'),
  alert: _sv('<circle cx="12" cy="12" r="9"/><path d="M12 8v5"/><path d="M12 16h.01"/>'),
  person: _sv('<circle cx="12" cy="8" r="3.5"/><path d="M5 20a7 7 0 0 1 14 0"/>'),
  clock: _sv('<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>'),
};

// ---------------------------------------------------------------- stats
async function loadStats() {
  const s = await api("/api/summary");
  const ds = s.doc_status || {};
  $("#queue-count").textContent = s.open_reviews;
  $("#queue-count").hidden = !s.open_reviews;
  $("#stats").innerHTML = [
    ["Emails sorted", s.total, "", ICON.mail],
    ["BL checks done", (ds.OK || 0) + (ds.MISMATCH || 0), "", ICON.check],
    ["Mistakes caught", ds.MISMATCH || 0, "bad", ICON.alert],
    ["Waiting for a person", s.open_reviews, "warn", ICON.person],
    ["Staff time saved", "≈" + Math.round(s.minutes_saved / 60) + "h", "ok", ICON.clock],
  ].map(([l, n, c, i]) => `<div class="stat ${c}"><span class="stat-ico">${i}</span>` +
       `<div><div class="l">${l}</div><div class="n">${n}</div></div></div>`).join("");
  state.summary = s;
}

// ---------------------------------------------------------------- list
function chips() {
  $("#cat-chips").innerHTML = [["All types", null], ...Object.entries(CAT).map(([k, v]) => [v[0], k])]
    .map(([l, v]) => `<button class="chip ${state.cat === v ? "on" : ""}" data-cat="${v ?? ""}">${l}</button>`).join("");
  $("#status-chips").innerHTML = [["Any result", null], ["Doesn't match", "MISMATCH"], ["Needs a person", "NEEDS_REVIEW"], ["Matches", "OK"], ["Waiting for BL", "WAITING_FOR_BL"]]
    .map(([l, v]) => `<button class="chip ${state.status === v ? "on" : ""}" data-status="${v ?? ""}">${l}</button>`).join("")
    + `<button class="chip chip-ai ${state.ai ? "on" : ""}" data-ai="1" title="Only the emails where the AI did something the rules couldn't">✦ AI stepped in</button>`;
}

async function loadList() {
  const p = new URLSearchParams();
  if (state.cat) p.set("category", state.cat);
  if (state.status) p.set("status", state.status);
  if (state.q) p.set("q", state.q);
  if (state.ai) p.set("ai", "true");
  if (state.view === "queue") p.set("queue", "true");
  state.rows = await api("/api/emails?" + p);
  renderList();
}

function renderList() {
  const el = $("#list");
  if (!state.rows.length) {
    el.innerHTML = `<div class="empty">${state.view === "queue" ? "Nothing waiting for a person 🎉" : "No emails match."}</div>`;
    return;
  }
  el.innerHTML = state.rows.map((r) => `
    <div class="row ${state.sel === r.email_id ? "sel" : ""}" data-id="${r.email_id}" role="listitem">
      <div class="subj">${esc(r.subject)}</div>
      <div class="meta">${catPill(r.category)} ${statusPill(r.status)}
        ${r.review_reason ? `<span>${esc(REASON[r.review_reason] || r.review_reason)}</span>` : ""}
        ${r.status === "MISMATCH" ? `<span>${r.defect_fields.length} field(s)</span>` : ""}
        ${r.reviewed ? `<span class="pill pill-ok">✔ reviewed</span>` : ""}
        ${r.uploaded ? `<span class="pill pill-info">new</span>` : ""}
        ${r.ai ? `<span class="pill pill-brand" title="The AI did something here the rules couldn't">✦ AI</span>` : ""}
        <span style="margin-left:auto">${esc(r.email_id)}</span></div>
    </div>`).join("");
}

// ---------------------------------------------------------------- detail
async function openEmail(id) {
  state.sel = id;
  renderList();
  $("#detail").innerHTML = `<div class="empty">Loading…</div>`;
  const e = await api("/api/emails/" + encodeURIComponent(id));
  renderDetail(e);
  if (window.innerWidth < 900 && state.userClicked) $("#detail").scrollIntoView({ behavior: "smooth" });
  state.userClicked = false;
  if (location.hash !== `#/${state.view}/${id}`) history.replaceState(null, "", `#/${state.view}/${id}`);
}

function banner(e) {
  const f = state.cfg.fields;
  if (e.category !== "BL_COMPARISON")
    return `<div class="banner grey">No BL check needed<small>This email is sorted as “${CAT[e.category]?.[0]}”. ${esc(e.class_reason || "")}</small></div>`;
  if (e.status === "OK") return `<div class="banner ok">✓ No mismatch detected<small>All 7 fields on the draft BL match the Shipping Instruction.</small></div>`;
  if (e.status === "MISMATCH")
    return `<div class="banner bad">✗ ${e.defect_fields.length} field(s) don't match: ${e.defect_fields.map((x) => esc(f[x])).join(", ")}<small>The draft BL must be corrected before it is finalised.</small></div>`;
  if (e.status === "NEEDS_REVIEW")
    return `<div class="banner warn">! Needs a person — ${esc(REASON[e.review_reason] || e.review_reason)}<small>${esc(e.review_detail || "")}</small></div>`;
  if (e.status === "WAITING_FOR_BL") return `<div class="banner grey">⏳ Waiting for the draft BL<small>This is a request to check a BL, but no documents were attached yet.</small></div>`;
  return "";
}

function comparisonTable(e) {
  if (!e.comparison?.length) return "";
  const rows = e.comparison.map((r, i) => {
    const cls = r.match === false ? "mismatch clickable" : r.match === null ? "blank clickable" : "clickable";
    const res = r.match === true ? `<span class="pill pill-ok">Same</span>` : r.match === false ? `<span class="pill pill-bad">Different</span>` : `<span class="pill pill-amber">Can't tell</span>`;
    const src = (s) => (s === "ai" ? "matched by AI" : s === "ai-vision" ? "read from scan by AI" : s === "rules" ? "found by label" : "not found");
    return `<tr class="${cls}" data-ev="${i}"><td><b>${esc(r.label)}</b></td><td class="v">${esc(r.si ?? "—")}</td><td class="v">${esc(r.bl ?? "—")}</td><td>${res}${r.note ? `<div class="muted" style="font-size:11px">${esc(r.note)}</div>` : ""}</td></tr>
      <tr class="evidence" data-evrow="${i}" hidden><td></td><td>From the SI: <code>${esc(r.si_quote ?? "—")}</code><br><span class="muted">${src(r.si_source)}</span></td>
        <td>From the BL: <code>${esc(r.bl_quote ?? "—")}</code><br><span class="muted">${src(r.bl_source)}</span></td><td></td></tr>`;
  }).join("");
  return `<h3>Shipping Instruction vs draft BL <span class="muted">· click a row to see where each value came from</span></h3>
    <table class="cmp"><thead><tr><th>Field</th><th>Shipping Instruction (correct)</th><th>Draft BL</th><th>Result</th></tr></thead><tbody>${rows}</tbody></table>`;
}

function docsBlock(e) {
  if (!e.documents?.length) return "";
  const TYPE = { SI: "Shipping Instruction", BL: "Bill of Lading", COMMERCIAL_INVOICE: "Commercial Invoice", PACKING_LIST: "Packing List", CERTIFICATE_OF_ORIGIN: "Certificate of Origin", UNKNOWN: "Unknown" };
  return `<h3>Attachments</h3><div class="docs">${e.documents.map((d) => `
    <a class="doc ${d.ok || d.ai_read ? "" : "bad"}" href="/api/files/${encodeURI(d.path)}" target="_blank" rel="noopener">
      <b>📄 ${esc(d.path.split("/").pop())}</b>
      <span>${d.ok || d.ai_read ? esc(TYPE[d.doc_type] || d.doc_type) : "⚠ " + esc({ empty: "Empty file", corrupt: "Damaged file", no_text_layer: "Scanned image" }[d.error] || d.error)}</span>
      ${d.ai_read ? `<span class="pill pill-info">read by AI</span>` : ""}
    </a>`).join("")}</div>`;
}

function aiBlock(e) {
  const used = e.ai_used || [];
  const op = e.second_opinion;
  if (!used.length && !op) return "";
  const list = used.length
    ? `<ul class="ai-list">${used.map((u) => `<li>${esc(u)}</li>`).join("")}</ul>`
    : "";
  const second = op
    ? `<div class="ai-verdict ${op.agrees ? "agree" : "disagree"}">
         <b>${op.agrees ? "✓ The AI reviewer agrees with the rules" : "⚠ The AI reviewer disagrees with the rules"}</b>
         <p>${esc(op.note || "")}</p>
         <small>Independent second read by ${esc(op.model || "the AI")}. Advisory only — the decision above
         comes from the deterministic comparison, never from this. A disagreement is a signal for a person,
         not an automatic override.</small>
       </div>`
    : "";
  return `<h3>Where the AI helped <span class="muted">— everything else was decided by rules</span></h3>
    <div class="ai-panel">${list}${second}</div>`;
}

function traceBlock(e) {
  if (!e.trace?.length) return "";
  return `<h3>What the system did</h3><ol class="trace">${e.trace.map((t) =>
    `<li class="${t.status}"><span class="s">${esc(t.step)}</span> <span class="ms">${t.ms} ms</span><div>${esc(t.detail)}</div></li>`).join("")}</ol>`;
}

function reviewBlock(e) {
  const f = state.cfg.fields;
  const rv = e.review;
  let head;
  if (rv) {
    head = `<div class="done">✔ ${rv.action === "confirm" ? "Confirmed" : "Corrected"} by ${esc(rv.reviewer || "a reviewer")} · ${esc(rv.at)}</div>
      ${rv.action === "correct" ? `<div class="muted">The system first said: ${esc(CAT[e.system.category]?.[0])} · ${esc(STATUS[e.system.status]?.[0] || "")} ${e.system.defect_fields?.length ? "(" + e.system.defect_fields.map((x) => f[x]).join(", ") + ")" : ""}</div>` : ""}
      ${rv.note ? `<div>“${esc(rv.note)}”</div>` : ""}`;
  } else if (e.status === "NEEDS_REVIEW" || e.decided_by === "rule_low_confidence") {
    head = `<b>The system isn't sure. Please check the documents above and decide.</b>`;
  } else {
    head = `<b>Is this right?</b> <span class="muted">A quick confirm helps the team trust the result.</span>`;
  }
  const catOpts = Object.entries(CAT).map(([k, v]) => `<option value="${k}" ${e.category === k ? "selected" : ""}>${v[0]}</option>`).join("");
  const stOpts = ["OK", "MISMATCH", "NEEDS_REVIEW", "WAITING_FOR_BL"].map((k) => `<option value="${k}" ${e.status === k ? "selected" : ""}>${STATUS[k][0]}</option>`).join("");
  const boxes = Object.entries(f).map(([k, l]) => `<label style="font-weight:400;display:flex;gap:4px;align-items:center"><input type="checkbox" name="df" value="${k}" ${e.defect_fields?.includes(k) ? "checked" : ""} style="width:auto"> ${esc(l)}</label>`).join("");
  return `<h3>Human check</h3><div class="review">${head}
    <div class="actions">
      <button class="btn btn-ok" data-act="confirm">✔ Yes, this is right</button>
      <button class="btn" data-act="toggle-correct">✎ No, change it</button>
      ${e.status === "MISMATCH" ? `<button class="btn btn-primary" data-act="draft">✉ Write email to shipping line</button>` : ""}
      <button class="btn btn-ghost" data-act="retry" title="Run the checks again">↻ Run again</button>
    </div>
    <form id="correct-form" hidden>
      <label>Email type <select name="category">${catOpts}</select></label>
      <label>Result <select name="status">${stOpts}</select></label>
      <div><b style="font-size:13px">Fields that don't match</b><div class="fields">${boxes}</div></div>
      <label>Note (optional) <input name="note" placeholder="e.g. Consignee is a known alias, OK to pass"></label>
      <label>Your name <input name="reviewer" placeholder="e.g. Nandhini"></label>
      <div><button class="btn btn-primary" type="submit">Save correction</button></div>
    </form></div>`;
}

function renderDetail(e) {
  const conf = e.class_confidence != null ? Math.round(e.class_confidence * 100) + "%" : "";
  $("#detail").innerHTML = `
    <div class="d-head"><div class="tags">${catPill(e.category)} ${statusPill(e.status)}</div>
      <h2>${esc(e.subject)}</h2>
      <div class="meta">From ${esc(e.from)} · ${esc(e.email_id)} · ${esc(BY[e.decided_by] || e.decided_by)}${conf ? " (" + conf + " sure)" : ""}</div></div>
    ${banner(e)}
    ${comparisonTable(e)}
    ${docsBlock(e)}
    ${reviewBlock(e)}
    ${aiBlock(e)}
    ${traceBlock(e)}
    <h3>Email</h3><details class="body" ${e.comparison?.length ? "" : "open"}><summary>Show the email text</summary><pre>${esc(e.body)}</pre></details>`;
  const d = $("#detail");
  d.querySelectorAll("tr[data-ev]").forEach((tr) => tr.addEventListener("click", () => {
    const ev = d.querySelector(`tr[data-evrow="${tr.dataset.ev}"]`); ev.hidden = !ev.hidden;
  }));
  d.querySelector('[data-act="confirm"]').onclick = () => saveReview(e.email_id, { action: "confirm", reviewer: localStorage.getItem("reviewer") || null });
  d.querySelector('[data-act="toggle-correct"]').onclick = () => { const f = $("#correct-form"); f.hidden = !f.hidden; };
  d.querySelector('[data-act="retry"]').onclick = async (ev) => {
    ev.target.disabled = true; ev.target.textContent = "Running…";
    try { renderDetail(await api(`/api/emails/${e.email_id}/reprocess`, { method: "POST" })); await refresh(); }
    catch (err) { alert("Retry failed: " + err.message); ev.target.disabled = false; }
  };
  const draftBtn = d.querySelector('[data-act="draft"]');
  if (draftBtn) draftBtn.onclick = () => draftReply(e.email_id, draftBtn);
  const form = $("#correct-form");
  if (localStorage.getItem("reviewer")) form.reviewer.value = localStorage.getItem("reviewer");
  form.onsubmit = (ev) => {
    ev.preventDefault();
    const fd = new FormData(form);
    if (fd.get("reviewer")) localStorage.setItem("reviewer", fd.get("reviewer"));
    saveReview(e.email_id, { action: "correct", category: fd.get("category"), status: fd.get("status"),
      defect_fields: fd.getAll("df"), note: fd.get("note") || null, reviewer: fd.get("reviewer") || null });
  };
}

async function saveReview(id, body) {
  try { renderDetail(await api(`/api/emails/${id}/review`, { method: "POST", body: JSON.stringify(body) })); await refresh(); }
  catch (err) { alert("Could not save: " + err.message); }
}

async function draftReply(id, btn) {
  btn.disabled = true; btn.textContent = "Writing…";
  try {
    const d = await api(`/api/emails/${id}/draft-reply`, { method: "POST" });
    showModal(`<h2 style="margin-top:0">Email to the shipping line</h2>
      <p class="muted">${d.generated_by === "ai" ? "Written by AI" : "Written from a template"} — edit before sending.</p>
      <label style="font-weight:600">Subject <input id="dr-subj" style="width:100%;padding:8px;border:1px solid var(--line);border-radius:8px" value="${esc(d.subject)}"></label>
      <p><textarea id="dr-body">${esc(d.body)}</textarea></p>
      <button class="btn btn-primary" id="dr-copy">Copy to clipboard</button>`);
    $("#dr-copy").onclick = () => { navigator.clipboard.writeText($("#dr-subj").value + "\n\n" + $("#dr-body").value); $("#dr-copy").textContent = "Copied ✓"; };
  } catch (err) { alert(err.message); }
  btn.disabled = false; btn.textContent = "✉ Write email to shipping line";
}

function showModal(html) { $("#modal-body").innerHTML = html; $("#modal").hidden = false; }
$("#modal").addEventListener("click", (e) => { if (e.target.id === "modal" || e.target.classList.contains("modal-close")) $("#modal").hidden = true; });

// ---------------------------------------------------------------- new email
const EXAMPLES = {
  malay: { sender: "ops@pelanggan.com.my", subject: "Semakan draf BL untuk OC 5RSG-00133",
    body: "Salam,\n\nDilampirkan arahan penghantaran dan draf bil muatan untuk OC 5RSG-00133. Sila semak draf bil muatan dan sahkan bahawa butirannya sepadan dengan arahan penghantaran. Maklumkan jika ada percanggahan.\n\nTerima kasih." },
  chinese: { sender: "operations@customer.cn", subject: "请审核提单草稿 OC 5RSG-00133",
    body: "您好，\n\n附件中是装运指示和提单草稿。请比较提单和装运指示，并确认所有信息是否相符。如有差异，请告知。\n\n谢谢。" },
  invoice: { sender: "finance@customer.com", subject: "Question about our last bill",
    body: "Hi team,\n\nWe were charged twice for port handling on invoice 5250071354. Could you check and send a corrected bill?\n\nThanks" },
  spam: { sender: "rewards@lucky-winner.biz", subject: "You are our lucky shipper!", body: "Congratulations! You have won a free container. Claim your prize now at http://free-container.win" },
};
document.querySelectorAll("[data-example]").forEach((b) => b.addEventListener("click", () => {
  const ex = EXAMPLES[b.dataset.example]; const f = $("#new-form");
  f.sender.value = ex.sender; f.subject.value = ex.subject; f.body.value = ex.body;
}));
$("#new-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const f = ev.target; const btn = f.querySelector("button[type=submit]");
  btn.disabled = true; $("#new-status").textContent = "Checking…";
  try {
    const files = await Promise.all([...f.files.files].map((file) => new Promise((res, rej) => {
      const r = new FileReader(); r.onload = () => res({ name: file.name, content_b64: r.result.split(",")[1] }); r.onerror = rej; r.readAsDataURL(file);
    })));
    const e = await api("/api/process", { method: "POST", body: JSON.stringify({ sender: f.sender.value, subject: f.subject.value, body: f.body.value, files }) });
    $("#new-status").textContent = "";
    location.hash = `#/inbox/${e.email_id}`;
  } catch (err) { $("#new-status").textContent = "Failed: " + err.message; }
  btn.disabled = false;
});

// ---------------------------------------------------------------- how it works
function renderHow() {
  const s = state.summary || {}; const c = state.cfg;
  const by = s.decided_by || {}; const tot = s.total || 1;
  const mf = Object.entries(s.mismatch_fields || {}).sort((a, b) => b[1] - a[1]);
  const max = Math.max(1, ...mf.map((x) => x[1]));
  const v = s.validation;
  $("#view-how").innerHTML = `
    <p style="margin-top:0">Every email goes through the same steps. Simple, clear cases are handled by fast rules. The AI is used only where it helps: unclear emails and unfamiliar labels. <b>When the system isn't sure, it asks a person instead of guessing.</b></p>
    <div class="how-flow">
      <div class="how-step"><span class="num">1</span><b>Sort</b>What kind of email is it? Check BL, new SI, invoice, general or spam.</div>
      <div class="how-step"><span class="num">2</span><b>Read</b>Open the attachments (txt, PDF, Word, Excel) and find the 7 fields.</div>
      <div class="how-step"><span class="num">3</span><b>Compare</b>Check the draft BL against the Shipping Instruction, field by field.</div>
      <div class="how-step"><span class="num">4</span><b>Ask a person</b>Missing file, wrong document, blank field or unreadable scan → sent to a person with the reason.</div>
    </div>
    <h3>Right now</h3>
    <p>Handled automatically: <b>${s.auto_pct}%</b> of emails. Estimated staff time saved: <b>≈${Math.round((s.minutes_saved || 0) / 60)} hours</b>.</p>
    <p>AI model: <b>${c.ai ? esc(c.ai_model) + " (" + esc(c.ai_provider) + ")" : "off — running on rules only"}</b> · Storage: <b>${esc(c.store)}</b></p>
    <div class="bars">
      ${[["Sorted by rules", by.rule || 0], ["Sorted by AI", by.llm || 0], ["Not sure (asked a person)", by.rule_low_confidence || 0]].map(([l, n]) =>
        `<div class="bar"><span>${l}</span><div class="track"><div class="fill" style="width:${(100 * n / tot).toFixed(1)}%"></div></div><span>${n}</span></div>`).join("")}
    </div>
    ${mf.length ? `<h3>Most common BL mistakes</h3><div class="bars">${mf.map(([k, n]) =>
      `<div class="bar"><span>${esc(c.fields[k])}</span><div class="track"><div class="fill" style="width:${100 * n / max}%;background:var(--bad)"></div></div><span>${n}</span></div>`).join("")}</div>` : ""}
    ${v ? `<h3>Accuracy on the organisers' test set</h3><p>Score <b>${(v.final_score * 100).toFixed(1)}%</b> · sorting ${(v.stage1.accuracy * 100).toFixed(1)}% · mistakes caught ${v.end_to_end.success}/${v.end_to_end.total} · asked a person on ${v.reliability.pred_review} emails (needed: ${v.reliability.gold_review})</p>` : ""}
    <p><a href="/api/submission">Download results (organisers' format)</a></p>`;
}

// ---------------------------------------------------------------- routing
async function refresh() { await Promise.all([loadStats(), state.view === "inbox" || state.view === "queue" ? loadList() : null]); }

const HEADS = {
  inbox: ["Operations", "Inbox", "Every email sorted. Every draft BL checked against its Shipping Instruction."],
  queue: ["Human check", "Needs a person", "Cases the system couldn't decide on its own, each with the reason and the evidence."],
  new: ["Try it live", "Check your own email", "Paste an email, attach a Shipping Instruction and a draft Bill of Lading, and see the result in seconds."],
  how: ["About", "How it works", "Fast rules for the clear cases, AI for the unclear ones, and a person whenever it isn't sure."],
};

async function route() {
  const [, view = "inbox", id] = location.hash.split("/");
  state.view = ["inbox", "queue", "new", "how"].includes(view) ? view : "inbox";
  document.querySelectorAll(".tabs a").forEach((a) => a.classList.toggle("active", a.dataset.tab === state.view));
  const [eb, ti, sub] = HEADS[state.view];
  $("#eyebrow").textContent = eb; $("#page-title").textContent = ti; $("#page-sub").textContent = sub;
  $("#stats").hidden = !(state.view === "inbox" || state.view === "queue");
  $("#view-list").hidden = !(state.view === "inbox" || state.view === "queue");
  $("#view-new").hidden = state.view !== "new";
  $("#view-how").hidden = state.view !== "how";
  if (state.view === "inbox" || state.view === "queue") {
    await loadList();
    if (id) await openEmail(decodeURIComponent(id));
    else if (state.rows[0] && !state.rows.some((row) => row.email_id === state.sel)) {
      await openEmail(state.rows[0].email_id);
    }
  }
  if (state.view === "how") { await loadStats(); renderHow(); }
}

async function init() {
  state.cfg = await api("/api/config");
  $("#app-name").textContent = state.cfg.app_name; document.title = state.cfg.app_name;
  $("#ai-status").textContent = state.cfg.ai ? `AI · ${state.cfg.ai_model}` : "Rules only";
  $("#ai-status").classList.toggle("off", !state.cfg.ai);
  chips();
  $("#cat-chips").addEventListener("click", (e) => { if (!e.target.dataset) return; if ("cat" in e.target.dataset) { state.cat = e.target.dataset.cat || null; chips(); loadList(); } });
  $("#status-chips").addEventListener("click", (e) => {
    const d = e.target.dataset || {};
    if ("ai" in d) { state.ai = !state.ai; chips(); loadList(); }
    else if ("status" in d) { state.status = d.status || null; chips(); loadList(); }
  });
  let t; $("#search").addEventListener("input", (e) => { clearTimeout(t); t = setTimeout(() => { state.q = e.target.value.trim(); loadList(); }, 200); });
  $("#list").addEventListener("click", (e) => { const r = e.target.closest(".row"); if (r) { state.userClicked = true; openEmail(r.dataset.id); } });
  const closeNav = () => { document.body.classList.remove("nav-open"); $("#scrim").hidden = true; };
  $("#menu-btn").addEventListener("click", () => { document.body.classList.add("nav-open"); $("#scrim").hidden = false; });
  $("#scrim").addEventListener("click", closeNav);
  document.querySelectorAll(".sidebar a").forEach((a) => a.addEventListener("click", closeNav));
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") { closeNav(); $("#modal").hidden = true; } });
  window.addEventListener("hashchange", route);
  await loadStats();
  await route();
}
init().catch((e) => { document.body.insertAdjacentHTML("afterbegin", `<div class="banner bad">Could not load: ${esc(e.message)}</div>`); });
