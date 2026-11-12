from pathlib import Path
import json
import sys
import tempfile
import threading
import unittest

from test_update import fixture
from silence_core import Project, Cut, US, create_copy, discover_projects, UserError


class MacLayoutTests(unittest.TestCase):
    def test_linked_and_real_project_paths_are_canonical_and_not_duplicated(self):
        with tempfile.TemporaryDirectory() as scratch:
            root=Path(scratch);real=root/'real';real.mkdir();alias=root/'alias'
            if sys.platform=='win32':
                import _winapi
                _winapi.CreateJunction(str(real),str(alias))
            else:alias.symlink_to(real,target_is_directory=True)
            project=fixture(alias/'source')
            index=alias/'root_meta_info.json'
            index.write_text(json.dumps({'all_draft_store':[
                {'draft_fold_path':str(alias/'source'),'draft_name':'Test'},
                {'draft_fold_path':str(project.folder),'draft_name':'Test'}]}))
            found=discover_projects(index)
            self.assertEqual(len(found),1)
            self.assertEqual(found[0][1],project.folder)

    def test_info_filename_preserved_in_root_and_timeline_copy(self):
        with tempfile.TemporaryDirectory() as scratch:
            root=Path(scratch);project=fixture(root/'source')
            timeline=project.folder/'Timelines/timeline';timeline.mkdir(parents=True)
            (timeline/'draft_info.json').write_bytes(project.file.read_bytes())
            (project.folder/'Timelines/project.json').write_text('{"main_timeline_id":"timeline","timelines":[{"id":"timeline"}]}')
            project.file.rename(project.file.with_name('draft_info.json'))
            project=Project(project.folder)
            self.assertEqual(project.file.name,'draft_info.json')
            self.assertEqual(discover_projects(root/'root_meta_info.json')[0][1],project.folder)
            output=create_copy(project,[Cut(US,2*US)],threading.Event(),index=root/'absent.json',check_running=False)
            result=Project(output)
            self.assertEqual(result.duration,59*US)
            self.assertTrue(all(path.name=='draft_info.json' for path in result.content_files))
            self.assertFalse((output/'draft_content.json').exists())
            project.assert_unchanged()

    def test_ambiguous_project_filenames_are_rejected(self):
        with tempfile.TemporaryDirectory() as scratch:
            project=fixture(Path(scratch)/'source')
            (project.folder/'draft_info.json').write_bytes(project.file.read_bytes())
            with self.assertRaises(UserError):Project(project.folder)


if __name__=='__main__':unittest.main()
