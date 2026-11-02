// Tests for hash.js. Run: node --test tests/test_hash.js
const test = require("node:test");
const assert = require("node:assert/strict");
const { parseHash, formatHash } = require("../hash.js");

test("island links", () => {
  assert.deepEqual(parseHash("#island=planning"), { island: "planning" });
  assert.deepEqual(parseHash("island=quarry"), { island: "quarry" });
  assert.deepEqual(parseHash("#Island=Governance"), { island: "Governance" });
});

test("agent links, encoded or not", () => {
  assert.deepEqual(parseHash("#agent=SAAF-Project/RCM-Builder"), { agent: "SAAF-Project/RCM-Builder" });
  assert.deepEqual(parseHash("#agent=SAAF-Project%2FRCM-Builder"), { agent: "SAAF-Project/RCM-Builder" });
  assert.deepEqual(parseHash("#/agent=SAAF-Project/RCM-Builder"), { agent: "SAAF-Project/RCM-Builder" });
  assert.deepEqual(parseHash("#agent=/SAAF-Project/RCM-Builder/"), { agent: "SAAF-Project/RCM-Builder" });
  assert.deepEqual(parseHash("#agent=SAAF-Project/RCM-Builder&x=1"), { agent: "SAAF-Project/RCM-Builder" });
});

test("anything else is an empty target", () => {
  for (const h of ["", "#", "#foo", "#foo=bar", "#island=", "#agent=%2F", "#agent=%E0%A4%A", null, undefined]) {
    assert.deepEqual(parseHash(h), {}, JSON.stringify(h));
  }
});

test("formatHash writes URL-encoded links and round-trips", () => {
  assert.equal(formatHash({ agent: "SAAF-Project/RCM-Builder" }), "#agent=SAAF-Project%2FRCM-Builder");
  assert.equal(formatHash({ island: "planning" }), "#island=planning");
  assert.equal(formatHash({}), "");
  assert.equal(formatHash(null), "");
  for (const t of [{ agent: "SAAF-Project/RCM-Builder" }, { island: "foundation" }]) {
    assert.deepEqual(parseHash(formatHash(t)), t);
  }
});
