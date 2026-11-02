"""Runs the deep-link tests in tests/test_hash.js (hash.js) under node, so that
python -m unittest discover tests covers them too."""
import shutil, subprocess, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class DeepLinkHash(unittest.TestCase):
    def test_hash_js(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node is not installed; tests/test_hash.js needs it (node --test tests/test_hash.js)")
        r = subprocess.run([node, "--test", "tests/test_hash.js"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, "node --test tests/test_hash.js failed:\n" + r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
