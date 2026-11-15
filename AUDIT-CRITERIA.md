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
| **CO-1 — The public map carries only allowlisted fields.** Anything else a manifest declares, including the mandate and any `owners`, is checked but never published — not even inside an error message. | GDPR Art. 5(1)(c) (data minimisation) / ISO 27001 A.5.12 (classification of information) | Manifests come from private repositories; `map.json` and the build log are public. Publishing more than the allowlist would leak private mandate content or personal data. |
| **CO-2 — Agent status is never overstated or misattributed.** A seed is unconfirmed by default; `has_mandate` is true only when the mandate passes every check; an entry always belongs to the repository it was read from; a seed shown because the repository could not be read says so. | IIA Standards (sufficiency and reliability of information) / COSO 2013 Principle 13 (relevant, quality information) | Readers use the map to decide which agents to trust and reuse. A badge that isn't earned, or a status shown under the wrong name, gives false assurance. |
| **CO-3 — A declared mandate is checked for completeness.** It must forbid `change_own_config`, list trusted inputs, give a rationale per forbidden action, name an evidence policy and a human approval step, and (from Ready onward) a maximum runtime. | EU AI Act Art. 14 (human oversight) / OWASP LLM Top 10 — LLM06 Excessive Agency | The mandate is the agent's declared boundary. A mandate without approval steps or reasons is a boundary in name only. |
| **CO-4 — Island and maturity use only the portal's vocabulary.** Unknown ids, old labels and plan-only stages are flagged, not silently accepted. | COBIT BAI10 (configuration management) | The map and the portal must describe the same thing in the same terms; drift between them breaks the shared picture of SAAF. |
| **CO-5 — Bad input or a broken source cannot silently degrade the map.** Invalid or hostile manifests become warnings on that agent; when too many repositories cannot be read, the build fails and keeps the last good map. | ISO 27001 A.8.28 (secure coding) / COBIT DSS01 (operations) | Any repository owner can write a manifest, and the build depends on a token and on GitHub being reachable. Failures must be visible, not absorbed. |

## 3. Acceptance criteria (testable, pass/fail)

**CO-1**
- Given a manifest with fields outside the allowlist (e.g. `owner_email`, `internal_notes`), the published entry contains none of them, and their names appear in the build log as dropped.
- Given a manifest with a valid mandate, the published entry contains no `mandate` key, only `has_mandate: true`, and the mandate is not reported as dropped.
- Warnings published in `map.json` count mandate items but never name them.
- Given a manifest that is not valid YAML, the published warning gives only the line number; no text from the manifest appears in `map.json`.

**CO-2**
- Given a seed manifest with no `confirmed` field, the entry is `confirmed: false`; given an `agent.yaml` from the agent's own repository, it is `confirmed: true`.
- Given a non-boolean `confirmed` value, the source default applies and a warning is added.
- Given a mandate that fails any check, `has_mandate` is `false`.
- Given a manifest whose `repo` field names another repository, the entry keeps the repository it was read from, with a warning.
- Given a repository whose `agent.yaml` cannot be read (an HTTP error other than 404, or a network error), its entry shows the seed with a warning saying so; a repository with no `agent.yaml` gets no such warning.

**CO-3**
- The shipped `agent.example.yaml` produces no warnings.
- Given a Ready (or later) agent without `max_runtime_minutes`, a warning is raised.
- Given a mandate missing trusted inputs, an evidence policy, a human approval step, a rationale for a forbidden action, or the `change_own_config` prohibition, a warning names the gap (by count, not content).

**CO-4**
- Island and maturity accept exactly the portal's ids and keys.
- Old display labels and the plan stages `draft-plan` / `final-plan` are flagged.
- Every seed manifest in `manifests/` uses the vocabulary.

**CO-5**
- Given a manifest that is not valid YAML, or not a mapping, or with a field of the wrong type, that agent is listed as `invalid` or gets a warning, and the build still writes `map.json` for all others.
- Given a non-integer `open_slots`, the value becomes 0 with a warning and the build completes.
- Given the hostile manifests in `tests/test_hostile_manifests.py`, the build completes and nothing outside the allowlist reaches `map.json`.
- Given more unreadable repositories than `--max-read-errors` (default 2), the build exits with an error and leaves the existing `map.json` unchanged.

## 4. Good output / never do

| A correct output MUST contain | The service must NEVER |
|---|---|
| ✓ Only allowlisted fields per agent, plus `warnings`, `confirmed`, `has_mandate` | ✕ Publish a mandate block, `owners`, any non-allowlisted field, or text quoted from a manifest |
| ✓ `confirmed: false` for every agent drawn from a seed | ✕ Show an agent as confirmed or as having a mandate it has not earned |
| ✓ Each entry under the repository it was read from | ✕ Let a manifest present itself as another agent |
| ✓ A warning for every rule a manifest fails, and for every repository that could not be read | ✕ Fall back to a seed without saying so |
| ✓ An entry for every repository in `repos.txt` (mapped, unmapped or invalid) | ✕ Let one repository's manifest stop the build for the others |
| ✓ The same `map.json`, byte for byte, when nothing has changed | ✕ Publish a degraded map when the source is broken; keep the last good one instead |

