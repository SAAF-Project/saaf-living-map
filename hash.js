// Deep links for the Living Map: #island=<id> opens the map on an island,
// #agent=<owner/repo> opens an agent. Pure functions, no DOM: index.html loads
// this as a plain script and tests/test_hash.js loads it as a CommonJS module.
(function (root) {
  "use strict";

  // parseHash("#agent=SAAF-Project%2FRCM-Builder") -> {agent: "SAAF-Project/RCM-Builder"}
  // parseHash("#island=planning")                   -> {island: "planning"}
  // Anything else (no hash, unknown key, empty value, bad encoding) -> {}.
  // The value may be URL-encoded or not; a bare slash in a repo is fine.
  function parseHash(hash) {
    let s = String(hash == null ? "" : hash).trim();
    if (s.charAt(0) === "#") s = s.slice(1);
    if (s.charAt(0) === "/") s = s.slice(1);          // tolerate "#/agent=..."
    const eq = s.indexOf("=");
    if (eq < 0) return {};
    const key = s.slice(0, eq).trim().toLowerCase();
    if (key !== "island" && key !== "agent") return {};
    let value = s.slice(eq + 1).split("&")[0];
    try { value = decodeURIComponent(value); } catch (e) { return {}; }
    value = value.trim().replace(/^\/+|\/+$/g, "");
    if (!value) return {};
    return key === "island" ? { island: value } : { agent: value };
  }

  // formatHash({island: "planning"})                  -> "#island=planning"
  // formatHash({agent: "SAAF-Project/RCM-Builder"})   -> "#agent=SAAF-Project%2FRCM-Builder"
  // formatHash({}) -> ""   (the page is addressed with no fragment)
  function formatHash(target) {
    if (target && target.agent) return "#agent=" + encodeURIComponent(target.agent);
    if (target && target.island) return "#island=" + encodeURIComponent(target.island);
    return "";
  }

  const api = { parseHash, formatHash };
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.LivingMapHash = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
