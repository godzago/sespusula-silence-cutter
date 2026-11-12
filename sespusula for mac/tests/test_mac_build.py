import ast
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock

import build_mac
import mac_target
import setup_mac
import portable_selftest
from packaging_support import archive_release, mac_wheels, RUNTIME_SOURCES


class MacBuildTests(unittest.TestCase):
    def test_build_failure_opens_the_actual_test_error_in_visible_file(self):
        def broken():raise AssertionError('actual failure details')
        suite=unittest.TestSuite([unittest.FunctionTestCase(broken)])
        with tempfile.TemporaryDirectory() as scratch:
            root=Path(scratch)
            with patch.object(build_mac.unittest.defaultTestLoader,'discover',return_value=suite), patch.object(build_mac.sys,'platform','darwin'), patch.object(build_mac.subprocess,'run') as opened, contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit):build_mac.run_tests(root)
            self.assertIn('actual failure details',(root/'KURULUM-HATASI.txt').read_text(encoding='utf-8'))
            opened.assert_called_once_with(['/usr/bin/open','-a','TextEdit',str(root/'KURULUM-HATASI.txt')],check=False)

    def test_native_arm64_on_macos26_is_accepted(self):
        with patch.object(mac_target.sys,'platform','darwin'), patch.object(mac_target.sys,'version_info',(3,11,9)), patch.object(mac_target.platform,'machine',return_value='arm64'), patch.object(mac_target.platform,'mac_ver',return_value=('26.3.2',(),'')):
            self.assertEqual(mac_target.require_native_mac(),'arm64')

    def test_rosetta_old_os_and_wrong_python_are_rejected(self):
        for machine,version,python in [('x86_64','26.3.2',(3,11,9)),('arm64','15.6',(3,11,9)),('arm64','26.3.2',(3,12,0))]:
            with self.subTest(machine=machine,version=version,python=python), patch.object(mac_target.sys,'platform','darwin'), patch.object(mac_target.sys,'version_info',python), patch.object(mac_target.platform,'machine',return_value=machine), patch.object(mac_target.platform,'mac_ver',return_value=(version,(),'')):
                with self.assertRaises(RuntimeError):mac_target.require_native_mac()

    def test_frozen_app_spec_collects_current_workers_and_features(self):
        text=build_mac.spec_text(Path('/Users/test/Desktop/folder with spaces'))
        ast.parse(text)
        for item in ('captions','export_pipeline','jump_cut','timeline_markers','speech_worker'):
            self.assertIn(item,text)
            self.assertIn(item+'.py',RUNTIME_SOURCES)
        self.assertIn("target_arch='arm64'",text)
        self.assertIn("'LSMinimumSystemVersion':'26.0'",text)
        self.assertIn("'NSHighResolutionCapable':True",text)
        self.assertIn('optimize=0',text)

    def test_arm_wheel_dependency_graph_is_complete(self):
        wheels=mac_wheels(build_mac.ROOT/'wheelhouse/arm64','arm64')
        self.assertEqual(len(wheels),34)
        self.assertTrue(all('x86_64' not in p.name and 'win_amd64' not in p.name for p in wheels))

    def test_offline_assets_match_locked_hashes(self):
        setup_mac.verify_assets(build_mac.ROOT)

    def test_setup_checkpoint_includes_runtime_changes(self):
        with tempfile.TemporaryDirectory() as scratch:
            root=Path(scratch)
            for relative in ('requirements-mac-arm64.lock','wheelhouse/arm64/manifest.json','.models/whisper-small/local-manifest.json','app.py'):
                path=root/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('first',encoding='utf-8')
            initial=setup_mac.environment_key(root=root)
            (root/'app.py').write_text('changed',encoding='utf-8')
            self.assertNotEqual(initial,setup_mac.environment_key(root=root))

    def test_frozen_selftest_requires_dependencies_inside_app_not_siblings(self):
        with tempfile.TemporaryDirectory() as scratch:
            app=Path(scratch)/'Applications/SesPusula.app'
            executable=app/'Contents/MacOS/SesPusula'
            with patch.object(portable_selftest.sys,'frozen',True,create=True), patch.object(portable_selftest.sys,'platform','darwin'), patch.object(portable_selftest.sys,'executable',str(executable)):
                self.assertEqual(portable_selftest.runtime_boundary(),app.resolve())

    def test_stale_or_wrong_arch_venv_is_not_ready(self):
        with tempfile.TemporaryDirectory() as scratch:
            root=Path(scratch);python=root/'python';python.touch()
            checkpoint=root/'checkpoint.json';checkpoint.write_text(json.dumps({'key':'ready'}))
            with patch.object(setup_mac.subprocess,'run',return_value=Mock(returncode=1)):
                self.assertFalse(setup_mac.environment_ready(python,checkpoint,'ready'))
            with patch.object(setup_mac.subprocess,'run',return_value=Mock(returncode=0)):
                self.assertTrue(setup_mac.environment_ready(python,checkpoint,'ready'))

    def test_source_zip_excludes_work_data_and_preserves_launch_permissions(self):
        import zipfile
        with tempfile.TemporaryDirectory() as scratch:
            root=Path(scratch)/'source';root.mkdir()
            for relative in ('app.py','Mac Uygulamasini Olustur.command','mac_launcher.sh','.state/private.json','.git/config','gpt.md','Dogrulama/report.json'):
                path=root/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('example')
            archive=Path(scratch)/'source.zip';archive_release(root,archive)
            with zipfile.ZipFile(archive) as bundle:
                names=bundle.namelist()
                self.assertEqual(set(names),{'source/app.py','source/Mac Uygulamasini Olustur.command','source/mac_launcher.sh','source/SHA256SUMS.json'})
                self.assertTrue((bundle.getinfo('source/mac_launcher.sh').external_attr>>16)&0o111)
                self.assertTrue((bundle.getinfo('source/Mac Uygulamasini Olustur.command').external_attr>>16)&0o111)


if __name__=='__main__':unittest.main()
