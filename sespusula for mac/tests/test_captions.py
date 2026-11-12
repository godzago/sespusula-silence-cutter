import copy
import json
import tempfile
import threading
import unittest
from pathlib import Path

from captions import build_captions, validate_captions, wrap_caption, srt_text, add_caption_track
from silence_core import US, Cut, UserError, Project, create_copy, digest, Cancelled
from test_update import fixture


def word(text,start,end):return {'word':text,'start':round(start*US),'end':round(end*US),'probability':.95}


class CaptionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='sespusula-caption-test-')
        self.root=Path(self.temp.name);self.cancel=threading.Event()
    def tearDown(self):self.temp.cleanup()

    def test_cut_words_removed_and_later_words_retimed(self):
        words=[word('Merhaba',0,.5),word('bunu',1.1,1.5),word('sil',1.6,1.9),word('dünya.',2.2,2.8)]
        cues=build_captions(words,[Cut(US,2*US)],3*US,30)
        self.assertEqual([c['text'] for c in cues],['Merhaba','dünya.'])
        self.assertEqual(cues[1]['start'],1_200_000)
        self.assertEqual(cues[1]['end'],1_800_000)
        self.assertNotIn('bunu',srt_text(cues))

    def test_partial_word_removed_and_cut_boundary_words_preserved(self):
        words=[word('önce',0,1),word('yarım',.9,1.2),word('sonra',2,2.5)]
        cues=build_captions(words,[Cut(US,2*US)],3*US,30)
        self.assertEqual([c['text'] for c in cues],['önce','sonra'])
        self.assertEqual(cues[1]['start'],US)

    def test_line_limits_sentence_gaps_and_unicode(self):
        words=[word(f'kelime{i}',i*.3,i*.3+.25) for i in range(30)]
        cues=build_captions(words,[],10*US,width=28)
        self.assertGreater(len(cues),3)
        self.assertTrue(all(len(c['text'].splitlines())<=2 for c in cues))
        self.assertTrue(all(len(line)<=28 for c in cues for line in c['text'].splitlines()))
        self.assertEqual(' '.join(' '.join(c['text'].split()) for c in cues),' '.join(w['word'] for w in words))
        data={'duration':3*US,'materials':{},'tracks':[]}
        add_caption_track(data,[{'start':0,'end':US,'text':'İğne, çığ ve şüphe 😊'}])
        content=json.loads(data['materials']['texts'][0]['content'])
        self.assertEqual(content['styles'][0]['range'][1],len(content['text'].encode('utf-16-le'))//2)
        self.assertEqual(data['tracks'][0]['type'],'text')

    def test_srt_times_and_invalid_cues(self):
        cues=[{'start':3_661_020_000,'end':3_662_030_000,'text':'Türkçe altyazı.'}]
        self.assertIn('01:01:01,020 --> 01:01:02,030',srt_text(cues))
        for invalid in ([],[{'start':0,'end':US,'text':''}],
                        [{'start':0,'end':2*US,'text':'a'},{'start':US,'end':3*US,'text':'b'}],
                        [{'start':False,'end':US,'text':'a'}],[{'start':0,'end':4*US,'text':'a'}]):
            with self.assertRaises(UserError):validate_captions(invalid,3*US)
        with self.assertRaises(UserError):build_captions([{'word':'a','start':0,'end':float('inf')}],[],US)
        with self.assertRaises(UserError):wrap_caption('a'*100,28)

    def test_subtitle_only_copy_editable_text_srt_and_source_unchanged(self):
        p=fixture(self.root/'source');before={f:digest(f) for f in p.hashes}
        cues=[{'start':0,'end':US,'text':'Merhaba dünya.'}]
        out=create_copy(p,[],self.cancel,index=self.root/'missing',check_running=False,captions=cues)
        new=Project(out)
        self.assertEqual(new.duration,p.duration);self.assertEqual(new.compatibility(),[])
        self.assertEqual(new.data['tracks'][-1]['type'],'text')
        content=json.loads(new.data['materials']['texts'][0]['content'])
        self.assertEqual(content['text'],'Merhaba dünya.')
        self.assertTrue((out/'otomatik_altyazi.srt').read_text(encoding='utf-8-sig').startswith('1\n00:00:00,000'))
        self.assertEqual(before,{f:digest(f) for f in p.hashes})

    def test_prealigned_cut_copy_mirror_and_caption_end_within_output(self):
        p=fixture(self.root/'source')
        cuts=[Cut(US,2*US)]
        cues=build_captions([word('başta',0,.5),word('bitti.',57,58)],cuts,p.duration)
        # A mirrored saved timeline must receive the generated text track too.
        p.data['id']='timeline'
        timeline=p.folder/'Timelines/timeline';timeline.mkdir(parents=True)
        (p.folder/'Timelines/project.json').write_text(json.dumps({'main_timeline_id':'timeline','timelines':[{'id':'timeline'}]}))
        (timeline/'draft_content.json').write_bytes(p.file.read_bytes())
        mirrored=Project(p.folder)
        out=create_copy(mirrored,cuts,self.cancel,index=self.root/'missing',check_running=False,captions=cues)
        new=Project(out)
        self.assertEqual(new.duration,59*US)
        self.assertEqual(len(new.content_files),2)
        self.assertEqual(json.loads(new.content_files[1].read_text(encoding='utf-8')),new.data)
        self.assertEqual(new.data['tracks'][-1]['segments'][-1]['target_timerange']['start'],56*US)

    def test_disabled_captions_dont_add_text_and_cancel_doesnt_publish(self):
        p=fixture(self.root/'source')
        out=create_copy(p,[Cut(US,2*US)],self.cancel,index=self.root/'missing',check_running=False)
        self.assertFalse(any(t['type']=='text' for t in Project(out).data['tracks']))
        self.assertFalse((out/'otomatik_altyazi.srt').exists())
        self.cancel.set()
        with self.assertRaises(Cancelled):
            create_copy(p,[],self.cancel,check_running=False,captions=[{'start':0,'end':US,'text':'test'}])
        self.assertEqual(len(list(self.root.glob('Sessizlik-*'))),1)


if __name__=='__main__':unittest.main()
