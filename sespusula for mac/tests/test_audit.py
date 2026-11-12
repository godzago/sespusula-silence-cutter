import copy
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from captions import add_caption_track, build_captions
from export_pipeline import export_copy
from review import ReviewSession
from silence_core import Cut, Project, Settings, US, UserError, create_copy
from speech_analysis import ENGINE, analyze_speech, prune_cache
from timeline_markers import add_repeat_markers
from test_update import fixture


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='sespusula-audit-')
        self.root=Path(self.temp.name);self.cancel=threading.Event()
        self.p=fixture(self.root/'source',seconds=6)
    def tearDown(self):self.temp.cleanup()

    def test_word_crossing_analysis_chunk_boundary_keeps_full_timestamp(self):
        def result(duration,words):
            return {'engine':ENGINE,'speech_us':[[0,duration]],'words':words}
        word={'word':'sınırdaki','start':1900000,'end':2200000,'probability':.95}
        local=dict(word,start=900000,end=1200000)
        with patch('speech_analysis.CHUNK_US',2*US),patch('speech_analysis._cache_read',side_effect=[
            result(3*US,[word]),result(4*US,[local]),result(3*US,[])]):
            analysis=analyze_speech(self.p,2,Settings(auto_jump_cut=True,next_speech_padding=.1),
                self.cancel,transcribe=True,suggest=False,cache=self.root/'cache')
        self.assertEqual(analysis.transcript,[word])

    def test_export_does_not_repeat_confirmed_empty_repeat_analysis(self):
        with patch('export_pipeline.analyze_speech',side_effect=AssertionError('Unnecessary inference')):
            packet=export_copy(self.p,2,[],self.cancel,mark_repeats=True,proposals=[],
                index=self.root/'none',check_running=False)
        self.assertEqual(packet['marker_count'],0)

    def test_export_reuses_already_detected_repeat_proposals(self):
        words=[{'word':'Merhaba.','start':0,'end':US,'probability':.95}]
        with patch('export_pipeline.suggest_edits',side_effect=AssertionError('Duplicate repeat analysis')):
            packet=export_copy(self.p,2,[],self.cancel,caption_words=words,proposals=[],
                index=self.root/'none',check_running=False)
        self.assertEqual(packet['marker_count'],0)

    def test_regenerated_captions_replace_only_the_previous_generated_track(self):
        data=copy.deepcopy(self.p.data)
        add_caption_track(data,[{'start':0,'end':US,'text':'Eski altyazı.'}])
        user_track=copy.deepcopy(data['tracks'][-1]);user_track['name']='Kullanıcının başlığı'
        shared_material_id=user_track['segments'][0]['material_id'];data['tracks'].append(user_track)
        add_caption_track(data,[{'start':US,'end':2*US,'text':'Yeni altyazı.'}])
        self.assertEqual(sum(t.get('name')=='SesPusula · Otomatik altyazı' for t in data['tracks']),1)
        self.assertIn(user_track,data['tracks'])
        self.assertTrue(any(m['id']==shared_material_id for m in data['materials']['texts']))

    def test_changed_copy_does_not_keep_an_old_tool_generated_srt(self):
        (self.p.folder/'otomatik_altyazi.srt').write_text('outdated timing',encoding='utf-8')
        out=create_copy(self.p,[Cut(US,2*US)],self.cancel,index=self.root/'none',check_running=False)
        self.assertFalse((out/'otomatik_altyazi.srt').exists())
        self.assertTrue((self.p.folder/'otomatik_altyazi.srt').exists())

    def test_repeat_markers_do_not_multiply_when_processing_a_copy(self):
        data=copy.deepcopy(self.p.data)
        marker={'start':US,'end':2*US,'title':'Tekrar olabilir · aynı cümle'}
        add_repeat_markers(data,[marker],[],self.p.duration)
        add_repeat_markers(data,[marker],[],self.p.duration)
        self.assertEqual(len(data['time_marks']['mark_items']),1)

    def test_overlapping_word_times_do_not_shorten_caption_before_word_end(self):
        words=[{'word':'Uzun','start':0,'end':1500000},{'word':'kelime','start':200000,'end':500000}]
        cues=build_captions(words,[],self.p.duration)
        self.assertEqual(cues[0]['end'],1500000)

    def test_timeline_folder_id_cannot_escape_project_directory(self):
        data=copy.deepcopy(self.p.data);data['id']='../../outside'
        self.p.file.write_text(json.dumps(data),encoding='utf-8')
        with self.assertRaises(UserError):Project(self.p.folder)

    def test_cut_cache_updates_after_edit_restore_and_failed_manual_cut(self):
        s=Settings(auto_jump_cut=True,next_speech_padding=.1)
        session=ReviewSession(self.p,2,s,[Cut(US,2*US)],self.root/'reviews')
        self.assertEqual(session.selected_cuts(),[Cut(US,2*US)])
        returned=session.selected_cuts();returned.clear()
        self.assertEqual(session.selected_cuts(),[Cut(US,2*US)])
        session.mark(0,'wrong');self.assertEqual(session.selected_cuts(),[])
        session.edit(0,2*US,3*US);self.assertEqual(session.selected_cuts(),[Cut(2*US,3*US)])
        with self.assertRaises(UserError):session.add_manual(0,self.p.duration,'entire recording')
        self.assertEqual(session.selected_cuts(),[Cut(2*US,3*US)])
        session.save();session.mark(0,'wrong');session.restore()
        self.assertEqual(session.selected_cuts(),[Cut(2*US,3*US)])

    def test_cache_cleanup_tolerates_files_removed_by_another_instance(self):
        cache=self.root/'cache';cache.mkdir()
        file=cache/('a'*64+'-speech.json');file.write_text('{}')
        original=Path.stat
        hits=[0]
        def transient_stat(path,*args,**kwargs):
            if path==file:
                hits[0]+=1
                if hits[0]>1:raise FileNotFoundError(str(path))
            return original(path,*args,**kwargs)
        with patch.object(Path,'stat',transient_stat):prune_cache(cache,limit=0)
        self.assertTrue(file.exists())


if __name__=='__main__':unittest.main()
