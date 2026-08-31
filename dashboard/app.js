"use strict";

/* Static dashboard: reads jobs.json + applications.json and renders them.
 * No backend. Works both when the dashboard is a subfolder (../data/...) and
 * when it is deployed at the repo root (data/...). */

const DATA_CANDIDATES = ["../data/", "data/", "./data/"];

const state = {
  jobs: [],
  applications: [],
  view: "applications",
  search: "",
  status: "",
  sort: "recent",
  dataBase: null,
  updatedAt: null,
};

async function findDataBase() {
  for (const base of DATA_CANDIDATES) {
    try {
      const res = await fetch(base + "applications.json", { cache: "no-store" });
      if (res.ok) return base;
    } catch (_) { /* try next */ }
  }
  return null;
}

async function loadData() {
  const listEl = document.querySelector("#list");
  state.dataBase = state.dataBase || (await findDataBase());
  if (!state.dataBase) {
    listEl.innerHTML =
      '<div class="error">Could not locate data/applications.json. ' +
      "Serve the repo root (e.g. <code>python -m app.main dashboard</code>).</div>";
    return;
  }
  try {
    const [appsRes, jobsRes] = await Promise.all([
      fetch(state.dataBase + "applications.json", { cache: "no-store" }),
      fetch(state.dataBase + "jobs.json", { cache: "no-store" }),
    ]);
    const apps = await appsRes.json();
    const jobs = jobsRes.ok ? await jobsRes.json() : { jobs: [] };
    state.applications = apps.applications || [];
    state.jobs = jobs.jobs || [];
    state.updatedAt = appsRes.headers.get("last-modified");
    render();
  } catch (err) {
    listEl.innerHTML = '<div class="error">Failed to parse data: ' + esc(String(err)) + "</div>";
  }
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function renderStats() {
  const apps = state.applications;
  const count = (s) => apps.filter((a) => a.status === s).length;
  const cells = [
    ["Total", apps.length],
    ["Applied", count("APPLIED")],
    ["OA / Interview", count("OA") + count("INTERVIEW")],
    ["Offers", count("OFFER")],
    ["Queue", state.jobs.filter((j) => j.status === "QUEUED").length],
  ];
  document.querySelector("#stats").innerHTML = cells
    .map(([l, n]) => `<div><span class="l">${l}</span><span class="n">${n}</span></div>`)
    .join("");
}

function matchesFilter(name, role, status) {
  const q = state.search.toLowerCase();
  if (q && !(`${name} ${role}`.toLowerCase().includes(q))) return false;
  if (state.status && status !== state.status) return false;
  return true;
}

function sortItems(items, keyFns) {
  const { score, company, recent } = keyFns;
  const s = state.sort;
  return [...items].sort((a, b) => {
    if (s === "score") return (score(b) ?? -1) - (score(a) ?? -1);
    if (s === "company") return company(a).localeCompare(company(b));
    return String(recent(b) || "").localeCompare(String(recent(a) || ""));
  });
}

function appCard(a) {
  const badges = [
    `<span class="badge s-${esc(a.status)}">${esc(a.status)}</span>`,
    a.match_score != null ? `<span class="badge score">${a.match_score}</span>` : "",
    a.resume ? `<span class="badge">${esc(a.resume)}</span>` : "",
    a.date_applied ? `<span class="badge">${esc(a.date_applied)}</span>` : "",
  ].join("");

  const needsHuman = (a.notes || "").toLowerCase().includes("needs human")
    ? '<span class="badge review">needs human</span>' : "";

  const qa = (a.questions || [])
    .map((q) => `<div class="qa"><b>${esc(q.question)}</b><br>${esc(q.answer)}</div>`)
    .join("");

  return `<article class="card">
    <h3>${esc(a.role)}</h3>
    <div class="sub">${esc(a.company)}</div>
    <div class="row">${badges}${needsHuman}
      ${a.application_url ? `<a href="${esc(a.application_url)}" target="_blank" rel="noopener">Open form ↗</a>` : ""}
    </div>
    ${a.notes ? `<div class="reason">${esc(a.notes)}</div>` : ""}
    ${qa ? `<details><summary>${(a.questions || []).length} answer(s)</summary>${qa}</details>` : ""}
  </article>`;
}

function jobCard(j) {
  const badges = [
    `<span class="badge s-${esc(j.status)}">${esc(j.status)}</span>`,
    j.match_score != null ? `<span class="badge score">${j.match_score}</span>` : "",
    j.recommendation ? `<span class="badge">${esc(j.recommendation)}</span>` : "",
    j.source ? `<span class="badge">${esc(j.source)}</span>` : "",
    j.requires_human_review ? '<span class="badge review">review</span>' : "",
  ].join("");

  const skills = (j.matching_skills || []).slice(0, 8).join(", ");
  return `<article class="card">
    <h3>${esc(j.title)}</h3>
    <div class="sub">${esc(j.company)}${j.location ? " · " + esc(j.location) : ""}</div>
    <div class="row">${badges}
      ${j.url ? `<a href="${esc(j.url)}" target="_blank" rel="noopener">Posting ↗</a>` : ""}
    </div>
    ${j.reason ? `<div class="reason">${esc(j.reason)}</div>` : ""}
    ${skills ? `<div class="reason">Matches: ${esc(skills)}</div>` : ""}
  </article>`;
}

function render() {
  renderStats();
  const listEl = document.querySelector("#list");
  let html = "";
  let items = [];

  if (state.view === "applications") {
    items = state.applications.filter((a) => matchesFilter(a.company, a.role, a.status));
    items = sortItems(items, {
      score: (a) => a.match_score,
      company: (a) => a.company || "",
      recent: (a) => a.updated_at || a.created_at,
    });
    html = items.map(appCard).join("");
  } else {
    let jobs = state.jobs;
    if (state.view === "queue") jobs = jobs.filter((j) => j.status === "QUEUED");
    items = jobs.filter((j) => matchesFilter(j.company, j.title, j.status));
    items = sortItems(items, {
      score: (j) => j.match_score,
      company: (j) => j.company || "",
      recent: (j) => j.analyzed_at || j.discovered_at,
    });
    html = items.map(jobCard).join("");
  }

  listEl.innerHTML = html || '<div class="empty">Nothing to show.</div>';
  document.querySelector("#meta").textContent =
    `${items.length} item(s)` + (state.updatedAt ? ` · data updated ${state.updatedAt}` : "");
}

function wire() {
  document.querySelector("#search").addEventListener("input", (e) => {
    state.search = e.target.value; render();
  });
  document.querySelector("#status").addEventListener("change", (e) => {
    state.status = e.target.value; render();
  });
  document.querySelector("#sort").addEventListener("change", (e) => {
    state.sort = e.target.value; render();
  });
  document.querySelector("#refresh").addEventListener("click", loadData);
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");
      state.view = tab.dataset.view;
      render();
    });
  });
}

wire();
loadData();
