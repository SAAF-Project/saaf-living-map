#!/usr/bin/env python3
"""Collect agent.yaml manifests from SAAF agent repos and write map.json.

For each repo listed in repos.txt the script tries, in order:
  1. agent.yaml in the repo itself (main, then master branch)
  2. a seed manifest in manifests/<owner>__<repo>.yaml in this repo
Repos with neither still appear on the map as "unmapped".

Usage:  python scripts/build_map.py [--repos repos.txt] [--out map.json] [--offline]
"""
import argparse, json, os, sys, urllib.request, urllib.error
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
# Island ids and maturity stage keys are the SAAF portal's own (agreed on
# SAAF-Project/saaf-portal#7): manifests carry the id or key, labels may change on
# the portal side without touching any manifest. Order follows the portal.
ISLANDS = {
    "foundation": "Shared Infrastructure",
    "planning": "GIAS Audit Planning Pipeline",
    "collection": "Evidence Collection & Extraction",
    "reporting": "Reporting & Visualization",
    "monitoring": "Compliance & Regulatory Assessment",
    "governance": "AI Governance & Quality Assurance",
    "quarry": "Not yet assigned to a track",
}
# The portal's draft-plan and final-plan stages belong to a plan, not a repo,
# so a manifest never carries them.
MATURITY = {"building": "Building", "ready": "Ready", "tested": "Tested",
            "improving": "Improving"}
PLAN_STAGES = ["draft-plan", "final-plan"]
READY_ONWARD = ["ready", "tested", "improving"]
REQUIRED = ["name", "repo", "island", "maturity", "description"]
# Actions every mandate should forbid (the "agents gone rogue" baseline).
BASELINE_FORBIDDEN = ["change_own_config"]


def fetch_remote(repo):
    token = os.environ.get("GITHUB_TOKEN")
    for branch in ("main", "master"):
        url = f"https://raw.githubusercontent.com/{repo}/{branch}/agent.yaml"
        req = urllib.request.Request(url)
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                return r.read().decode("utf-8"), url
        except urllib.error.HTTPError as e:
            if e.code != 404:
                print(f"  ! {repo}@{branch}: HTTP {e.code}", file=sys.stderr)
        except Exception as e:  # network trouble: fall back to seed
            print(f"  ! {repo}@{branch}: {e}", file=sys.stderr)
            break
    return None, None


def fetch_seed(repo):
    p = ROOT / "manifests" / (repo.replace("/", "__") + ".yaml")
    return (p.read_text("utf-8"), str(p.relative_to(ROOT))) if p.exists() else (None, None)


def as_list(v):
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def normalize_forbidden(mandate):
    """Accept plain names or {action, rationale} entries; return list of dicts."""
    out = []
    for f in as_list(mandate.get("forbidden_actions")):
        if isinstance(f, dict):
            out.append({"action": str(f.get("action", "")), "rationale": f.get("rationale")})
        else:
            out.append({"action": str(f), "rationale": None})
    mandate["forbidden_actions"] = out
    return out


def check(m):
    """Return a list of human-readable warnings for one manifest."""
    w = [f"missing field: {f}" for f in REQUIRED if not m.get(f)]
    if m.get("island") and m["island"] not in ISLANDS:
        w.append(f"unknown island: {m['island']} (use one of: {', '.join(ISLANDS)})")
    if m.get("maturity") in PLAN_STAGES:
        w.append(f"maturity {m['maturity']} is a plan stage; a repo starts at building")
    elif m.get("maturity") and m["maturity"] not in MATURITY:
        w.append(f"unknown maturity: {m['maturity']} (use one of: {', '.join(MATURITY)})")
    return w + check_mandate(m)


