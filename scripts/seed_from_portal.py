#!/usr/bin/env python3
"""Draft seed manifests for SAAF's reviewed agents from the portal's own data.

Source: public/data/agent-reviews.json in SAAF-Project/saaf-portal (public repo),
the registry the portal uses for the agent-library "reviewed" badge.

For every record with verdict "reviewed" this writes
    manifests/SAAF-Project__<repo>.yaml
and adds the repo to repos.txt. Existing manifests are left alone, so hand-written
ones (such as UC-8's, which has a full mandate) are never overwritten.

The drafts carry the map fields only. They have no mandate block on purpose: no
SAAF agent has published one yet, so the map shows them as "mandate issues" until
the agent's owners add one. That gap is the honest state of things.

Usage:
    python scripts/seed_from_portal.py                       # fetch from GitHub
    python scripts/seed_from_portal.py --reviews path.json   # use a local copy
"""
import argparse, json, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE_URL = ("https://raw.githubusercontent.com/SAAF-Project/saaf-portal/main/"
              "public/data/agent-reviews.json")

# Island per agent (the portal's part ids): a judgement call from each repo's README
# and the SAAF track it came from. Anything not listed falls back to the category
# default below.
ISLAND = {
    "RCM-Builder": "planning",
    "Audit-Work-Program-Agent-UC-8-": "planning",
    "GDPR-AI-Audit-Agent": "monitoring",
    "Vendor_Guard": "monitoring",
    "Track-2-Evidence-Collection-Extraction": "collection",
    "CUEC_Crosscheck": "collection",
    "Track-2---IAM-final": "collection",
    "Compliance-Report-Generator": "monitoring",
    "Compliance-Audit-Agent": "collection",
    "three-way-match-audit": "reporting",
    "ExecGRC": "reporting",
    "Executive-Summary-Writer": "reporting",
    "WhatsTheNews": "monitoring",
    "llm_owasp": "governance",
    "judging-found-controls": "governance",
    "Audit-criteria": "governance",
    "OWASP-top-10-LLM-assessment": "governance",
    "SAAF-circuit-breaker": "governance",
    "hallucination-detection-agent": "governance",
}
CATEGORY_DEFAULT = {
    "Compliance": "collection", "Evidence": "collection", "Risk & Controls": "planning",
    "Audit Reporting": "reporting", "AI Security": "governance",
    "AI Assurance": "governance", "Governance & Guardrails": "governance",
}

# Every reviewed agent is "ready" (the portal's stage key: Do complete, not tested
# yet). Seeds never claim "tested" or "improving"; that is for the owners to say.
MATURITY = "ready"

# Display names for the map tiles.
NAME = {
    "GDPR-AI-Audit-Agent": "GDPR AI Audit", "Vendor_Guard": "Vendor Guard",
    "RCM-Builder": "RCM Builder (UC7)",
    "Track-2-Evidence-Collection-Extraction": "Evidence Collection & Extraction",
    "llm_owasp": "LLM OWASP Review", "CUEC_Crosscheck": "CUEC Crosscheck",
    "WhatsTheNews": "What's The News", "ExecGRC": "ExecGRC",
    "Track-2---IAM-final": "IAM Access Review",
    "Audit-Work-Program-Agent-UC-8-": "Work Program (UC8)",
    "Compliance-Report-Generator": "Compliance Report Generator",
    "three-way-match-audit": "Three-Way Match Audit",
    "judging-found-controls": "Judging Found Controls",
    "Executive-Summary-Writer": "Executive Summary Writer",
    "Compliance-Audit-Agent": "Compliance Audit Agent",
    "Audit-criteria": "Audit Criteria & Mandate Guard",
    "OWASP-top-10-LLM-assessment": "OWASP Top 10 LLM Assessment",
    "SAAF-circuit-breaker": "SAAF Circuit Breaker",
    "hallucination-detection-agent": "Hallucination Detection",
}

