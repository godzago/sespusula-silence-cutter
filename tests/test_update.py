import copy
import hashlib
import json
import random
import tempfile
import threading
import unittest
import wave
from pathlib import Path

import numpy as np

from silence_core import (Project, US, Cut, Settings, UserError, Cancelled, edit_timeline,
                          create_copy, silence_cut, preview, digest, map_time)
from speech_analysis import non_speech_cuts
from review import ReviewSession, save_settings, load_preferences


def write_wav(path, samples, rate=8000):
    with wave.open(str(path),'wb') as wav:
        wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(rate)
        wav.writeframes((np.clip(samples,-.99,.99)*32767).astype('<i2').tobytes())


def fixture(root, seconds=60):
    root.mkdir(exist_ok=True)
    materials={'videos':[],'audios':[]};tracks=[]
    for i,kind in enumerate(('videos','videos','audios')):
        path=root/f'{i}.wav'
        write_wav(path,np.zeros(8000*seconds,dtype=np.float32))
        materials[kind].append({'id':f'm{i}','type':'video' if kind=='videos' else 'audio',
                                'path':str(path),'name':f'recording-{i}','has_audio':True})
        tracks.append({'type':'video' if i<2 else 'audio','segments':[{
            'id':f's{i}','material_id':f'm{i}','target_timerange':{'start':0,'duration':seconds*US},
            'source_timerange':{'start':0,'duration':seconds*US},'volume':.5,'last_nonzero_volume':.5}]})
    data={'id':'timeline','version':360000,'duration':seconds*US,'fps':30,'tracks':tracks,'materials':materials}
    (root/'draft_content.json').write_text(json.dumps(data),encoding='utf-8')
    (root/'draft_meta_info.json').write_text(json.dumps({'draft_name':'test'}),encoding='utf-8')
    return Project(root)


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='sespusula-update-test-')
        self.root=Path(self.temp.name);self.cancel=threading.Event()
    def tearDown(self):self.temp.cleanup()

    def test_asymmetric_word_protection_and_small_cuts(self):
        s=Settings(padding=.18,lead_padding=.07,minimum_cut=.1)
        c=silence_cut(US,2*US,s,100)
        self.assertEqual(c,Cut(1_180_000,1_930_000))
        self.assertIsNone(silence_cut(0,500_000,Settings(padding=.24,minimum_cut=.08),30))
        self.assertEqual(non_speech_cuts(0,3*US,[Cut(0,US),Cut(2*US,3*US)],s,100),[c])

    def test_settings_roundtrip(self):
        path=self.root/'preferences.json';s=Settings(lead_padding=.08,minimum_cut=.12)
        save_settings(s,path)
        self.assertEqual(load_preferences(path)['audio_settings']['lead_padding'],.08)
        for settings in (Settings(lead_padding=-1),Settings(minimum_cut=float('nan'))):
            with self.assertRaises(UserError):settings.validate(US)

    def test_prealigned_three_tracks_keep_source_offsets_gaps_and_mix(self):
        p=fixture(self.root/'source');before=copy.deepcopy(p.data)
        offsets=[2*US,5*US,9*US];volumes=[0.,.12,1.]
        for i,track in enumerate(p.data['tracks']):
            seg=track['segments'][0];seg['volume']=volumes[i]
            seg['source_timerange']['start']=offsets[i]
            if i==1:
                # Pre-aligned footage can have different coverage. Do not crop to common overlap.
                seg['target_timerange']={'start':2*US,'duration':56*US}
                seg['source_timerange']['duration']=56*US
        original=copy.deepcopy(p.data)
        cuts=[Cut(3*US,4*US),Cut(7*US,8*US)]
        edited=edit_timeline(p,cuts)
        self.assertEqual(edited['duration'],58*US)
        self.assertEqual([t['segments'][0]['target_timerange']['start'] for t in edited['tracks']],[0,2*US,0])
        self.assertEqual([t['segments'][0]['source_timerange']['start'] for t in edited['tracks']],offsets)
        for i,track in enumerate(edited['tracks']):
            for seg in track['segments']:self.assertEqual(seg['volume'],volumes[i])
        for i in (0,2):
            self.assertEqual([(s['target_timerange']) for s in edited['tracks'][i]['segments']],
                             [{'start':0,'duration':3*US},{'start':3*US,'duration':3*US},{'start':6*US,'duration':52*US}])
        self.assertEqual(p.data,original)

    def test_prealigned_multiple_clips_supported_and_only_main_audio_analyzed(self):
        from silence_core import analyze
        p=fixture(self.root/'source',seconds=6)
        # Other recordings are continuously noisy; clean microphone has one central speech-like tone.
        t=np.arange(8000*6)/8000
        for i in (0,1):write_wav(p.folder/f'{i}.wav',.2*np.sin(2*np.pi*440*t))
        clean=.2*np.sin(2*np.pi*440*t);clean[(t<2)|(t>=4)]=0
        write_wav(p.folder/'2.wav',clean)
        seg=p.data['tracks'][0]['segments'][0]
        second=copy.deepcopy(seg);second['id']='second'
        seg['target_timerange']['duration']=3*US;seg['source_timerange']['duration']=3*US
        second['target_timerange']={'start':3*US,'duration':3*US}
        second['source_timerange']={'start':3*US,'duration':3*US}
        p.data['tracks'][0]['segments'].append(second)
        cuts=analyze(p,2,Settings(minimum=.5,padding=.1,lead_padding=.1),self.cancel)
        self.assertEqual(len(cuts),2)
        self.assertLessEqual(cuts[0].end,2*US);self.assertGreaterEqual(cuts[1].start,4*US)
        edited=edit_timeline(p,cuts)
        self.assertEqual(len(edited['tracks']),3)
        self.assertEqual(edited['duration'],p.duration-sum(c.duration for c in cuts))


    def test_copy_with_cuts_review_restore_and_preview(self):
        p=fixture(self.root/'source')
        settings=Settings();cuts=[Cut(US,2*US)]
        review=ReviewSession(p,2,settings,cuts,self.root/'reviews')
        review.mark(0,'correct');review.save()
        restored=ReviewSession(p,2,settings,cuts,self.root/'reviews')
        self.assertTrue(restored.restore());self.assertEqual(restored.selected_cuts(),cuts)
        out=create_copy(p,cuts,self.cancel,index=self.root/'none',check_running=False,review=review.payload())
        self.assertEqual(Project(out).duration,59*US)
        preview(p,2,Cut(0,US),self.root/'preview.wav',self.cancel,full=True)
        with wave.open(str(self.root/'preview.wav')) as wav:self.assertEqual(wav.getnframes(),22050)


    def test_source_change_rejected(self):
        p=fixture(self.root/'source');(p.folder/'draft_meta_info.json').write_text('{}')
        with self.assertRaises(UserError):create_copy(p,[Cut(US,2*US)],self.cancel,index=self.root/'missing',check_running=False)


    def test_optimized_timeline_matches_original_algorithm_randomized(self):
        rng=random.Random(2026);p=fixture(self.root/'source',seconds=100)
        for case in range(120):
            cuts=[Cut(i*US+100_000,i*US+rng.randint(200_000,700_000)) for i in rng.sample(range(1,99),rng.randint(1,40))]
            cuts=sorted(cuts)
            segments=[]
            for j in range(25):
                a=rng.randrange(0,99*US);b=min(100*US,a+rng.randint(50_000,8*US))
                segments.append({'id':str(j),'material_id':'m0','target_timerange':{'start':a,'duration':b-a},
                                 'source_timerange':{'start':3*US,'duration':b-a}})
            p.data['tracks'][0]['segments']=segments
            edited=edit_timeline(p,cuts)
            expected=[]
            for seg in segments:
                a=seg['target_timerange']['start'];b=a+seg['target_timerange']['duration'];pieces=[(a,b)]
                for cut in cuts:
                    pieces=[(x,y) for x,y in pieces if y<=cut.start or x>=cut.end]+[
                        pair for x,y in pieces if x<cut.end and y>cut.start
                        for pair in ((x,min(y,cut.start)),(max(x,cut.end),y)) if pair[1]>pair[0]]
                for x,y in sorted(pieces):expected.append((map_time(x,cuts),y-x,3*US+x-a))
            actual=[(s['target_timerange']['start'],s['target_timerange']['duration'],s['source_timerange']['start'])
                    for s in edited['tracks'][0]['segments']]
            self.assertEqual(sorted(actual),sorted(expected),case)


if __name__=='__main__':unittest.main()
