# SAAF Living Map

**Live map:** https://saaf-project.github.io/saaf-living-map/ (rebuilt on a schedule)

*Problem.* SAAF's agents live in GitHub repos and in a portal list with a review status. Maturity, phase and dependencies are tracked by hand and go stale.

*Idea.* Each agent repo carries a small agent.yaml. A GitHub Action collects them and renders one map: islands (the SAAF portal's parts: Shared Infrastructure, Planning, Evidence Collection, Reporting, Compliance & Regulatory Assessment, AI Governance & QA, and the quarry of unassigned work), maturity (Building → Ready → Tested → Improving), dependencies and open slots. It is rebuilt on a schedule (hourly by cron, though GitHub can delay runs), so a change in an agent repo shows up at the next run.

*Who benefits.* Participants find an agent to reuse or join. Maintainers see gaps and plan hackathon tracks. Member organisations see what SAAF has delivered and how mature it is.

*Add your agent.* Put an `agent.yaml` in your repo root (see `agent.example.yaml`), open a PR if you don't have push rights, and make sure your repo is listed in `repos.txt`. The next scheduled build picks it up. Until then the map uses a seed manifest from `manifests/`, drafted from the portal; it counts as unconfirmed until the repo has its own `agent.yaml`.

*How it works.*
1. `agent.yaml` schema: see `agent.example.yaml`. `island` and `maturity` take the portal's part ids (`foundation`, `planning`, `collection`, `reporting`, `monitoring`, `governance`, `quarry`) and stage keys (`building`, `ready`, `tested`, `improving`), as agreed on [SAAF-Project/saaf-portal#7](https://github.com/SAAF-Project/saaf-portal/pull/7); the labels come from the portal, so they can change without touching any manifest. The portal's `draft-plan` and `final-plan` stages belong to a plan, not a repo, so a manifest never uses them. Two fields are proposed and not read yet: `plan` (the plan the repo implements) and `owners` (who answers for the agent and its mandate); they sit commented out in the example. Until the build reads them, a manifest that sets them still builds: the allowlist drops them and names them in the build log.
2. `scripts/build_map.py` reads the manifests from the repos in `repos.txt` and writes `map.json`. `map.json` is public, so the `mandate` block is checked but not copied into it; each agent gets `has_mandate: true/false` instead (true only when the block is present and passes every check). Every other field goes through an allowlist (`PUBLISHED` in the script); anything else in a manifest is dropped and named in the build log. `confirmed` says whether the repo has its own `agent.yaml`: it defaults to true for an agent.yaml in the repo and to false for a seed, and the map marks unconfirmed agents. The map does not check who added the file. Run it locally with `pip install pyyaml && python scripts/build_map.py`. Tests: `python -m unittest discover tests`. `map.json` carries `schema_version`, currently 1, which changes only if the file's shape changes in a way readers must handle.
3. `index.html` renders `map.json` as the island map and an overview. The page accepts deep links, `#island=<id>` and `#agent=<owner/repo>`, and the address bar follows the open agent, so any view can be shared. `.nojekyll` tells GitHub Pages to serve these files as they are, without a Jekyll build.

See also: the mandate guard ([SAAF-Project/Audit-criteria PR #1](https://github.com/SAAF-Project/Audit-criteria/pull/1)) reads the same mandate block but checks different fields: output invariants and approval gates. Aligning the two sets of fields is still open.

## Prerequisites

- Python 3 with `pyyaml` (the workflow uses Python 3.12: `.github/workflows/build-map.yml`). The code needs at least Python 3.7 (checked with vermin); a currently supported Python version is recommended.
- Node.js, only for the deep-link tests in `tests/test_hash.js`. `tests/test_deeplink.py` runs them under `python -m unittest` when `node` is available.
- Optional `GITHUB_TOKEN` environment variable. `scripts/build_map.py` sends it when fetching `agent.yaml` from the agent repos, which private repos need. Without it, only public repos and seed manifests are read. Use `--offline` to build from the seed manifests only. In CI the token comes from the `SAAF_READ_TOKEN` secret, or else the workflow's `GITHUB_TOKEN`. Never commit a token. Keep it in your environment or in a `.env` file, which is gitignored.

## Limitations & human review

The README above already states these limits. They are repeated here in one place:

- Island, maturity and dependencies are **self-reported** in each repo's `agent.yaml`. The map does not check who added the file or whether the stated maturity is true.
- Seed manifests in `manifests/` were drafted from the portal and are shown as unconfirmed until the repo carries its own `agent.yaml`.
- The `mandate` block is checked, but only `has_mandate` is published. A `true` value means the block passes the build's checks. It does not mean the agent behaves within its mandate.
- The map is rebuilt hourly, but GitHub can delay scheduled runs, so the map can lag behind the repos.
- No AI model is called. The map is built by deterministic code.

Treat the map as an overview for finding and planning work, not as evidence of an agent's quality.

## Observability

- `scripts/build_map.py` prints one line per repo to the build log: `+` mapped, `-` unmapped, `x` invalid manifest, `~` keys dropped by the allowlist. Fetch errors go to stderr. The log is visible in the GitHub Actions run of `build-map.yml`.
- `map.json` records `generated_at`, a summary, and per-agent `source`, `source_kind` and `warnings`. Its git history shows each change, because the workflow commits it only when it changes.
- Not recorded: who changed an agent's `agent.yaml` (that history lives in the agent repo), or a separate log of failed builds beyond GitHub Actions run history, which is kept according to the SAAF organisation's retention setting (GitHub's default is 90 days).

## License & contact

- Code: MIT, see [`LICENSE`](LICENSE) (copyright TonyBarratt100). TODO(owner): confirm that this licence is agreed with Stichting SAAF, which has not yet decided an organisation-wide licence.
- Maintainer: TonyBarratt100. Contact: open an issue on this repo.
- Plan: none. The Living Map is shared infrastructure for all agents, not an agent with its own plan.
