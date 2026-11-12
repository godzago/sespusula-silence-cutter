from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock,patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import platform_support as support


class PlatformTests(unittest.TestCase):
    def test_windows_prefers_bundled_python(self):
        with tempfile.TemporaryDirectory() as scratch,patch.object(support,'PLATFORM','win32'):
            root=Path(scratch);python=root/'.runtime/python.exe';python.parent.mkdir();python.touch()
            self.assertEqual(support.runtime_python(root),python)

    def test_mac_prefers_native_venv(self):
        with tempfile.TemporaryDirectory() as scratch,patch.object(support,'PLATFORM','darwin'):
            root=Path(scratch);python=root/'.venv/bin/python3';python.parent.mkdir(parents=True);python.touch()
            self.assertEqual(support.runtime_python(root),python)

    def test_mac_project_locations_are_home_relative(self):
        with patch.object(support,'PLATFORM','darwin'):
            paths=support.capcut_indexes(Path('/Users/example'))
        self.assertTrue(all(p.is_relative_to(Path('/Users/example')) for p in paths))
        self.assertTrue(any('UserData' in str(p) for p in paths))
        self.assertTrue(any('User Data' in str(p) for p in paths))

    def test_mac_ffmpeg_discovery_does_not_choose_windows_binary(self):
        with tempfile.TemporaryDirectory() as scratch,patch.object(support,'PLATFORM','darwin'),patch.object(support.importlib.util,'find_spec',return_value=None):
            root=Path(scratch);folder=root/'vendor/imageio_ffmpeg/binaries'
            folder.mkdir(parents=True);(folder/'ffmpeg-win64.exe').touch()
            for name in ('ffmpeg-macos-aarch64-v7.1','ffmpeg-osx-aarch64-v7'):
                binary=folder/name;binary.touch()
                self.assertEqual(support.ffmpeg_path(root),binary)
                binary.unlink()

    def test_mac_audio_is_asynchronous_and_stops_its_owned_process(self):
        with patch.object(support,'PLATFORM','darwin'),patch.object(support.subprocess,'Popen') as spawn:
            process=spawn.return_value;process.poll.return_value=None
            player=support.AudioPlayer();player.play(Path('/tmp/phone call.wav'))
            self.assertEqual(spawn.call_args.args[0],['/usr/bin/afplay',str(Path('/tmp/phone call.wav'))])
            player.stop();process.terminate.assert_called_once();process.wait.assert_called_once_with(timeout=2)

    def test_mac_folder_open_uses_argument_list(self):
        with patch.object(support,'PLATFORM','darwin'),patch.object(support.subprocess,'Popen') as spawn:
            support.open_folder(Path('/tmp/project with spaces'))
        self.assertEqual(spawn.call_args.args[0],['/usr/bin/open',str(Path('/tmp/project with spaces'))])

    def test_mac_capcut_process_blocks_publishing(self):
        import psutil
        process=Mock();process.info={'name':'CapCut'}
        with patch.object(psutil,'process_iter',return_value=[process]):self.assertTrue(support.capcut_is_running())
        process.info={'name':'python'}
        with patch.object(psutil,'process_iter',return_value=[process]):self.assertFalse(support.capcut_is_running())

    def test_frozen_worker_dispatches_back_to_bundled_entry_point(self):
        with patch.object(sys,'frozen',True,create=True):
            self.assertEqual(support.worker_command(Path('/app/executable'),Path('/tmp/request.json')),
                             [str(Path('/app/executable')),'--speech-worker',str(Path('/tmp/request.json'))])

    def test_mac_frozen_preferences_use_application_support(self):
        with patch.object(support,'PLATFORM','darwin'),patch.object(sys,'frozen',True,create=True),patch.object(Path,'home',return_value=Path('/Users/example')):
            self.assertEqual(support.state_root(),Path('/Users/example/Library/Application Support/SesPusulaSilenceCutter'))


if __name__=='__main__':unittest.main()