## 5. Coverage gaps

Honest limits an auditor would reasonably expect this service to address, that it currently does not, or only partly does:

- **"Confirmed" is self-declared.** The map does not check who added `agent.yaml`, and a manifest's own `confirmed` value wins. Signed attestations by an independent reviewer would be the long-term answer.
- **Input limits.** Manifest size, YAML structure and free-text fields are not yet capped, and dependencies on untracked repositories add entries to the map.
- **Workflow hardening.** Least-privilege permissions per job, actions pinned to commit SHAs, and review of the bot's generated commits are still to do; branch protection on `main` needs an organisation admin.
- **Token scope** for reading private repositories is not documented.
- **The seed generator** (`scripts/seed_from_portal.py`) does not yet validate portal data.
- **`plan` and `owners`** are proposed in `agent.example.yaml` but not read by the build yet.

Fixed during the 2026 hardening round: parser error text could reach the public map; a manifest's own `repo` field could override the repository it was read from; an unreadable repository fell back to its seed silently; a manifest field of the wrong type could stop the build for every repository.

## 6. Observability

**Logged/traced today:** the GitHub Actions log of each run: one line per repository (`+` repo or seed, with its warning count; `-` unmapped; `x` invalid; `~` dropped fields; `!` a repository that could not be read, with the HTTP status or "network error"), and the summary counts. On the map, an unreadable repository carries a warning saying its seed is shown instead. When more repositories than `--max-read-errors` cannot be read, the run fails (red) and `map.json` is left unchanged. `map.json` carries `generated_at` (when the content last changed) and a `summary` block. Every content change is a commit by `living-map-bot`.

**Missing:** no run manifest (input hashes per repository, which source was used and why); no alert beyond the failed run itself; Actions logs expire, so older runs cannot be reconstructed beyond the committed `map.json`.

## 7. Status / validation

| Acceptance criterion | Verified? | Evidence |
|---|---|---|
| CO-1 #1 (non-allowlisted fields dropped and named) | ☑ | `test_unknown_fields_are_dropped_and_named` |
| CO-1 #2 (mandate never published, not reported as dropped) | ☑ | `test_mandate_is_never_published_nor_reported_as_dropped` |
| CO-1 #3 (warnings never name mandate items) | ☑ | `test_warnings_never_name_mandate_items` |
| CO-1 #4 (YAML errors never quote the manifest) | ☑ | `test_yaml_error_does_not_quote_the_manifest` |
| CO-2 #1 (seed unconfirmed, repo confirmed) | ☑ | `test_defaults_by_source`, `test_uc8_seed_is_unconfirmed_with_a_clean_mandate` |
| CO-2 #2 (non-boolean confirmed flagged) | ☑ | `test_non_boolean_is_flagged_and_defaulted` |
| CO-2 #3 (failing mandate → has_mandate false) | ☐ | Follows from `entry()`; no dedicated test — recommend adding one |
| CO-2 #4 (manifest cannot claim another repo) | ☑ | `test_manifest_cannot_claim_another_repo`, `test_matching_repo_field_gives_no_warning` |
| CO-2 #5 (unreadable repo shown as seed, with warning) | ☑ | `test_unreadable_repo_shows_its_seed_with_a_warning`, `test_repo_without_agent_yaml_gets_no_read_warning` |
| CO-3 #1 (example is clean) | ☑ | `test_example_is_clean` |
| CO-3 #2 (max runtime from Ready onward) | ☑ | `test_max_runtime_required_from_ready_onward` |
| CO-3 #3 (each mandate gap warned) | ☐ | Logic in `check_mandate()`; only some gaps have named tests |
| CO-4 #1–#3 (portal vocabulary) | ☑ | `test_portal_ids_and_keys`, `test_old_labels_are_flagged`, `test_plan_stage_is_flagged`, `test_seeds_use_the_vocabulary` |
| CO-5 #1 (invalid manifest doesn't stop the build) | ☑ | `test_wrong_field_types_never_stop_the_build`, `test_unexpected_error_marks_only_that_repo_invalid` |
| CO-5 #2 (bad open_slots tolerated) | ☑ | `test_anything_else_is_zero_and_flagged`, `test_build_completes_with_open_slots_lots` |
| CO-5 #3 (hostile manifests) | ☑ | `tests/test_hostile_manifests.py` |
| CO-5 #4 (too many read errors → fail, keep last map) | ☑ | `test_too_many_unreadable_repos_fail_and_keep_the_last_map` |
| Good output: unchanged content → unchanged file | ☑ | `test_same_inputs_keep_generated_at_and_file` |
