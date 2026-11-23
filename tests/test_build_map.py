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
        self.assertIn("confirmed must be true or false; source default used", e["warnings"])

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
            self.assertIn("open_slots must be a whole number; using 0", e["warnings"])

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
        self.assertIn("open_slots must be a whole number; using 0", a["warnings"])
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


class UntrustedManifests(unittest.TestCase):
    def test_yaml_error_does_not_quote_the_manifest(self):
        text = "name: Secret Agent\nmandate:\n  purpose: do-not-publish-this\n  bad: [unclosed\n"
        e = build_map.entry("SAAF-Project/Private", text, "agent.yaml", "repo")
        self.assertEqual(e["status"], "invalid")
        published = json.dumps(e)
        self.assertNotIn("do-not-publish-this", published)
        self.assertNotIn("unclosed", published)
        self.assertTrue(e["warnings"][0].startswith("manifest is not valid YAML"))

    def test_manifest_cannot_claim_another_repo(self):
        m = example() | {"repo": "SAAF-Project/RCM-Builder"}
        e = build_map.entry("SAAF-Project/Impostor", yaml.safe_dump(m), "agent.yaml", "repo")
        self.assertEqual(e["repo"], "SAAF-Project/Impostor")
        self.assertIn("manifest names a different repo; the repo it was read from is used", e["warnings"])

    def test_matching_repo_field_gives_no_warning(self):
        m = example() | {"repo": "SAAF-Project/Same"}
        e = build_map.entry("SAAF-Project/Same", yaml.safe_dump(m), "agent.yaml", "repo")
        self.assertEqual(e["warnings"], [])


