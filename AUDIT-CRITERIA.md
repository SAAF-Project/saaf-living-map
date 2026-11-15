# `AUDIT-CRITERIA.md` — SAAF Living Map

> The README says *what the Living Map does and how to run it*; this document says *what it must be judged against as an auditee* — its control objectives, testable acceptance criteria, and known limits.
>
> SAAF standard 3 (A2 — Audit Criteria & Controls), following `docs/conventions/audit-criteria-template.md` in SAAF-Project. The Living Map is a shared service, not an audit agent: it makes no audit judgements, but it publishes claims about other agents (mapped, confirmed, mandate declared), so those claims must hold up.

---

## Metadata

| Field | Value |
|---|---|
| **Service** | SAAF Living Map |
| **Repository** | https://github.com/SAAF-Project/saaf-living-map |
| **Live map** | https://saaf-project.github.io/saaf-living-map/ |
| **Maintainer(s)** | Tony Barratt (@TonyBarratt100) |
| **Last reviewed** | 2026-11-15 |
| **Status** | Draft |

## 1. What the service does

The Living Map collects one manifest per SAAF agent repository and renders them as a public map. A scheduled GitHub Action (hourly) reads `repos.txt`, fetches each repository's own `agent.yaml`, or falls back to a seed manifest in `manifests/` drafted from the portal, checks every manifest against plain rules, and writes `map.json`, which `index.html` renders. There is **no LLM anywhere in the pipeline**: `scripts/build_map.py` is deterministic Python, and the page only reads `map.json`.

What it claims about each agent: its island and maturity (the portal's ids), its dependencies, whether it is **confirmed** (its owners added their own `agent.yaml`) and whether it **has a mandate** that passes every check. `map.json` is public; manifests may come from private repositories.

## 2. Control objectives & framework mapping (5)

| Control objective | Framework + clause/area | Why relevant |
|---|---|---|
| **CO-1 — The public map carries only allowlisted fields.** Anything else a manifest declares, including the mandate and any `owners`, is checked but never published. | GDPR Art. 5(1)(c) (data minimisation) / ISO 27001 A.5.12 (classification of information) | Manifests come from private repositories; `map.json` is public. Publishing more than the allowlist would leak private mandate content or personal data. |
| **CO-2 — Agent status is never overstated.** A seed manifest is unconfirmed by default; `has_mandate` is true only when the mandate block is present and passes every check. | IIA Standards (sufficiency and reliability of information) / COSO 2013 Principle 13 (relevant, quality information) | Readers use the map to decide which agents to trust and reuse. A "confirmed" or "mandate declared" badge that isn't earned gives false assurance. |
| **CO-3 — A declared mandate is checked for completeness.** It must forbid `change_own_config`, list trusted inputs, give a rationale per forbidden action, name an evidence policy and a human approval step, and (from Ready onward) a maximum runtime. | EU AI Act Art. 14 (human oversight) / OWASP LLM Top 10 — LLM06 Excessive Agency | The mandate is the agent's declared boundary. A mandate without approval steps or reasons is a boundary in name only. |
| **CO-4 — Island and maturity use only the portal's vocabulary.** Unknown ids, old labels and plan-only stages are flagged, not silently accepted. | COBIT BAI10 (configuration management) | The map and the portal must describe the same thing in the same terms; drift between them breaks the shared picture of SAAF. |
| **CO-5 — One bad manifest cannot stop or poison the whole map.** Invalid, hostile or oversized manifests become warnings on that agent; the build completes for everyone else. | ISO 27001 A.8.28 (secure coding) / OWASP (input validation) | Any repository owner can write a manifest. The service must treat every manifest as untrusted input. |

## 3. Acceptance criteria (testable, pass/fail)

**CO-1**
- Given a manifest with fields outside the allowlist (e.g. `owner_email`, `internal_notes`), the published entry contains none of them, and their names appear in the build log as dropped.
- Given a manifest with a valid mandate, the published entry contains no `mandate` key, only `has_mandate: true`, and the mandate is not reported as dropped.
- Warnings published in `map.json` count mandate items but never name them (no tool or action names).

**CO-2**
- Given a seed manifest with no `confirmed` field, the entry is `confirmed: false`; given an `agent.yaml` from the agent's own repository, it is `confirmed: true`.
- Given a non-boolean `confirmed` value, the source default applies and a warning is added.
- Given a mandate that fails any check, `has_mandate` is `false`.

**CO-3**
- The shipped `agent.example.yaml` produces no warnings.
- Given a Ready (or later) agent without `max_runtime_minutes`, a warning is raised.
- Given a mandate missing trusted inputs, an evidence policy, a human approval step, a rationale for a forbidden action, or the `change_own_config` prohibition, a warning names the gap (by count, not content).

**CO-4**
- Island and maturity accept exactly the portal's ids and keys.
- Old display labels and the plan stages `draft-plan` / `final-plan` are flagged.
- Every seed manifest in `manifests/` uses the vocabulary.

**CO-5**
- Given a manifest that is not valid YAML, or not a mapping, that agent is listed as `invalid` and the build still writes `map.json` for all others.
- Given a non-integer `open_slots`, the value becomes 0 with a warning and the build completes.
- Given the hostile manifests in `tests/test_hostile_manifests.py`, the build completes and nothing outside the allowlist reaches `map.json`.

## 4. Good output / never do

| A correct output MUST contain | The service must NEVER |
|---|---|
| ✓ Only allowlisted fields per agent, plus `warnings`, `confirmed`, `has_mandate` | ✕ Publish a mandate block, `owners`, or any non-allowlisted field |
| ✓ `confirmed: false` for every agent drawn from a seed | ✕ Show an agent as confirmed or as having a mandate it has not earned |
| ✓ A warning for every rule a manifest fails | ✕ Name mandate tools or actions in a public warning |
| ✓ An entry for every repository in `repos.txt` (mapped, unmapped or invalid) | ✕ Let one repository's manifest stop the build for the others |
| ✓ The same `map.json`, byte for byte, when nothing has changed | ✕ Commit a new `map.json` (or a new timestamp) when the content did not change |

## 5. Coverage gaps

Honest limits, several raised as findings at the SAAF Security Challenge of 10 November 2026:

- **A failed fetch falls back to the seed silently.** If a repository's `agent.yaml` cannot be read (network error, expired token, HTTP 401/403), the build logs it, uses the seed, and the job stays green. A confirmed agent would quietly show as unconfirmed. Planned fix: a warning on the agent, and a failing job when several repositories cannot be read.
- **"Confirmed" is self-declared.** The map does not check who added `agent.yaml`, and a manifest's own `confirmed` value wins. Signed attestations (as in the SAAF circuit breaker's closure work) would be the long-term answer.
- **A manifest can set its own `repo` field** and so present itself as another agent. Planned fix: always take the repository name from `repos.txt`.
- **YAML error text is published.** For a private repository's manifest, the parser's error message could include fragments of its content in `map.json`.
- **Unbounded input.** Response size, YAML aliases, ghost dependency nodes and free text are not capped.
- **CO-5 under real-world inputs.** A finding reports that one malformed manifest can still crash the hourly build; until that is reproduced and fixed, CO-5 is only partly met.
- **Workflow hardening.** The pull-request test job has `contents: write`; actions are pinned to version tags, not commit SHAs; the bot pushes generated commits straight to `main`; `main` has no branch protection (needs an organisation admin).
- **Read-token scope.** The private-repository read token is sent for every entry in `repos.txt`, and its scope is not documented.
- **`seed_from_portal.py`** writes unvalidated portal data into file paths and YAML.
- **`plan` and `owners`** are proposed in `agent.example.yaml` but not read by the build yet.

