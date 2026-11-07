const MCOL = ["var(--m0)","var(--m1)","var(--m2)","var(--m3)"];
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
let data, filter = {q:"", maturity:null, issues:false, slots:false}, selected = null, targetIsland = null;
const {parseHash, formatHash} = LivingMapHash;

// Islands and maturity levels are {id|key, label}; plain strings are the older map.json shape.
const norm = (xs, k) => (xs||[]).map(x => typeof x === "string" ? {[k]:x, label:x} : x);
fetch("map.json", {cache:"no-store"}).then(r => r.json()).then(d => {
  data = d; data.islands = norm(d.islands, "id"); data.maturity_levels = norm(d.maturity_levels, "key"); render(); applyHash(); })
  .catch(e => document.getElementById("islands").innerHTML = `<p class="empty">Could not load map.json (${esc(e)}).</p>`);

function mindex(m){ return data.maturity_levels.findIndex(l => l.key === m); }
function mcolor(m){ const i = mindex(m); return i < 0 ? "var(--m0)" : MCOL[i]; }
function mlabel(m){ return data.maturity_levels[mindex(m)]?.label ?? m; }
function ilabel(i){ return data.islands.find(l => l.id === i)?.label ?? i; }
function byRepo(r){ return data.agents.find(a => a.repo === r); }
function byRepoLoose(r){ const k = String(r).toLowerCase(); return byRepo(r) || data.agents.find(a => a.repo.toLowerCase() === k); }

function render(){
  const s = data.summary;
  document.getElementById("stats").innerHTML = [
    [s.mapped, "agents mapped"], [s.unmapped, "repos not yet mapped"],
    [s.confirmed ?? 0, "with their own agent.yaml"],
    [s.open_slots, "open team slots"],
    [s.with_warnings, "with warnings"]
  ].map(([n,l]) => `<div class="stat"><b>${n}</b><span>${l}</span></div>`).join("");
  const tot = s.mapped || 1;
  document.getElementById("pipe").innerHTML = data.maturity_levels
    .map((m,i) => `<i style="width:${100*(s.by_maturity[m.key]||0)/tot}%;background:${MCOL[i]}"></i>`).join("");
  document.getElementById("legend").innerHTML = data.maturity_levels
    .map((m,i) => `<span><span class="dot" style="background:${MCOL[i]}"></span>${esc(m.label)} · ${s.by_maturity[m.key]||0}</span>`).join("");
  document.getElementById("chips").innerHTML =
    data.maturity_levels.map(m => `<button class="chip" data-m="${esc(m.key)}" aria-pressed="${filter.maturity===m.key}">${esc(m.label)}</button>`).join(" ") +
    ` <button class="chip" data-f="slots" aria-pressed="${filter.slots}">Open slots</button>` +
    ` <button class="chip" data-f="issues" aria-pressed="${filter.issues}">Warnings</button>`;
  drawIslands();
  document.getElementById("foot").innerHTML =
    `Last changed ${esc(new Date(data.generated_at).toLocaleString())}. Add your agent: put an <code>agent.yaml</code> in its repo and add the repo to <code>repos.txt</code>.`;
}

function matches(a){
  if (filter.maturity && a.maturity !== filter.maturity) return false;
  if (filter.slots && !(a.open_slots > 0)) return false;
  if (filter.issues && !(a.warnings||[]).length) return false;
  if (filter.q){
    const hay = [a.name,a.repo,a.description,a.category,a.language,...(a.tags||[])].join(" ").toLowerCase();
    if (!hay.includes(filter.q)) return false;
  }
  return true;
}

function card(a){
  const ghost = a.status !== "mapped";
  const rel = selected && (selected.repo === a.repo || (selected.depends_on||[]).includes(a.repo) || (selected.used_by||[]).includes(a.repo));
  const cls = ["card", ghost?"ghost":"", !matches(a)?"dim":"", rel?"hl":""].join(" ");
  const meta = ghost ? esc(a.repo) :
    [a.maturity && mlabel(a.maturity), a.category, a.language, a.open_slots>0 ? `${a.open_slots} open slot${a.open_slots>1?"s":""}` : null].filter(Boolean).map(esc).join(" · ");
  const badges = (a.warnings?.length && !ghost ? `<span class="badge w" title="${esc(a.warnings.join("\n"))}">${a.warnings.length} issue${a.warnings.length>1?"s":""}</span>` : "") +
    (!ghost && a.confirmed === false ? `<span class="badge s" title="Seed drafted from the portal; the repo has no agent.yaml of its own yet">unconfirmed</span>` : "") + (ghost ? `<span class="badge s">not mapped</span>` : "");
  return `<button class="${cls}" data-repo="${esc(a.repo)}" style="border-left-color:${ghost?"var(--line)":mcolor(a.maturity)}">
    <div class="t">${esc(a.name)}${badges}</div><div class="meta">${meta}</div></button>`;
}

function drawIslands(){
  const groups = data.islands.map(i => [i.id, i.label, data.agents.filter(a => a.status==="mapped" && a.island===i.id)]);
  const other = data.agents.filter(a => a.status==="mapped" && !data.islands.some(i => i.id===a.island));
  if (other.length) groups.push([null, "Other", other]);
  const ghosts = data.agents.filter(a => a.status!=="mapped");
  if (ghosts.length) groups.push([null, "Not yet mapped", ghosts]);
  document.getElementById("islands").innerHTML = groups.map(([id, name, list]) =>
    `<div class="island${id && id===targetIsland ? " target" : ""}"${id ? ` id="island-${esc(id)}"` : ""}><h2>${
      id ? `<a href="${esc(formatHash({island:id}))}">${esc(name)}</a>` : esc(name)}<small>${list.length}</small></h2>${
      list.length ? list.map(card).join("") : `<p class="empty">No agents yet — a gap worth a hackathon track.</p>`}</div>`).join("");
}

