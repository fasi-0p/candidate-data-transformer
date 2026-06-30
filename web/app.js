"use strict";
// Minimal client for the transformation engine. No framework — the UI's only
// job is to render the engine's explainability (provenance, confidence,
// conflicts) and re-project without re-running.

let lastRunId = null;

const $ = (id) => document.getElementById(id);

async function loadProjections() {
  const data = await (await fetch("/api/projections")).json();
  const sel = $("projection");
  sel.innerHTML = "";
  for (const p of data.projections) {
    const opt = document.createElement("option");
    opt.value = p.id;
    opt.textContent = p.name;
    sel.appendChild(opt);
  }
}

async function run() {
  const form = new FormData();
  for (const f of $("csv").files) form.append("csv", f);
  for (const f of $("resume").files) form.append("resume", f);
  for (const f of $("ats").files) form.append("ats", f);
  for (const f of $("notes").files) form.append("notes", f);
  const github = $("github").value.trim();
  const linkedin = $("linkedin").value.trim();
  if (github) form.append("github", github);
  if (linkedin) form.append("linkedin", linkedin);  // verify id, not a source
  if (!$("csv").files.length && !$("resume").files.length && !$("ats").files.length
      && !$("notes").files.length && !github) {
    $("status").textContent = "Choose at least one CSV, resume PDF, ATS JSON, recruiter notes, or GitHub URL.";
    return;
  }
  $("status").textContent = "Running…";
  $("run").disabled = true;
  try {
    const resp = await fetch("/api/run", { method: "POST", body: form });
    if (!resp.ok) throw new Error((await resp.json()).detail || resp.statusText);
    const data = await resp.json();
    lastRunId = data.run_id;
    renderStats(data);
    renderCandidates(data.candidates, data.validation);
    $("apply").disabled = false;
    $("status").textContent = "Done.";
  } catch (e) {
    $("status").textContent = "Error: " + e.message;
  } finally {
    $("run").disabled = false;
  }
}

function renderStats(data) {
  const t = data.timings_ms || {};
  const order = ["extract", "normalize", "resolve", "merge", "validate"];
  const timings = order
    .filter((k) => k in t)
    .map((k) => `${k} ${t[k].toFixed(1)}ms`)
    .join(" · ");
  const s = data.stats || {};
  $("stats").textContent =
    `${s.records_in} records → ${s.clusters_out} candidates · ` +
    `${s.conflicts_found} conflicts · ${timings}`;
}

// --- candidate rendering -----------------------------------------------------

function confBar(conf) {
  const pct = Math.round(conf * 100);
  const cls = conf >= 0.9 ? "hi" : conf >= 0.75 ? "mid" : "lo";
  return `<span class="conf ${cls}"><span class="track">` +
    `<span class="fill" style="width:${pct}%"></span></span>` +
    `<span class="num">${conf.toFixed(2)}</span></span>`;
}

function fmtValue(v) {
  if (v === null || v === undefined) return '<span class="muted">—</span>';
  if (typeof v === "object") {
    return escapeHtml(Object.entries(v).map(([k, val]) => `${k}: ${val}`).join(", "));
  }
  return escapeHtml(String(v));
}

function fmtEducation(v) {
  if (!v || typeof v !== "object") return fmtValue(v);
  const head = [v.degree, v.institution, v.field_of_study].filter(Boolean).join(", ");
  const dates = [v.start, v.end].filter(Boolean).join(" – ");
  if (!head && !dates) return '<span class="muted">—</span>';
  return escapeHtml(head) +
    (dates ? ` <span class="muted">(${escapeHtml(dates)})</span>` : "");
}

function field(label, tv, fmt = fmtValue) {
  if (!tv) {
    return `<div class="field"><summary><span class="label">${label}</span>` +
      `<span class="val muted">—</span><span class="src"></span></summary></div>`;
  }
  const detail = [];
  detail.push(`<div class="line"><span class="k">source</span>${escapeHtml(tv.source)} (${escapeHtml(tv.method)})</div>`);
  if (tv.sources && tv.sources.length > 1)
    detail.push(`<div class="line agree"><span class="k">agreed by</span>${tv.sources.map(escapeHtml).join(", ")}</div>`);
  if (tv.malformed)
    detail.push(`<div class="line warn"><span class="k">note</span>kept but could not be normalized</div>`);
  for (const c of tv.conflicts || [])
    detail.push(`<div class="line conflict"><span class="k">conflict</span>` +
      `${fmt(c.value)} from ${escapeHtml(c.source)} lost (${escapeHtml(c.reason)})</div>`);

  return `<details class="field">
    <summary>
      <span class="label">${label}</span>
      <span class="val">${fmt(tv.value)}${tv.conflicts && tv.conflicts.length ? '<span class="badge">conflict</span>' : ""}</span>
      <span class="src">${confBar(tv.confidence)}</span>
    </summary>
    <div class="detail">${detail.join("")}</div>
  </details>`;
}

function collection(label, arr, fmt = fmtValue) {
  if (!arr || !arr.length)
    return field(label, null);
  return arr.map((tv, i) => field(i === 0 ? label : "", tv, fmt)).join("");
}

function verifyBadge(rep) {
  // Only surface mismatches — a successful verify just shows up as raised
  // confidence, not a badge.
  const issues = (rep && rep.issues) || [];
  let out = "";
  for (const [code, label] of [["linkedin_mismatch", "LinkedIn ✗"],
                               ["github_mismatch", "GitHub ✗"]]) {
    const issue = issues.find((i) => i.code === code);
    if (issue)
      out += `<span class="badge warn" title="${escapeHtml(issue.message)}">${label}</span>`;
  }
  return null;
}

function renderCandidates(cands, reports) {
  const root = $("candidates");
  root.innerHTML = "";
  const reportById = {};
  for (const r of reports || []) reportById[r.candidate_id] = r;

  // Inspector lists candidates by descending overall confidence (highest first).
  // Stable id tiebreak keeps equal-confidence ordering deterministic.
  const ordered = [...cands].sort(
    (a, b) => (b.record_confidence - a.record_confidence)
      || a.candidate_id.localeCompare(b.candidate_id));

  for (const c of ordered) {
    const rep = reportById[c.candidate_id];
    const badge = rep && !rep.is_valid
      ? '<span class="badge warn">invalid</span>' : "";
    const el = document.createElement("div");
    el.className = "candidate";
    el.innerHTML =
      `<div class="head">
         <span class="name">${fmtValue(c.full_name && c.full_name.value)}</span>
         <span class="id">${escapeHtml(c.candidate_id)} · conf ${c.record_confidence}</span>
       </div>` +
      field("Headline", c.headline) +
      field("Location", c.location) +
      field("Experience (yrs)", c.years_experience) +
      collection("Emails", c.emails) +
      collection("Phones", c.phones) +
      collection("Skills", c.skills) +
      collection("Links", c.links) +
      collection("Education", c.education, fmtEducation);
    root.appendChild(el);
  }
}

// --- projection --------------------------------------------------------------

async function applyProjection() {
  if (!lastRunId) return;
  const body = { run_id: lastRunId, projection_id: $("projection").value };
  const resp = await fetch("/api/project", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await resp.json();
  $("output").textContent = JSON.stringify(
    resp.ok ? data.output : data, null, 2);
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

$("run").addEventListener("click", run);
$("apply").addEventListener("click", applyProjection);
loadProjections();
