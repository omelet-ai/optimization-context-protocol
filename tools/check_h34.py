"""Fresh README installation and real MCP/app calls with no Node/npm on PATH."""
import json
from pathlib import Path
import shutil
import sys
import unittest

from check_h32 import ReadmeJourney, DiagnosticResult


class NoNodeJourney(ReadmeJourney):
    include_node = False

    def test_06_documented_node_install_and_application(self):
        self.assertIsNone(shutil.which('node', path=self.env['PATH']))
        self.assertIsNone(shutil.which('npm', path=self.env['PATH']))
        manifest = json.loads((self.kit / 'manifest.json').read_text())
        self.assertEqual(manifest['target'], 'python')
        self.assertFalse(any(p.suffix in ('.tgz', '.ts') for p in self.kit.iterdir()))
        self.assertFalse((self.kit / 'package.json').exists())
        self.assertEqual(self.first['status'], 'PASS')

    def test_08_existing_destination_is_preserved(self):
        destination = self.work / 'existing'
        destination.mkdir()
        marker = destination / 'keep.txt'
        marker.write_text('keep me')
        result = self.run_ok(['python3.12', '-B', self.source / 'tools/quickstart.py',
                              '--directory', destination], self.source, expected=1)
        self.assertIn('ENVIRONMENT_EXISTS', result.stderr)
        self.assertEqual(marker.read_text(), 'keep me')
        self.assertEqual(list(destination.iterdir()), [marker])

    def test_09_symlink_and_source_destinations_are_rejected(self):
        destination = self.work / 'linked'
        destination.symlink_to(self.work / 'new destination')
        for target, code in [(destination, 'OUTPUT_SYMLINK'), (self.source / 'build', 'OUTPUT_IN_SOURCE')]:
            result = self.run_ok(['python3.12', '-B', self.source / 'tools/quickstart.py',
                                  '--directory', target], self.source, expected=1)
            self.assertIn(code, result.stderr)
        self.assertFalse((self.work / 'new destination').exists())

    def test_10_missing_offline_wheels_do_not_create_environment(self):
        target = self.work / 'missing-wheels-output'
        result = self.run_ok(['python3.12', '-B', self.source / 'tools/quickstart.py',
                              '--directory', target, '--offline-wheelhouse', self.work / 'no-wheels'], self.source, expected=1)
        self.assertIn('OFFLINE_WHEELHOUSE_INVALID', result.stderr)
        self.assertFalse(target.exists())

    def test_11_unknown_kit_target_cannot_install(self):
        broken = self.work / 'broken kit'
        broken.mkdir()
        shutil.copy2(self.kit / 'install.py', broken / 'install.py')
        manifest = json.loads((self.kit / 'manifest.json').read_text())
        manifest['target'] = 'invented'
        (broken / 'manifest.json').write_text(json.dumps(manifest))
        result = self.run_ok(['python3.12', '-B', broken / 'install.py', '--venv', broken / 'env'], broken, expected=1)
        self.assertIn('KIT_INVALID', result.stderr)
        self.assertFalse((broken / 'env').exists())


if __name__ == '__main__':
    result = unittest.TextTestRunner(resultclass=DiagnosticResult).run(unittest.defaultTestLoader.loadTestsFromTestCase(NoNodeJourney))
    ok = result.wasSuccessful() and result.testsRun >= 11 and not result.skipped
    print(json.dumps({'status': 'PASS' if ok else 'FAIL', 'tests_run': result.testsRun,
                      'failures': len(result.failures), 'errors': len(result.errors), 'skipped': len(result.skipped),
                      'failure_diagnostics': result.diagnostics, 'model_calls': 0,
                      'scope': 'Fresh offline selected-source installation with no Node/npm; real apps and MCP SDK; not external human acceptance'}))
    sys.exit(0 if ok else 1)
