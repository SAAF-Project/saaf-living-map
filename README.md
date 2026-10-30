# SAAF Living Map

**Live map:** https://tonybarratt100.github.io/saaf-living-map/ (rebuilds hourly)

*Problem.* SAAF's agents live in GitHub repos and in a portal list with a review status. Maturity, phase and dependencies are tracked by hand and go stale.

*Idea.* Each agent repo carries a small agent.yaml. A GitHub Action collects them and renders one map: islands (Planning, Fieldwork, Reporting, AI Governance & QA, Monitoring, Shared Infrastructure), maturity (Draft workplan → Building → QA Assessment → Ready), dependencies and open slots. It updates when a repo changes.

*Who benefits.* Participants find an agent to reuse or join. Maintainers see gaps and plan hackathon tracks. Member organisations see what SAAF has delivered and how mature it is.

*Add your agent.* Put an `agent.yaml` in your repo root (see `agent.example.yaml`), open a PR if you don't have push rights, and make sure your repo is listed in `repos.txt`. The next hourly build picks it up. Until then the map uses a seed manifest from `manifests/`.

*How it works.*
1. `agent.yaml` schema: see `agent.example.yaml`.
2. `scripts/build_map.py` reads the manifests from the repos in `repos.txt` and writes `map.json`. `map.json` is public, so the `mandate` block is checked but not copied into it; each agent gets `has_mandate: true/false` instead (true only when the block is present and passes every check). Run it locally with `pip install pyyaml && python scripts/build_map.py`.
3. `index.html` renders `map.json` as the island map and an overview. `.nojekyll` tells GitHub Pages to serve these files as they are, without a Jekyll build.

Built at the SAAF Agents Gone Rogue hackathon (6 Oct 2026) by the Dining Table Crew: Tony Barratt, Anja Nell, Bob McLaughlin, Francois Marais.

See also: the mandate guard built on this schema, in [SAAF-Project/Audit-criteria PR #1](https://github.com/SAAF-Project/Audit-criteria/pull/1).
