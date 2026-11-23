"""Synthetic public-output and empty-input regressions; no GitHub calls."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_map


class ServiceContract(unittest.TestCase):
    def example(self):
        return yaml.safe_load((ROOT / 'agent.example.yaml').read_text())

    def test_bad_nonpublic_values_are_not_quoted_in_warnings(self):
        for field in ('confirmed', 'open_slots'):
            manifest = self.example() | {field: {'synthetic_private_marker': 'not-public'}}
            entry = build_map.entry('SAAF-Project/example', yaml.safe_dump(manifest), 'agent.yaml', 'repo')
            public, _ = build_map.publish(entry)
            self.assertNotIn('synthetic_private_marker', json.dumps(public))
            self.assertTrue(public['warnings'])

    def test_mixed_unknown_keys_do_not_crash_or_reach_build_logs(self):
        manifest = self.example() | {42: 'synthetic_value', 'synthetic_private_key': 'not-public'}
        text = yaml.safe_dump(manifest, sort_keys=False)
        with tempfile.TemporaryDirectory() as directory:
            repos = Path(directory) / 'repos'; repos.write_text('SAAF-Project/example\n')
            output = Path(directory) / 'map.json'
            stdout = io.StringIO()
            with mock.patch.object(sys, 'argv', ['build_map', '--offline', '--repos', str(repos), '--out', str(output)]), \
                    mock.patch.object(build_map, 'fetch_seed', return_value=(text, 'synthetic.yaml')), \
                    contextlib.redirect_stdout(stdout):
                build_map.main()
            result = json.loads(output.read_text())
            self.assertEqual(result['summary']['mapped'], 1)
            self.assertNotIn('synthetic_private_key', stdout.getvalue() + output.read_text())
            self.assertIn('dropped 2 keys', stdout.getvalue())

    def test_empty_input_and_negative_error_budget_keep_last_map(self):
        with tempfile.TemporaryDirectory() as directory:
            repos = Path(directory) / 'repos'; output = Path(directory) / 'map.json'
            output.write_text('previous verified output')
            for text, extra in [('# comment only\n', []), ('SAAF-Project/example\n', ['--max-read-errors', '-1'])]:
                repos.write_text(text)
                with mock.patch.object(sys, 'argv', ['build_map', '--offline', '--repos', str(repos), '--out', str(output), *extra]), \
                        contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                    build_map.main()
                self.assertEqual(error.exception.code, 2)
                self.assertEqual(output.read_text(), 'previous verified output')

    def test_invalid_mandate_never_sets_has_mandate(self):
        manifest = self.example()
        manifest['mandate'].pop('evidence_policy')
        result = build_map.entry('SAAF-Project/example', yaml.safe_dump(manifest), 'agent.yaml', 'repo')
        self.assertFalse(result['has_mandate'])

    def test_service_manifest_is_valid_but_unconfirmed(self):
        result = build_map.entry('SAAF-Project/saaf-living-map', (ROOT / 'agent.yaml').read_text(), 'agent.yaml', 'repo')
        self.assertEqual(result['warnings'], [])
        self.assertFalse(result['confirmed'])
        self.assertTrue(result['has_mandate'])


if __name__ == '__main__':
    unittest.main()