function showDetail(a){
  selected = a; drawIslands();
  const d = document.getElementById("detail");
  const pills = (xs, no) => (xs||[]).map(x => `<span class="pill${no?" no":""}">${esc(x)}</span>`).join("") || "—";
  const links = xs => (xs||[]).length ? xs.map(r => `<button class="link" data-repo="${esc(r)}">${esc(byRepo(r)?.name || r)}</button>`).join(", ") : "—";
  const noMandate = (a.warnings||[]).includes("no mandate block");
  d.innerHTML = `<button class="close" aria-label="Close">×</button>
    <h3>${esc(a.name)}</h3>
    <a href="https://github.com/${esc(a.repo)}" target="_blank" rel="noopener">${esc(a.repo)}</a>
    ${a.status==="mapped" ? `<p>${esc(a.description)}</p>
    <dl><dt>Island</dt><dd>${esc(ilabel(a.island))}</dd>
      <dt>Maturity</dt><dd><span class="dot" style="background:${mcolor(a.maturity)}"></span>${esc(mlabel(a.maturity))}</dd>
      <dt>Category</dt><dd>${esc(a.category||"—")}</dd><dt>Language</dt><dd>${esc(a.language||"—")}</dd>
      <dt>Open slots</dt><dd>${esc(a.open_slots ?? 0)}</dd><dt>Tags</dt><dd>${pills(a.tags)}</dd>
      <dt>Depends on</dt><dd>${links(a.depends_on)}</dd><dt>Used by</dt><dd>${links(a.used_by)}</dd>
      <dt>Source</dt><dd>${a.source_kind==="seed" ? "seed manifest in this repo, drafted from the portal" : "agent.yaml in agent repo"}</dd>
      <dt>Confirmed</dt><dd>${a.confirmed === false ? "no: seed manifest, the repo has no agent.yaml of its own yet" : "yes, has its own agent.yaml"}</dd></dl>
    <h4>Mandate</h4>
    ${a.has_mandate ? `<p>Declared; all mandate checks pass.</p>`
      : noMandate ? `<p class="empty">No mandate declared.</p>`
      : `<p>Declared, with issues (see Checks).</p>`}`
    : `<p class="empty">This repo has no agent.yaml yet.</p><dl><dt>Used by</dt><dd>${links(a.used_by)}</dd></dl>`}
    <h4>Checks</h4>
    ${(a.warnings||[]).length ? `<ul class="warns">${a.warnings.map(w=>`<li>${esc(w)}</li>`).join("")}</ul>` : `<p>All checks pass.</p>`}`;
  d.classList.add("open");
}

function closeDetail(){ document.getElementById("detail").classList.remove("open"); selected = null; drawIslands(); }

// Deep links. The hash is the source of truth: clicks write it (replaceState, so the
// back button still leaves the page), applyHash() reads it on load and whenever it changes.
// The hash is visitor-controlled: it is only ever used to look up an island or agent in
// map.json, and an unknown value does nothing. Only the looked-up ids reach the DOM.
function setHash(h){
  if (location.hash === h || (!h && !location.hash)) return;
  history.replaceState(null, "", location.pathname + location.search + h);
  applyHash();
}
function applyHash(){
  if (!data) return;
  const t = parseHash(location.hash);
  const a = t.agent ? byRepoLoose(t.agent) : null;
  const island = t.island ? data.islands.find(i => i.id === t.island) : null;
  targetIsland = island ? island.id : null;
  if (a) showDetail(a); else closeDetail();
  const el = a ? document.querySelector(`.card[data-repo="${CSS.escape(a.repo)}"]`)
           : island ? document.getElementById(`island-${island.id}`) : null;
  if (!el) return;
  const r = el.getBoundingClientRect();
  if (r.top < 0 || r.bottom > window.innerHeight) el.scrollIntoView({block: a ? "center" : "start"});
}
window.addEventListener("hashchange", applyHash);

document.addEventListener("click", e => {
  const c = e.target.closest("[data-repo]");
  if (c){ const a = byRepo(c.dataset.repo); if (a) setHash(formatHash({agent: a.repo})); return; }
  if (e.target.closest(".close")){ setHash(""); return; }
  const il = e.target.closest(".island h2 a");
  if (il){ e.preventDefault(); setHash(il.getAttribute("href")); return; }
  const chip = e.target.closest(".chip");
  if (chip){
    if (chip.dataset.m) filter.maturity = filter.maturity===chip.dataset.m ? null : chip.dataset.m;
    if (chip.dataset.f) filter[chip.dataset.f] = !filter[chip.dataset.f];
    render();
  }
});
document.addEventListener("keydown", e => { if (e.key==="Escape" && selected) setHash(""); });
document.getElementById("q").addEventListener("input", e => { filter.q = e.target.value.trim().toLowerCase(); drawIslands(); });

// Theme toggle, as in the portal: flips data-theme and remembers the choice.
const themeBtn = document.getElementById("theme");
function drawTheme(){
  const light = document.documentElement.getAttribute("data-theme") === "light";
  const label = light ? "Switch to dark mode" : "Switch to light mode";
  themeBtn.textContent = light ? "☾" : "☀"; themeBtn.title = label; themeBtn.setAttribute("aria-label", label);
}
themeBtn.addEventListener("click", () => {
  const next = document.documentElement.getAttribute("data-theme") === "light" ? "dark" : "light";
  document.documentElement.setAttribute("data-theme", next);
  try { localStorage.setItem("theme", next); } catch {}
  drawTheme();
});
drawTheme();
