"""Hostile manifests must never put markup on the page.

Manifests are written by agent owners, so every field is untrusted. This builds a map
from manifests full of script tags, event handlers, attribute break-outs and javascript:
links (through build_map.main(), as the workflow does), renders it with the page's own
hash.js and app.js (tests/render_page.js, under node), and parses every HTML string the
page writes. Only the page's own tags and attributes may appear; the payloads must come
through as text. Run: python -m unittest discover tests
"""
import contextlib, io, json, shutil, subprocess, sys, tempfile, unittest
from html.parser import HTMLParser
from pathlib import Path
from unittest import mock
from urllib.parse import urlsplit

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import build_map  # noqa: E402

PAYLOADS = [
    "<script>alert(1)</script>",
    "<img src=x onerror=alert(1)>",
    '"><svg onload=alert(1)>',
    "' onmouseover='alert(1)' x='",
    '" onfocus="alert(1)" autofocus="',
    "javascript:alert(1)",
    "</textarea></title><iframe srcdoc=\"<script>alert(1)</script>\">",
    "&lt;script&gt;alert(1)&lt;/script&gt;",
    "`${alert(1)}`",
]
P = " ".join(PAYLOADS)

# Everything the page itself writes. Anything else came from a manifest.
TAGS = {"a", "b", "button", "code", "dd", "div", "dl", "dt", "h2", "h3", "h4", "i", "li",
        "p", "small", "span", "ul"}
ATTRS = {"aria-label", "aria-pressed", "class", "data-f", "data-m", "data-repo", "href", "id",
         "rel", "style", "target", "title"}


def manifest(repo, **over):
    m = yaml.safe_load((ROOT / "agent.example.yaml").read_text("utf-8"))
    return yaml.safe_dump(m | {"repo": repo} | over, allow_unicode=True)


# repo in repos.txt -> manifest text (None: no manifest, so the repo is unmapped).
SEEDS = {
    "SAAF-Project/every-field": manifest(
        "SAAF-Project/every-field", name=P, description=P, category=P, language=P, tags=PAYLOADS,
        island=P, maturity=P, confirmed=P, review=P,
        depends_on=["SAAF-Project/<script>alert(1)</script>", "javascript:alert(1)",
                    '"><img src=x onerror=alert(1)>']),
    "SAAF-Project/repo-override": manifest("javascript:alert(1)//<svg onload=alert(1)>",
                                           name="<b onclick=alert(1)>x</b>"),
    "SAAF-Project/ready-and-clean-but-named": manifest(
        "SAAF-Project/ready-and-clean-but-named", name="' autofocus onfocus='alert(1)", island="planning", maturity="ready",
        depends_on=["SAAF-Project/every-field"]),
    "SAAF-Project/broken-yaml": "name: <script>alert(1)</script>\n  description: [\"><img src=x onerror=alert(1)>\n",
    "SAAF-Project/not-a-mapping": "- <script>alert(1)</script>\n",
    "SAAF-Project/<svg onload=alert(1)>": None,
}


def build(tmp):
    repos = tmp / "repos.txt"
    repos.write_text("\n".join(SEEDS) + "\n", "utf-8")
    out = tmp / "map.json"
    argv = ["build_map.py", "--offline", "--repos", str(repos), "--out", str(out)]
    with mock.patch.object(sys, "argv", argv), \
            mock.patch.object(build_map, "fetch_seed", lambda r: (SEEDS.get(r), f"manifests/{r}.yaml") if SEEDS.get(r) else (None, None)), \
            contextlib.redirect_stdout(io.StringIO()):
        build_map.main()
    return out


class Collect(HTMLParser):
    """Records every tag, attribute and text node in one HTML string."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags, self.attrs, self.text = [], [], []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.attrs += [(tag, k, v or "") for k, v in attrs]

    handle_startendtag = handle_starttag

    def handle_data(self, data):
        self.text.append(data)

    def handle_comment(self, data):
        self.tags.append("<!--")

    def handle_decl(self, decl):
        self.tags.append("<!")

    def handle_pi(self, data):
        self.tags.append("<?")

    def unknown_decl(self, data):
        self.tags.append("<![")


@unittest.skipUnless(shutil.which("node"), "node is not installed; the page is rendered with it")
class HostileManifests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as d:
            out = build(Path(d))
            cls.map = json.loads(out.read_text("utf-8"))
            r = subprocess.run([shutil.which("node"), str(ROOT / "tests" / "render_page.js"), str(out)],
                               cwd=ROOT, capture_output=True, text=True)
        if r.returncode:
            raise AssertionError("tests/render_page.js failed:\n" + r.stdout + r.stderr)
        cls.html = json.loads(r.stdout)
        cls.parsed = []
        for h in cls.html:
            p = Collect(); p.feed(h); p.close()
            cls.parsed.append((h, p))

    def test_payloads_reach_map_json_unchanged(self):
        # build_map.py is not the line of defence (map.json is data); the page is.
        a = next(a for a in self.map["agents"] if a["repo"] == "SAAF-Project/every-field")
        self.assertEqual(a["name"], P)
        self.assertEqual(a["tags"], PAYLOADS)
        self.assertTrue(any(x["status"] == "invalid" for x in self.map["agents"]))

    def test_every_view_was_rendered(self):
        details = [h for h in self.html if 'class="close"' in h]
        self.assertGreaterEqual(len(details), len(self.map["agents"]))

    def test_only_the_pages_own_tags(self):
        for h, p in self.parsed:
            self.assertEqual(set(p.tags) - TAGS, set(), h)

    def test_only_the_pages_own_attributes(self):
        for h, p in self.parsed:
            for tag, k, v in p.attrs:
                self.assertIn(k, ATTRS, f"<{tag} {k}={v!r}> in:\n{h}")

    def test_links_stay_on_the_page_or_github(self):
        for h, p in self.parsed:
            for tag, k, v in p.attrs:
                if k != "href":
                    continue
                u = urlsplit(v)
                ok = v.startswith("#") or (u.scheme == "https" and u.netloc == "github.com")
                self.assertTrue(ok, f"href={v!r} in:\n{h}")

    def test_styles_are_the_pages_own(self):
        for h, p in self.parsed:
            for tag, k, v in p.attrs:
                if k == "style":
                    self.assertNotRegex(v, r"(?i)alert|url\(|expression|javascript|[<>\"']", h)

    def test_payloads_show_up_as_text(self):
        # Proves the checks above are not vacuous: the payloads were rendered, as text.
        text = "".join(t for _, p in self.parsed for t in p.text)
        for payload in PAYLOADS:
            self.assertIn(payload, text)
        titles = [v for _, p in self.parsed for _, k, v in p.attrs if k in ("title", "data-repo")]
        self.assertTrue(any("<svg onload=alert(1)>" in v for v in titles), titles)


if __name__ == "__main__":
    unittest.main()
