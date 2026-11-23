// Renders the Living Map from a map.json the way index.html does, and prints every
// HTML string the page assigns to innerHTML, as a JSON array. Used by
// tests/test_hostile_manifests.py. Run: node tests/render_page.js <map.json>
//
// hash.js and app.js run unchanged in a vm context with a stub DOM that only records
// innerHTML writes. The page is driven through its main view, every filter chip, every
// island and every agent's detail panel (opened by #agent= deep link, as a visitor would).
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const ROOT = path.resolve(__dirname, "..");
const map = JSON.parse(fs.readFileSync(process.argv[2], "utf-8"));
const written = [];

function element() {
  let html = "";
  const attrs = {};
  return {
    get innerHTML() { return html; },
    set innerHTML(v) { html = String(v); written.push(html); },
    textContent: "", title: "",
    classList: { add() {}, remove() {} },
    setAttribute(k, v) { attrs[k] = String(v); },
    getAttribute(k) { return k in attrs ? attrs[k] : null; },
    addEventListener() {},
    getBoundingClientRect() { return { top: 0, bottom: 0 }; },
    scrollIntoView() {},
  };
}

const elements = {};
const location = { hash: "", pathname: "/", search: "" };
const ctx = {
  console,
  location,
  history: { replaceState(_s, _t, url) { location.hash = url.slice(url.indexOf("#")) || ""; } },
  localStorage: { getItem() { return null; }, setItem() {} },
  matchMedia() { return { matches: false }; },
  addEventListener() {},
  CSS: { escape: s => String(s).replace(/["\\]/g, "\\$&") },
  fetch: () => Promise.resolve({ json: () => Promise.resolve(map) }),
  document: {
    documentElement: element(),
    getElementById: id => elements[id] || (elements[id] = element()),
    querySelector: () => null,
    addEventListener() {},
  },
};
ctx.window = ctx;
ctx.globalThis = ctx;
vm.createContext(ctx);
for (const f of ["theme-init.js", "hash.js", "app.js"]) {
  vm.runInContext(fs.readFileSync(path.join(ROOT, f), "utf-8"), ctx, { filename: f });
}

setImmediate(() => {
  const run = code => vm.runInContext(code, ctx);
  if (!run("data")) throw new Error("map.json did not load");
  const go = target => { location.hash = run(`formatHash(${JSON.stringify(target)})`); run("applyHash()"); };
  for (const m of map.maturity_levels) run(`filter.maturity = ${JSON.stringify(m.key)}; render()`);
  run(`filter = {q:"", maturity:null, issues:true, slots:true}; render()`);
  run(`filter = {q:"", maturity:null, issues:false, slots:false}; render()`);
  for (const i of map.islands) go({ island: i.id });
  for (const a of map.agents) go({ agent: a.repo });
  go({});
  process.stdout.write(JSON.stringify(written));
});
