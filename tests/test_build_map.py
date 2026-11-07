"""Tests for scripts/build_map.py. Run: python -m unittest discover tests"""
import contextlib, io, json, subprocess, sys, tempfile, unittest
from pathlib import Path
from unittest import mock

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

    def test_warnings_never_name_mandate_items(self):
        m = example()
        m["mandate"]["allowed_tools"] = ["send_email", "claude_api"]
        m["mandate"]["forbidden_actions"] = ["send_email", "change_own_config", "delete_evidence"]
        w = build_map.check(m)
        self.assertIn("1 tool both allowed and forbidden", w)
        self.assertIn("3 forbidden actions without rationale", w)
        self.assertFalse([x for x in w if "send_email" in x or "delete_evidence" in x], w)
        m["mandate"]["forbidden_actions"] = [{"action": "send_email", "rationale": None},
                                             {"action": "change_own_config", "rationale": "PR only"}]
        self.assertIn("1 forbidden action without rationale", build_map.check(m))

    def test_seeds_use_the_vocabulary(self):
        for p in sorted((ROOT / "manifests").glob("*.yaml")):
            m = yaml.safe_load(p.read_text("utf-8"))
            self.assertIn(m["island"], build_map.ISLANDS, p.name)
            self.assertIn(m["maturity"], build_map.MATURITY, p.name)


def seed(repo):
    p = ROOT / "manifests" / (repo.replace("/", "__") + ".yaml")
    return p.read_text("utf-8"), str(p.relative_to(ROOT))


class Allowlist(unittest.TestCase):
    def test_list_is_what_the_page_and_summary_use(self):
        self.assertEqual(build_map.PUBLISHED, [
            "name", "repo", "island", "maturity", "category", "language", "description",
            "tags", "depends_on", "used_by", "open_slots", "status", "source_kind", "source",
            "warnings", "has_mandate", "confirmed", "review"])

    def test_unknown_fields_are_dropped_and_named(self):
        m = example() | {"owner_email": "x@example.org", "internal_notes": "do not publish"}
        e = build_map.entry("SAAF-Project/X", yaml.safe_dump(m), "agent.yaml", "repo")
        out, dropped = build_map.publish(e)
        self.assertEqual(dropped, ["internal_notes", "owner_email"])
        self.assertNotIn("owner_email", out)
        self.assertNotIn("internal_notes", out)
        self.assertNotIn("mandate", out)
        self.assertTrue(set(out) <= set(build_map.PUBLISHED), set(out) - set(build_map.PUBLISHED))
        self.assertTrue(out["has_mandate"])

    def test_mandate_is_never_published_nor_reported_as_dropped(self):
        e = build_map.entry("SAAF-Project/X", yaml.safe_dump(example()), "agent.yaml", "repo")
        out, dropped = build_map.publish(e)
        self.assertEqual(dropped, [])
        self.assertNotIn("mandate", out)


