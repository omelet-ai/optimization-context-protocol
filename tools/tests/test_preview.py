"""Release integrity negative cases; these fixtures never authorize a release."""
import hashlib
import json
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from prepare_preview import ROOT, PLAN, FORM, archive, archive_inventory, blank_form, files, read_plan, verify, prepare, write, sha


class Preview(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = self.root / 'data'; self.data.mkdir()
        (self.data / 'a.txt').write_text('synthetic\n')

    def test_archive_roundtrip(self):
        archive(self.data, self.root / 'a.zip')
        self.assertEqual(archive_inventory(self.root / 'a.zip'), files(self.data))

    def test_archive_is_deterministic(self):
        archive(self.data, self.root / 'a.zip'); archive(self.data, self.root / 'b.zip')
        self.assertEqual((self.root / 'a.zip').read_bytes(), (self.root / 'b.zip').read_bytes())

    def test_archive_never_overwrites(self):
        archive(self.data, self.root / 'a.zip')
        with self.assertRaises(FileExistsError): archive(self.data, self.root / 'a.zip')

    def test_source_symlink_rejected(self):
        (self.data / 'b.txt').symlink_to(self.data / 'a.txt')
        with self.assertRaisesRegex(ValueError, 'SYMLINK'): archive(self.data, self.root / 'a.zip')

    def test_traversal_and_absolute_paths_rejected(self):
        for i, name in enumerate(['../outside', '/outside', 'a/../outside', 'a\\outside', './outside']):
            path = self.root / f'{i}.zip'
            with zipfile.ZipFile(path, 'w') as z:
                info = zipfile.ZipInfo(name); info.external_attr = (stat.S_IFREG | 0o644) << 16
                z.writestr(info, b'test')
            with self.assertRaisesRegex(ValueError, 'UNSAFE'): archive_inventory(path)

    def test_zip_symlink_rejected(self):
        path = self.root / 'link.zip'
        with zipfile.ZipFile(path, 'w') as z:
            info = zipfile.ZipInfo('link'); info.external_attr = (stat.S_IFLNK | 0o777) << 16
            z.writestr(info, b'../outside')
        with self.assertRaisesRegex(ValueError, 'NON_REGULAR'): archive_inventory(path)

    def test_blank_review_has_no_invented_participant(self):
        blank_form(json.loads((ROOT / FORM).read_text()))

    def test_cannot_prepopulate_human_acceptance(self):
        form = json.loads((ROOT / FORM).read_text()); form['external_developer_acceptance'] = 'PASS'
        with self.assertRaises(ValueError): blank_form(form)

    def test_cannot_prepopulate_task_success(self):
        form = json.loads((ROOT / FORM).read_text()); form['tasks'][0]['status'] = 'PASS'
        with self.assertRaises(ValueError): blank_form(form)

    def test_cannot_omit_independent_engine_task(self):
        form = json.loads((ROOT / FORM).read_text()); form['tasks'].pop(2)
        with self.assertRaises(ValueError): blank_form(form)

    def test_local_plan_not_publication_permission(self):
        (self.root / PLAN).parent.mkdir(parents=True)
        plan = read_plan(); plan['publication_authorized'] = True
        (self.root / PLAN).write_text(json.dumps(plan))
        with self.assertRaisesRegex(ValueError, 'CANNOT_AUTHORIZE'): read_plan(self.root)

    def test_release_version_cannot_escape_output(self):
        (self.root / PLAN).parent.mkdir(parents=True)
        plan = read_plan(); plan['release_id'] = '../outside'
        (self.root / PLAN).write_text(json.dumps(plan))
        with self.assertRaisesRegex(ValueError, 'INVALID_PREVIEW'): read_plan(self.root)

    def test_existing_output_is_preserved(self):
        with patch('prepare_preview.verify_source', return_value={}):
            with self.assertRaises(FileExistsError): prepare(self.data)
        self.assertEqual((self.data / 'a.txt').read_text(), 'synthetic\n')

    def candidate(self):
        source = self.root / 'source'; (source / PLAN).parent.mkdir(parents=True)
        plan = read_plan(); write(source / PLAN, plan)
        (source / 'provenance').mkdir()
        write(source / 'provenance/repository-selection.json', {'files': [PLAN, 'provenance/repository-selection.json']})
        kit = self.root / 'kit'; kit.mkdir()
        write(kit / 'REVIEW_FORM.json', json.loads((ROOT / FORM).read_text()))
        write(kit / 'manifest.json', {'files': files(kit)})
        assets = self.root / 'assets'; assets.mkdir()
        archives = {}
        for kind, folder in [('source', source), ('native', kit)]:
            name = f'ocp-{kind}-{plan["release_id"]}.zip'; archive(folder, assets / name)
            archives[name] = sha(assets / name)
        inventory = files(source)
        write(assets / 'preview.json', {'plan': plan, 'status': 'PREPARED_NOT_PUBLISHED',
              'source_files': inventory, 'source_tree_sha256': hashlib.sha256(json.dumps(inventory, sort_keys=True).encode()).hexdigest(),
              'kit_manifest_sha256': sha(kit / 'manifest.json'), 'archives': archives})
        (assets / 'SHA256SUMS').write_text(''.join(f'{h}  {n}\n' for n,h in sorted(archives.items())))
        # Unit fixture tests inventory binding; real wheel versions run in H63.
        patcher = patch('prepare_preview.check_versions'); patcher.start(); self.addCleanup(patcher.stop)

    def test_complete_inventory_passes(self):
        self.candidate(); self.assertEqual(verify(self.root)['status'], 'PASS')

    def test_changed_kit_rejected(self):
        self.candidate(); (self.root / 'kit/REVIEW_FORM.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'KIT_INVENTORY'): verify(self.root)

    def test_changed_source_rejected(self):
        self.candidate(); (self.root / 'source/new.py').write_text('value=1')
        with self.assertRaisesRegex(ValueError, 'SOURCE_INVENTORY'): verify(self.root)

    def test_wrong_source_digest_rejected(self):
        self.candidate(); path = self.root / 'assets/preview.json'
        value = json.loads(path.read_text()); value['source_tree_sha256'] = '0' * 64; write(path, value)
        with self.assertRaisesRegex(ValueError, 'SOURCE_INVENTORY'): verify(self.root)

    def test_changed_archive_rejected(self):
        self.candidate(); path = next((self.root / 'assets').glob('ocp-native-*.zip'))
        path.write_bytes(path.read_bytes() + b'changed')
        with self.assertRaisesRegex(ValueError, 'ARCHIVE_INVENTORY'): verify(self.root)

    def test_unlisted_release_evidence_rejected(self):
        self.candidate(); (self.root / 'assets/run.log').write_text('local evidence')
        with self.assertRaisesRegex(ValueError, 'UNLISTED'): verify(self.root)

    def test_changed_checksum_file_rejected(self):
        self.candidate(); (self.root / 'assets/SHA256SUMS').write_text('invalid')
        with self.assertRaisesRegex(ValueError, 'CHECKSUM'): verify(self.root)


if __name__ == '__main__':
    r = unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(Preview))
    ok = r.wasSuccessful() and not r.skipped
    print(json.dumps({'status': 'PASS' if ok else 'FAIL', 'tests_run': r.testsRun, 'errors': len(r.errors),
                      'failures': len(r.failures), 'skipped': len(r.skipped)}))
    raise SystemExit(not ok)
