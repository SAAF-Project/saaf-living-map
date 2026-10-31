"""Tests for scripts/build_map.py. Run: python -m unittest discover tests"""
import json, subprocess, sys, tempfile, unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import build_map  # noqa: E402


def example():
    return yaml.safe_load((ROOT / "agent.example.yaml").read_text("utf-8"))


class Vocabulary(unittest.TestCase):
    def test_portal_ids_and_keys(self):
        # Agreed on SAAF-Project/saaf-portal#7.
        self.assertEqual(list(build_map.ISLANDS), ["foundation", "planning", "collection",
                         "reporting", "monitoring", "governance", "quarry"])
        self.assertEqual(list(build_map.MATURITY), ["building", "ready", "tested", "improving"])

    def test_example_is_clean(self):
        self.assertEqual(build_map.check(example()), [])

    def test_rcm_builder_manifest_is_clean(self):
        # The map fields of SAAF-Project/RCM-Builder's agent.yaml (PR #4). Its mandate
        # is private, so the example's stands in for it.
        m = example() | {"name": "RCM Builder (UC7)", "repo": "SAAF-Project/RCM-Builder",
                         "island": "planning", "maturity": "ready",
                         "category": "Risk & Controls", "depends_on": []}
        self.assertEqual(build_map.check(m), [])

    def test_old_labels_are_flagged(self):
        w = build_map.check(example() | {"island": "Fieldwork", "maturity": "QA Assessment"})
        self.assertTrue(any(x.startswith("unknown island: Fieldwork") for x in w), w)
        self.assertTrue(any(x.startswith("unknown maturity: QA Assessment") for x in w), w)

    def test_plan_stage_is_flagged(self):
        w = build_map.check(example() | {"maturity": "final-plan"})
        self.assertIn("maturity final-plan is a plan stage; a repo starts at building", w)

    def test_max_runtime_required_from_ready_onward(self):
        for stage, flagged in [("building", False), ("ready", True), ("tested", True), ("improving", True)]:
            m = example() | {"maturity": stage}
            del m["mandate"]["max_runtime_minutes"]
            self.assertEqual(f"{stage} agent without max_runtime_minutes" in build_map.check(m), flagged, stage)

    def test_seeds_use_the_vocabulary(self):
        for p in sorted((ROOT / "manifests").glob("*.yaml")):
            m = yaml.safe_load(p.read_text("utf-8"))
            self.assertIn(m["island"], build_map.ISLANDS, p.name)
            self.assertIn(m["maturity"], build_map.MATURITY, p.name)


class Build(unittest.TestCase):
    def test_offline_build(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "map.json"
            subprocess.run([sys.executable, str(ROOT / "scripts" / "build_map.py"),
                            "--offline", "--out", str(out)], check=True, capture_output=True)
            data = json.loads(out.read_text("utf-8"))
        self.assertEqual(data["islands"][1], {"id": "planning", "label": "GIAS Audit Planning Pipeline"})
        self.assertEqual([l["key"] for l in data["maturity_levels"]], list(build_map.MATURITY))
        mapped = [a for a in data["agents"] if a["status"] == "mapped"]
        self.assertTrue(mapped)
        for a in mapped:
            self.assertFalse([w for w in a["warnings"] if w.startswith("unknown")], a["repo"])
            self.assertNotIn("mandate", a)
        self.assertEqual(sum(data["summary"]["by_island"].values()), len(mapped))


if __name__ == "__main__":
    unittest.main()