class Confirmed(unittest.TestCase):
    def test_defaults_by_source(self):
        m = example(); m.pop("confirmed", None)
        text = yaml.safe_dump(m)
        self.assertTrue(build_map.entry("SAAF-Project/X", text, "agent.yaml", "repo")["confirmed"])
        self.assertFalse(build_map.entry("SAAF-Project/X", text, "manifests/x.yaml", "seed")["confirmed"])

    def test_manifest_value_wins(self):
        e = build_map.entry("SAAF-Project/X", yaml.safe_dump(example() | {"confirmed": False}), "agent.yaml", "repo")
        self.assertFalse(e["confirmed"])
        e = build_map.entry("SAAF-Project/X", yaml.safe_dump(example() | {"confirmed": True}), "m.yaml", "seed")
        self.assertTrue(e["confirmed"])

    def test_non_boolean_is_flagged_and_defaulted(self):
        e = build_map.entry("SAAF-Project/X", yaml.safe_dump(example() | {"confirmed": "yes please"}), "m.yaml", "seed")
        self.assertFalse(e["confirmed"])
        self.assertIn("confirmed must be true or false, not 'yes please'", e["warnings"])

    def test_uc8_seed_is_unconfirmed_with_a_clean_mandate(self):
        text, src = seed("SAAF-Project/Audit-Work-Program-Agent-UC-8-")
        e = build_map.entry("SAAF-Project/Audit-Work-Program-Agent-UC-8-", text, src, "seed")
        self.assertEqual(e["warnings"], [])
        self.assertTrue(e["has_mandate"])
        self.assertFalse(e["confirmed"])


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
        for a in data["agents"]:
            self.assertTrue(set(a) <= set(build_map.PUBLISHED), (a["repo"], set(a) - set(build_map.PUBLISHED)))
            self.assertIsInstance(a["confirmed"], bool, a["repo"])
        # Every seed is unconfirmed by default.
        self.assertTrue(all(not a["confirmed"] for a in mapped if a["source_kind"] == "seed"))
        self.assertEqual(sum(data["summary"]["by_island"].values()), len(mapped))
        self.assertEqual(list(data["summary"]), ["agents", "mapped", "unmapped", "open_slots",
                         "by_maturity", "by_island", "with_warnings", "confirmed"])
        self.assertEqual(data["summary"]["confirmed"], sum(1 for a in mapped if a["confirmed"]))
        self.assertLessEqual(data["summary"]["confirmed"], data["summary"]["mapped"])

    def test_schema_version_is_1_and_first(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "map.json"
            subprocess.run([sys.executable, str(ROOT / "scripts" / "build_map.py"),
                            "--offline", "--out", str(out)], check=True, capture_output=True)
            data = json.loads(out.read_text("utf-8"))
        self.assertIs(type(data["schema_version"]), int)
        self.assertEqual(data["schema_version"], 1)
        self.assertEqual(list(data)[0], "schema_version")


class OpenSlots(unittest.TestCase):
    def test_whole_numbers_pass_through(self):
        for v in (0, 3):
            e = build_map.entry("SAAF-Project/X", yaml.safe_dump(example() | {"open_slots": v}), "m.yaml", "seed")
            self.assertEqual(e["open_slots"], v)
            self.assertFalse([w for w in e["warnings"] if "open_slots" in w], e["warnings"])

    def test_anything_else_is_zero_and_flagged(self):
        for v in ("lots", "3", 2.5, True, [1], {"n": 1}):
            e = build_map.entry("SAAF-Project/X", yaml.safe_dump(example() | {"open_slots": v}), "m.yaml", "seed")
            self.assertEqual(e["open_slots"], 0, v)
            self.assertIn(f"open_slots must be a whole number, not {v!r}", e["warnings"])

    def test_build_completes_with_open_slots_lots(self):
        repo = "SAAF-Project/Audit-Work-Program-Agent-UC-8-"
        original = build_map.fetch_seed

        def lots(r):
            text, src = original(r)
            if r == repo:
                text = text.replace("open_slots: 0", 'open_slots: "lots"', 1)
            return text, src

        self.assertIn("open_slots: 0", seed(repo)[0])
        with tempfile.TemporaryDirectory() as d:
            data = json.loads(build_offline(Path(d) / "map.json", fetch_seed=lots))
        a = next(a for a in data["agents"] if a["repo"] == repo)
        self.assertEqual(a["open_slots"], 0)
        self.assertIn("open_slots must be a whole number, not 'lots'", a["warnings"])
        self.assertGreater(len(data["agents"]), 1)
        mapped = [a for a in data["agents"] if a["status"] == "mapped"]
        self.assertEqual(data["summary"]["open_slots"], sum(a.get("open_slots") or 0 for a in mapped))


OLD = "2000-01-01T00:00:00+00:00"


def build_offline(out, fetch_seed=build_map.fetch_seed):
    """Run build_map.main() in-process, offline, writing to out."""
    argv = ["build_map.py", "--offline", "--out", str(out)]
    with mock.patch.object(sys, "argv", argv), mock.patch.object(build_map, "fetch_seed", fetch_seed), \
            contextlib.redirect_stdout(io.StringIO()):
        build_map.main()
    return out.read_text("utf-8")


def backdate(out):
    """Rewrite out with an old generated_at, so a fresh timestamp is easy to spot."""
    data = json.loads(out.read_text("utf-8"))
    data["generated_at"] = OLD
    out.write_text(build_map.render(data), "utf-8")
    return out.read_text("utf-8")


class GeneratedAt(unittest.TestCase):
    def test_same_inputs_keep_generated_at_and_file(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "map.json"
            build_offline(out)
            before = backdate(out)
            after = build_offline(out)
        self.assertEqual(json.loads(after)["generated_at"], OLD)
        self.assertEqual(after, before)

    def test_real_change_updates_generated_at(self):
        repo = "SAAF-Project/Audit-Work-Program-Agent-UC-8-"
        original = build_map.fetch_seed

        def changed_seed(r):
            text, src = original(r)
            if r == repo:
                text = text.replace("maturity: building", "maturity: ready", 1)
            return text, src

        self.assertIn("maturity: building", seed(repo)[0])
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "map.json"
            build_offline(out)
            before = backdate(out)
            after = build_offline(out, fetch_seed=changed_seed)
        data = json.loads(after)
        self.assertNotEqual(data["generated_at"], OLD)
        self.assertNotEqual(after, before)
        self.assertEqual(next(a for a in data["agents"] if a["repo"] == repo)["maturity"], "ready")

    def test_unreadable_existing_file_gets_a_fresh_timestamp(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "map.json"
            out.write_text("not json", "utf-8")
            data = json.loads(build_offline(out))
        self.assertNotEqual(data["generated_at"], OLD)
        self.assertIn("T", data["generated_at"])


if __name__ == "__main__":
    unittest.main()
