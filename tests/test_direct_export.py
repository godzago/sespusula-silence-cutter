import tempfile
import threading
import unittest
from pathlib import Path

from captions import build_captions
from export_pipeline import export_copy
from review import ReviewSession
from silence_core import US, Cut, Settings, Project, create_copy
from speech_analysis import suggest_edits
from timeline_markers import repeat_markers
from test_update import fixture


class DirectExportTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='sespusula-direct-export-')
        self.root=Path(self.temp.name);self.cancel=threading.Event();self.p=fixture(self.root/'source')
    def tearDown(self):self.temp.cleanup()

    def proposals(self):
        return [{'kind':'filler','start':5*US,'end':6*US,'text':'yani'},
                {'kind':'retake','start':8*US,'end':10*US,'text':'Tekrar eden konuşma.',
                 'comparison_start':18*US,'comparison_end':20*US,'comparison':'Tekrar eden konuşma.','score':.97}]

    def test_silence_selected_without_approval_repeats_never_deleted(self):
        review=ReviewSession(self.p,2,Settings(auto_jump_cut=True),[Cut(US,2*US)],self.root/'reviews',proposals=self.proposals())
        self.assertNotIn('pending',review.decisions)
        self.assertEqual(review.selected_cuts(),[Cut(US,2*US)])
        self.assertEqual([c['kind'] for c in review.candidates],['silence','retake'])
        review.mark(1,'correct');self.assertEqual(review.decisions[1],'marker')
        self.assertEqual(review.selected_cuts(),[Cut(US,2*US)])
        review.save()
        restored=ReviewSession(self.p,2,Settings(auto_jump_cut=True),[Cut(US,2*US)],self.root/'reviews',proposals=self.proposals())
        self.assertTrue(restored.restore());self.assertEqual(restored.selected_cuts(),[Cut(US,2*US)])

    def test_repeat_detection_returns_two_markers_without_filler_candidates(self):
        words=[{'word':w,'start':i*500000,'end':i*500000+400000,'probability':.95}
               for i,w in enumerate(['aynı','cümleyi','tekrar','söyledim.','aynı','cümleyi','tekrar','söyledim.'])]
        proposals=suggest_edits(words,30)
        self.assertTrue(proposals)
        self.assertTrue(all(p['kind']=='retake' and p['marker_only'] for p in proposals))
        marks=repeat_markers(proposals)
        self.assertEqual({m['start'] for m in marks},{0,2*US})

    def test_marker_times_follow_cuts_and_copy_can_be_loaded_again(self):
        out=create_copy(self.p,[Cut(US,3*US)],self.cancel,index=self.root/'none',check_running=False,markers=repeat_markers(self.proposals()))
        new=Project(out);self.assertEqual(new.compatibility(),[])
        points=new.data['time_marks']['mark_items']
        self.assertEqual([m['time_range']['start'] for m in points],[6*US,16*US])
        self.assertEqual(new.duration,58*US)
        self.assertTrue(all(m['time_range']['duration']==0 for m in points))

    def test_existing_markers_preserved_retimed_and_removed_with_deleted_content(self):
        self.p.data['time_marks']={'id':'existing','mark_items':[
            {'id':'before','title':'önce','color':'#FFFFFF','time_range':{'start':0,'duration':0}},
            {'id':'gone','title':'kesildi','color':'#FFFFFF','time_range':{'start':2*US,'duration':0}},
            {'id':'after','title':'sonra','color':'#FFFFFF','time_range':{'start':4*US,'duration':0}}]}
        out=create_copy(self.p,[Cut(US,3*US)],self.cancel,index=self.root/'none',check_running=False)
        points=Project(out).data['time_marks']['mark_items']
        self.assertEqual([m['id'] for m in points],['before','after'])
        self.assertEqual(points[1]['time_range']['start'],2*US)

    def test_stale_captions_refresh_on_export_without_another_approval(self):
        words=[{'word':'Merhaba.','start':0,'end':US,'probability':.95},
               {'word':'Sonra.','start':4*US,'end':5*US,'probability':.95}]
        old=build_captions(words,[],self.p.duration)
        packet=export_copy(self.p,2,[Cut(US,3*US)],self.cancel,caption_enabled=True,
            captions_current=False,caption_words=words,caption_cues=old,mark_repeats=False,
            index=self.root/'none',check_running=False)
        self.assertTrue(packet['captions_refreshed'])
        self.assertEqual(packet['caption_cues'][-1]['start'],2*US)
        self.assertEqual(Project(packet['path']).duration,58*US)

    def test_no_cuts_copy_supported_and_current_caption_edits_preserved(self):
        cues=[{'start':0,'end':US,'text':'Elle düzeltilen altyazı.'}]
        packet=export_copy(self.p,2,[],self.cancel,caption_enabled=True,captions_current=True,
            caption_cues=cues,mark_repeats=False,index=self.root/'none',check_running=False)
        self.assertFalse(packet['captions_refreshed']);self.assertEqual(packet['caption_cues'],cues)
        empty=export_copy(self.p,2,[],self.cancel,mark_repeats=False,index=self.root/'none',check_running=False)
        self.assertEqual(Project(empty['path']).duration,self.p.duration)


if __name__=='__main__':unittest.main()
