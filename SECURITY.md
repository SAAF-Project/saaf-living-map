# Security policy

## Reporting a weakness

Please report security issues **privately**, not as a public issue or pull request:
email **info@saafproject.com** with "Living Map security" in the subject.

Describe what you found, where (file and line, or URL), and how to reproduce it.
Never include live keys, tokens or personal data in a report.

The Living Map is maintained by volunteers. We aim to acknowledge a report within
a week and will tell you what we decide to do about it.

## Scope

In scope:
- `scripts/build_map.py` and the build workflow (`.github/workflows/build-map.yml`)
- the published `map.json` and the map page (`index.html`, `app.js`)
- the seed manifests in `manifests/`

Out of scope: the agent repositories themselves (report to their owners) and
GitHub's own infrastructure.

## What the map publishes, by design

`map.json` is public. It carries only the fields on the build's allowlist; an agent's
mandate is checked but never published, and neither are any `owners`. An agent
marked "confirmed" has its own agent.yaml in its repository: the map does not
verify who added that file.