class ReadErrors(unittest.TestCase):
    """A repo that cannot be read must never fall back to its seed silently."""

    REPOS = ["SAAF-Project/A", "SAAF-Project/B", "SAAF-Project/C", "SAAF-Project/D"]

    def build(self, remote, out, max_errors=None):
        with tempfile.TemporaryDirectory() as d:
            repos = Path(d) / "repos.txt"
            repos.write_text("\n".join(self.REPOS) + "\n", "utf-8")
            argv = ["build_map.py", "--repos", str(repos), "--out", str(out)]
            if max_errors is not None:
                argv += ["--max-read-errors", str(max_errors)]
            seed = yaml.safe_dump(example())
            with mock.patch.object(sys, "argv", argv), \
                    mock.patch.object(build_map, "fetch_remote", remote), \
                    mock.patch.object(build_map, "fetch_seed", lambda r: (seed, "manifests/x.yaml")), \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                build_map.main()

    def agent(self, out, repo):
        return next(m for m in json.loads(out.read_text("utf-8"))["agents"] if m["repo"] == repo)

    def test_unreadable_repo_shows_its_seed_with_a_warning(self):
        remote = lambda r: (None, None, "HTTP 401") if r.endswith("/A") else (None, None, None)
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "map.json"
            self.build(remote, out)
            a = self.agent(out, "SAAF-Project/A")
            self.assertEqual(a["source_kind"], "seed")
            self.assertIn("could not read agent.yaml from the repo (HTTP 401); showing the seed instead",
                          a["warnings"])
            self.assertFalse(any("could not read" in w for w in self.agent(out, "SAAF-Project/B")["warnings"]))

    def test_repo_without_agent_yaml_gets_no_read_warning(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "map.json"
            self.build(lambda r: (None, None, None), out)
            for repo in self.REPOS:
                self.assertFalse(any("could not read" in w for w in self.agent(out, repo)["warnings"]))

    def test_too_many_unreadable_repos_fail_and_keep_the_last_map(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "map.json"
            out.write_text("last good map", "utf-8")
            with self.assertRaises(SystemExit) as stop:
                self.build(lambda r: (None, None, "network error"), out, max_errors=2)
            self.assertEqual(stop.exception.code, 1)
            self.assertEqual(out.read_text("utf-8"), "last good map")


class FieldTypes(ReadErrors):
    """A field of the wrong type must never stop the build for every other repo."""

    # Each of these crashed the build before (field types were not checked).
    BAD = {
        "island_list": {"island": ["planning"]},
        "maturity_list": {"maturity": ["ready"]},
        "nested_tools": {"mandate": {"allowed_tools": [["read_rcm"]]}},
        "date_description": {"description": __import__("datetime").date(2026, 11, 15)},
        "depends_on_mapping": {"depends_on": [{"repo": "SAAF-Project/B"}]},
        "depends_on_number": {"depends_on": [5]},
        "used_by_text": {"used_by": "SAAF-Project/B"},
    }

    def remote_with(self, bad):
        good = yaml.safe_dump(example())
        text = yaml.safe_dump(example() | bad)
        return lambda r: (text, "agent.yaml", None) if r.endswith("/A") else (good, "agent.yaml", None)

    def test_wrong_field_types_never_stop_the_build(self):
        for name, bad in self.BAD.items():
            with self.subTest(name), tempfile.TemporaryDirectory() as d:
                out = Path(d) / "map.json"
                self.build(self.remote_with(bad), out)
                self.assertEqual(self.agent(out, "SAAF-Project/B")["status"], "mapped")
                self.assertIn(self.agent(out, "SAAF-Project/A")["status"], ("mapped", "invalid"))

    def test_text_field_of_the_wrong_type_is_ignored_with_a_warning(self):
        m = build_map.entry("SAAF-Project/A", yaml.safe_dump(example() | {"island": ["planning"]}),
                            "agent.yaml", "repo")
        self.assertNotIn("island", m)
        self.assertIn("island must be text; ignored", m["warnings"])

    def test_non_text_list_items_are_dropped_with_a_warning(self):
        m = build_map.entry("SAAF-Project/A", yaml.safe_dump(example() | {
            "depends_on": ["SAAF-Project/B", {"repo": "x"}, 5]}), "agent.yaml", "repo")
        self.assertEqual(m["depends_on"], ["SAAF-Project/B"])
        self.assertIn("2 depends_on entries not text; ignored", m["warnings"])

    def test_nested_allowed_tools_fail_the_mandate(self):
        bad = example()
        bad["mandate"]["allowed_tools"] = [["read_rcm"]]
        m = build_map.entry("SAAF-Project/A", yaml.safe_dump(bad), "agent.yaml", "repo")
        self.assertIn("allowed_tools must be a list of names", m["warnings"])
        self.assertFalse(m["has_mandate"])

    def test_manifest_cannot_set_used_by(self):
        remote = self.remote_with({"used_by": ["SAAF-Project/X"]})
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "map.json"
            self.build(remote, out)
            self.assertEqual(self.agent(out, "SAAF-Project/A")["used_by"], [])

    def test_unexpected_error_marks_only_that_repo_invalid(self):
        real = build_map.entry
        def entry(repo, *a):
            if repo.endswith("/A"):
                raise RuntimeError("boom")
            return real(repo, *a)
        with tempfile.TemporaryDirectory() as d, mock.patch.object(build_map, "entry", entry):
            out = Path(d) / "map.json"
            self.build(self.remote_with({}), out)
            a = self.agent(out, "SAAF-Project/A")
            self.assertEqual(a["status"], "invalid")
            self.assertIn("manifest could not be processed", a["warnings"])
            self.assertNotIn("boom", out.read_text("utf-8"))
            self.assertEqual(self.agent(out, "SAAF-Project/B")["status"], "mapped")


class TemplatePlaceholders(unittest.TestCase):
    """A blank from the agent template that was never filled in is flagged, not published as if real."""

    TEMPLATE = (
        'name: "[Agent name]"\n'
        'repo: SAAF-Project/[repo-name]\n'
        'island: planning\n'
        'maturity: building\n'
        'description: "[One sentence: what the agent does and for whom.]"\n'
        'mandate:\n'
        '  purpose: "[One sentence. What the agent exists to do.]"\n'
        '  allowed_tools: [read_input_file, write_findings]\n'
        '  forbidden_actions:\n'
        '    - action: change_own_config\n'
        '      rationale: Changes to this mandate go through a pull request.\n'
        '  trusted_inputs: [input_file]\n'
        '  human_approval_required_for: [using the findings in an audit report]\n'
        '  evidence_policy: cite_only_given_context\n')

    def test_unfilled_template_is_flagged_field_by_field(self):
        w = build_map.entry("SAAF-Project/new-agent", self.TEMPLATE, "agent.yaml", "repo")["warnings"]
        for f in ("name", "description", "mandate purpose"):
            self.assertIn(f + " still has a template placeholder", w)
        self.assertIn("manifest names a different repo; the repo it was read from is used", w)

    def test_placeholder_warnings_never_quote_the_text(self):
        w = build_map.entry("SAAF-Project/new-agent", self.TEMPLATE, "agent.yaml", "repo")["warnings"]
        self.assertFalse(any("Agent name" in x or "One sentence" in x for x in w), w)

    def test_filled_in_template_gives_no_placeholder_warning(self):
        filled = (self.TEMPLATE.replace("[Agent name]", "Invoice Checker").replace("[repo-name]", "new-agent")
                  .replace("[One sentence: what the agent does and for whom.]", "Checks invoices against orders for auditors.")
                  .replace("[One sentence. What the agent exists to do.]", "Flag invoices that do not match an order."))
        e = build_map.entry("SAAF-Project/new-agent", filled, "agent.yaml", "repo")
        self.assertEqual(e["warnings"], [])
        self.assertTrue(e["has_mandate"])

    def test_yaml_lists_and_ordinary_brackets_are_not_placeholders(self):
        self.assertEqual(build_map.check(example() | {"description": "Reads the RCM [UC7] and writes a work program [beta]"}), [])
        self.assertEqual(build_map.check(example() | {"description": "Totals [1] and [2]"}), [])
        w = build_map.check(example() | {"tags": ["audit", "[your tag]"]})
        self.assertIn("1 tags entry still a template placeholder", w)


if __name__ == "__main__":
    unittest.main()
