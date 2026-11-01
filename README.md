# SAAF Living Map

**Live map:** https://saaf-project.github.io/saaf-living-map/ (rebuilds hourly)

*Problem.* SAAF's agents live in GitHub repos and in a portal list with a review status. Maturity, phase and dependencies are tracked by hand and go stale.

*Idea.* Each agent repo carries a small agent.yaml. A GitHub Action collects them and renders one map: islands (the SAAF portal's parts: Shared Infrastructure, Planning, Evidence Collection, Reporting, Compliance & Regulatory Assessment, AI Governance & QA, and the quarry of unassigned work), maturity (Building → Ready → Tested → Improving), dependencies and open slots. It rebuilds every hour, so a change in an agent repo shows up at the next run.

*Who benefits.* Participants find an agent to reuse or join. Maintainers see gaps and plan hackathon tracks. Member organisations see what SAAF has delivered and how mature it is.

*Add your agent.* Put an `agent.yaml` in your repo root (see `agent.example.yaml`), open a PR if you don't have push rights, and make sure your repo is listed in `repos.txt`. The next hourly build picks it up. Until then the map uses a seed manifest from `manifests/`, drafted from the portal; its island and maturity are unconfirmed until the owners add their own.

*How it works.*
1. `agent.yaml` schema: see `agent.example.yaml`. `island` and `maturity` take the portal's part ids (`foundation`, `planning`, `collection`, `reporting`, `monitoring`, `governance`, `quarry`) and stage keys (`building`, `ready`, `tested`, `improving`), as agreed on [SAAF-Project/saaf-portal#7](https://github.com/SAAF-Project/saaf-portal/pull/7); the labels come from the portal, so they can change without touching any manifest. The portal's `draft-plan` and `final-plan` stages belong to a plan, not a repo, so a manifest never uses them.
2. `scripts/build_map.py` reads the manifests from the repos in `repos.txt` and writes `map.json`. `map.json` is public, so the `mandate` block is checked but not copied into it; each agent gets `has_mandate: true/false` instead (true only when the block is present and passes every check). Every other field goes through an allowlist (`PUBLISHED` in the script); anything else in a manifest is dropped and named in the build log. `confirmed` says whether the owners have confirmed island and maturity: it defaults to true for an agent.yaml in the repo and to false for a seed, and the map marks unconfirmed agents. Run it locally with `pip install pyyaml && python scripts/build_map.py`. Tests: `python -m unittest discover tests`. `map.json` carries `schema_version`, currently 1, which changes only if the file's shape changes in a way readers must handle.
3. `index.html` renders `map.json` as the island map and an overview. `.nojekyll` tells GitHub Pages to serve these files as they are, without a Jekyll build.

See also: the mandate guard ([SAAF-Project/Audit-criteria PR #1](https://github.com/SAAF-Project/Audit-criteria/pull/1)) reads the same mandate block but checks different fields: output invariants and approval gates. Aligning the two sets of fields is still open.