## 6. Observability

**Logged/traced today:** the GitHub Actions log of each run: one line per repository (`+` repo or seed, with its warning count; `-` unmapped; `x` invalid; `~` dropped fields), fetch errors per branch, and the summary counts. `map.json` carries `generated_at` (when the content last changed) and a `summary` block (agents, mapped, confirmed, with warnings, per island and maturity). Every content change is a commit by `living-map-bot` in the repository history.

**Missing:** fetch errors are not visible on the map itself; no run manifest (input hashes per repository, which source was used and why); no alert when the share of seeds or unreadable repositories rises; Actions logs expire, so older runs cannot be reconstructed beyond the committed `map.json`.

## 7. Status / validation

| Acceptance criterion | Verified? | Evidence |
|---|---|---|
| CO-1 #1 (non-allowlisted fields dropped and named) | ☑ | `test_unknown_fields_are_dropped_and_named` |
| CO-1 #2 (mandate never published, not reported as dropped) | ☑ | `test_mandate_is_never_published_nor_reported_as_dropped` |
| CO-1 #3 (warnings never name mandate items) | ☑ | `test_warnings_never_name_mandate_items` |
| CO-2 #1 (seed unconfirmed, repo confirmed) | ☑ | `test_defaults_by_source`, `test_uc8_seed_is_unconfirmed_with_a_clean_mandate` |
| CO-2 #2 (non-boolean confirmed flagged) | ☑ | `test_non_boolean_is_flagged_and_defaulted` |
| CO-2 #3 (failing mandate → has_mandate false) | ☐ | Follows from `entry()`; no dedicated test — recommend adding one |
| CO-3 #1 (example is clean) | ☑ | `test_example_is_clean` |
| CO-3 #2 (max runtime from Ready onward) | ☑ | `test_max_runtime_required_from_ready_onward` |
| CO-3 #3 (each mandate gap warned) | ☐ | Logic in `check_mandate()`; only some gaps have named tests |
| CO-4 #1–#3 (portal vocabulary) | ☑ | `test_portal_ids_and_keys`, `test_old_labels_are_flagged`, `test_plan_stage_is_flagged`, `test_seeds_use_the_vocabulary` |
| CO-5 #1 (invalid manifest doesn't stop the build) | ◐ | Handled in `entry()`; a challenge finding reports a crash path — to reproduce and fix |
| CO-5 #2 (bad open_slots tolerated) | ☑ | `test_anything_else_is_zero_and_flagged`, `test_build_completes_with_open_slots_lots` |
| CO-5 #3 (hostile manifests) | ☑ | `tests/test_hostile_manifests.py` |
| Good output: unchanged content → unchanged file | ☑ | `test_same_inputs_keep_generated_at_and_file` |