# One-line descriptions from each repo's GitHub description or README (6 Oct 2026).
DESCRIPTION = {
    "GDPR-AI-Audit-Agent": "Audits AI systems for GDPR alignment, with PII masking, automated DPIA generation and risk scoring.",
    "Vendor_Guard": "Third-party risk management agent.",
    "RCM-Builder": "Builds a Risk and Control Matrix from UC1-UC5 risk inputs: normalise risks, design controls, validate IT dependencies.",
    "Track-2-Evidence-Collection-Extraction": "AI control assessment: upload policy PDFs and query them for evidence.",
    "llm_owasp": "Reviews LLM applications against the OWASP Top 10 for LLMs.",
    "CUEC_Crosscheck": "Matches vendor ISAE 3402 / SOC 2 CUECs to the organisation's controls.",
    "WhatsTheNews": "Finds news from trusted sources and produces a personal regulatory news summary.",
    "ExecGRC": "Executive GRC reporting: turns risk and control results into an executive summary.",
    "Track-2---IAM-final": "User access review over the full population (IAM).",
    "Audit-Work-Program-Agent-UC-8-": "Create audit work program based on the delivered risk-control matrix from UC 7.",
    "Compliance-Report-Generator": "Finds the relevant regulatory frameworks for a given financial entity.",
    "three-way-match-audit": "P2P 3-way match audit report generator with data and reporting tools.",
    "judging-found-controls": "Judges the controls found in a policy document to avoid hallucination.",
    "Executive-Summary-Writer": "Guides an audit manager through root cause, finding relationships, storyline and tone before writing the Executive Board summary.",
    "Compliance-Audit-Agent": "Triages internal policies for a regulatory clause, assesses compliance and renders a Word report.",
    "Audit-criteria": "Drafts and hardens AUDIT-CRITERIA.md for SAAF agent repos; includes the UC7-UC8-UC9 orchestrator and mandate guard.",
    "OWASP-top-10-LLM-assessment": "Assesses whether other agents comply with the OWASP Top 10 risks for LLM applications.",
    "SAAF-circuit-breaker": "Deterministic policy guards, drift detection, rollback and offline workpaper verification.",
    "hallucination-detection-agent": "Hallucination detection for AI-generated audit findings.",
}


def q(s):
    """Quote a scalar for YAML if it needs it."""
    s = str(s)
    if s == "" or any(c in s for c in ":#{}[],&*?|-<>=!%@`'\"") or s != s.strip():
        return json.dumps(s, ensure_ascii=False)
    return s


def manifest(r):
    repo = r["repo"]
    island = ISLAND.get(repo) or CATEGORY_DEFAULT.get(r.get("category"), "foundation")
    qual = r.get("quality") or {}
    lines = [
        f"# Draft seed manifest, generated by scripts/seed_from_portal.py from the",
        f"# SAAF portal's agent-reviews.json. Not written by the agent's owners:",
        f"# replace with an agent.yaml in the agent repo itself. Island and maturity",
        f"# are unconfirmed until the owners do.",
        f"name: {q(NAME.get(repo, repo))}",
        f"repo: SAAF-Project/{repo}",
        f"island: {q(island)}",
        f"maturity: {MATURITY}",
        f"category: {q(r.get('category', ''))}",
        f"language: {q(r.get('language', ''))}",
        "depends_on: []",
        "tags: [" + ", ".join(q(t) for t in r.get("tags", [])) + "]",
        "open_slots: 0",
        f"description: {q(DESCRIPTION.get(repo, r.get('structure', '')))}",
        "",
        "# From the portal review (not part of the mandate).",
        "review:",
        f"  verdict: {q(r['verdict'])}",
        f"  structure: {q(r.get('structure', ''))}",
        f"  has_tests: {str(bool(qual.get('hasTests'))).lower()}",
        f"  has_samples: {str(bool(qual.get('hasSamples'))).lower()}",
    ]
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reviews", help="local agent-reviews.json (default: fetch from GitHub)")
    a = ap.parse_args()
    if a.reviews:
        data = json.loads(Path(a.reviews).read_text("utf-8"))
    else:
        with urllib.request.urlopen(SOURCE_URL, timeout=20) as r:
            data = json.loads(r.read().decode("utf-8"))
    reviewed = [r for r in data["reviews"] if r.get("verdict") == "reviewed"]

    mdir = ROOT / "manifests"
    mdir.mkdir(exist_ok=True)
    written, kept = [], []
    for r in reviewed:
        p = mdir / f"SAAF-Project__{r['repo']}.yaml"
        if p.exists():
            kept.append(r["repo"])
            continue
        p.write_text(manifest(r), "utf-8")
        written.append(r["repo"])

    repos_path = ROOT / "repos.txt"
    lines = repos_path.read_text("utf-8").splitlines()
    present = {l.split("#")[0].strip() for l in lines}
    for r in reviewed:
        name = f"SAAF-Project/{r['repo']}"
        if name not in present:
            lines.append(name)
            present.add(name)
    repos_path.write_text("\n".join(lines) + "\n", "utf-8")

    print(f"{len(reviewed)} reviewed agents: {len(written)} drafts written, {len(kept)} kept as is")
    for x in kept:
        print(f"  kept: {x}")


if __name__ == "__main__":
    main()