def check_mandate(m):
    """Return warnings about the mandate block alone."""
    w = []
    mandate = m.get("mandate")
    if not isinstance(mandate, dict):
        w.append("no mandate block")
        return w
    allowed = set(as_list(mandate.get("allowed_tools")))
    fl = normalize_forbidden(mandate)
    forbidden = {f["action"] for f in fl}
    clash = allowed & forbidden
    if clash:
        w.append("tools both allowed and forbidden: " + ", ".join(sorted(clash)))
    for f in BASELINE_FORBIDDEN:
        if f not in forbidden:
            w.append(f"mandate does not forbid {f}")
    if not mandate.get("trusted_inputs"):
        w.append("mandate lists no trusted inputs")
    missing = [f["action"] for f in fl if not f["rationale"]]
    if missing:
        w.append("forbidden actions without rationale: " + ", ".join(missing))
    if not mandate.get("evidence_policy"):
        w.append("mandate has no evidence policy")
    if not mandate.get("human_approval_required_for"):
        w.append("mandate has no human approval step")
    if m.get("maturity") in READY_ONWARD and not mandate.get("max_runtime_minutes"):
        w.append(f"{m['maturity']} agent without max_runtime_minutes")
    return w


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repos", default=str(ROOT / "repos.txt"))
    ap.add_argument("--out", default=str(ROOT / "map.json"))
    ap.add_argument("--offline", action="store_true", help="only use seed manifests")
    a = ap.parse_args()

    repos = [l.split("#")[0].strip() for l in Path(a.repos).read_text().splitlines()]
    repos = [r for r in repos if r]

    agents = {}
    for repo in repos:
        text, src = (None, None) if a.offline else fetch_remote(repo)
        kind = "repo"
        if text is None:
            text, src = fetch_seed(repo)
            kind = "seed"
        if text is None:
            agents[repo] = {"repo": repo, "name": repo.split("/")[-1], "status": "unmapped",
                            "has_mandate": False,
                            "warnings": ["no agent.yaml in repo and no seed manifest"]}
            print(f"  - {repo}: unmapped")
            continue
        try:
            m = yaml.safe_load(text) or {}
        except yaml.YAMLError as e:
            agents[repo] = {"repo": repo, "name": repo.split("/")[-1], "status": "invalid",
                            "source": src, "has_mandate": False, "warnings": [f"YAML error: {e}"]}
            print(f"  x {repo}: invalid YAML")
            continue
        m["repo"] = m.get("repo") or repo
        m["depends_on"] = as_list(m.get("depends_on"))
        m["tags"] = as_list(m.get("tags"))
        m["status"] = "mapped"
        m["source_kind"] = kind
        m["source"] = src
        m["warnings"] = check(m)
        # map.json is public but manifests may come from private repos:
        # publish only whether a clean mandate exists, never the block itself.
        m["has_mandate"] = isinstance(m.get("mandate"), dict) and not check_mandate(m)
        m.pop("mandate", None)
        agents[repo] = m
        print(f"  + {repo}: {kind} ({len(m['warnings'])} warnings)")

    # Dependencies pointing at repos we don't track become ghost nodes.
    for m in list(agents.values()):
        for d in m.get("depends_on", []):
            if d not in agents:
                agents[d] = {"repo": d, "name": d.split("/")[-1], "status": "unmapped",
                             "has_mandate": False,
                             "warnings": ["referenced as a dependency but not in repos.txt"]}

    # Reverse edges: who uses me.
    for m in agents.values():
        m.setdefault("used_by", [])
    for m in agents.values():
        for d in m.get("depends_on", []):
            agents[d]["used_by"].append(m["repo"])

    mapped = [m for m in agents.values() if m["status"] == "mapped"]
    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "islands": [{"id": k, "label": v} for k, v in ISLANDS.items()],
        "maturity_levels": [{"key": k, "label": v} for k, v in MATURITY.items()],
        "summary": {
            "agents": len(agents),
            "mapped": len(mapped),
            "unmapped": len(agents) - len(mapped),
            "open_slots": sum(int(m.get("open_slots") or 0) for m in mapped),
            "by_maturity": {k: sum(1 for m in mapped if m.get("maturity") == k) for k in MATURITY},
            "by_island": {k: sum(1 for m in mapped if m.get("island") == k) for k in ISLANDS},
            "with_warnings": sum(1 for m in mapped if m["warnings"]),
        },
        "agents": sorted(agents.values(), key=lambda m: (m["status"] != "mapped", m["repo"].lower())),
    }
    Path(a.out).write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", "utf-8")
    print(f"wrote {a.out}: {out['summary']}")


if __name__ == "__main__":
    main()
