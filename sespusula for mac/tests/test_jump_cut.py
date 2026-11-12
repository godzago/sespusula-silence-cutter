from dataclasses import replace
from pathlib import Path
import unittest

from jump_cut import automatic_jump_cuts
from silence_core import Cut, Settings, AnalysisClip, US, UserError
from captions import build_captions


class JumpCutTests(unittest.TestCase):
    def clip(self,start=0,end=10*US):return AnalysisClip(Path('unused.wav'),0,start,end)
    def run_profile(self,speech,words=(),fps=30,settings=None):
        return automatic_jump_cuts([self.clip()],{0:speech},list(words),fps,settings or Settings(auto_jump_cut=True))

    def test_long_pause_shortened_short_pause_kept_and_speech_protected(self):
        speech=[Cut(0,US),Cut(1_200_000,2*US),Cut(4*US,10*US)]
        cuts,profile=self.run_profile(speech)
        self.assertEqual(len(cuts),1)
        self.assertGreater(cuts[0].start,2*US);self.assertLess(cuts[0].end,4*US)
        self.assertGreaterEqual(2*US-cuts[0].duration,round(profile['retained_pause_seconds']*US))
        for cut in cuts:
            for span in speech:self.assertTrue(cut.end<=span.start or cut.start>=span.end)

    def test_pause_cadence_adapts_and_long_dead_air_cannot_dominate(self):
        def spans(gap):
            result=[];cursor=0
            for i in range(8):result.append(Cut(cursor,cursor+400_000));cursor+=400_000+gap
            return result,cursor
        fast,end1=spans(150_000);slow,end2=spans(500_000)
        _,a=automatic_jump_cuts([self.clip(end=end1)],{0:fast},[],60,Settings(auto_jump_cut=True))
        _,b=automatic_jump_cuts([self.clip(end=end2)],{0:slow},[],60,Settings(auto_jump_cut=True))
        self.assertTrue(a['cadence_adapted']);self.assertTrue(b['cadence_adapted'])
        self.assertLess(a['retained_pause_seconds'],b['retained_pause_seconds'])
        self.assertLess(a['minimum_pause_seconds'],b['minimum_pause_seconds'])
        _,c=automatic_jump_cuts([self.clip(end=end1+30*US)],{0:fast},[],60,Settings(auto_jump_cut=True))
        self.assertEqual(a['minimum_pause_seconds'],c['minimum_pause_seconds'])

    def test_sentence_end_keeps_more_space_when_transcript_available(self):
        speech=[Cut(0,US),Cut(3*US,10*US)]
        plain,_=self.run_profile(speech)
        sentence,profile=self.run_profile(speech,[{'word':'Bitti.','start':0,'end':US,'probability':.95}])
        self.assertLess(sentence[0].duration,plain[0].duration)
        self.assertGreaterEqual(2*US-sentence[0].duration,320_000)
        self.assertEqual(profile['sentence_gaps'],1)

    def test_no_upper_gap_limit_or_legacy_range_and_cut_values(self):
        settings=Settings(auto_jump_cut=True,start=5,end=6,maximum=.6,minimum=60,padding=4,lead_padding=4)
        self.assertEqual(settings.validate(10*US),(0,10*US))
        cuts,_=self.run_profile([Cut(0,US),Cut(9*US,10*US)],settings=settings)
        self.assertEqual(len(cuts),1);self.assertGreater(cuts[0].duration,7*US)

    def test_leading_trailing_silence_and_frame_rounding(self):
        for fps in (24,29.97,30,60):
            speech=[Cut(2*US,8*US)]
            cuts,_=self.run_profile(speech,fps=fps)
            self.assertEqual(len(cuts),2)
            self.assertEqual(cuts[0].start,0)
            self.assertLessEqual(abs(cuts[-1].end-10*US),US/fps)
            for cut in cuts:
                self.assertAlmostEqual(cut.start*fps/US,round(cut.start*fps/US),delta=.0001)
                self.assertAlmostEqual(cut.end*fps/US,round(cut.end*fps/US),delta=.0001)

    def test_clip_gaps_not_invented_and_captions_follow_global_cuts(self):
        clips=[self.clip(0,4*US),self.clip(6*US,10*US)]
        cuts,_=automatic_jump_cuts(clips,{0:[Cut(0,US),Cut(3*US,4*US)],1:[Cut(6*US,7*US),Cut(9*US,10*US)]},[],30,Settings(auto_jump_cut=True))
        self.assertEqual(len(cuts),2)
        self.assertTrue(all(c.end<=4*US or c.start>=6*US for c in cuts))
        cues=build_captions([{'word':'Önce.','start':0,'end':US},{'word':'Sonra.','start':9*US,'end':10*US}],cuts,10*US)
        self.assertEqual(cues[-1]['end'],10*US-sum(c.duration for c in cuts))

    def test_no_speech_never_deletes_entire_recording(self):
        with self.assertRaises(UserError):self.run_profile([])

    def test_direct_rule_cuts_to_100ms_before_next_speech_without_tail_or_sentence_pause(self):
        settings=Settings(auto_jump_cut=True,next_speech_padding=.1)
        cuts,profile=self.run_profile([Cut(0,US),Cut(2*US,10*US)],
            [{'word':'Bitti.','end':US,'probability':1.}],settings=settings)
        self.assertEqual(cuts,[Cut(US,1_900_000)])
        self.assertEqual(profile['word_tail_seconds'],0.)
        self.assertIsNone(profile['sentence_pause_seconds'])

    def test_direct_rule_removes_small_silences_and_primary_clip_gaps(self):
        clips=[self.clip(US,3*US),self.clip(6*US,9*US)]
        cuts,_=automatic_jump_cuts(clips,{0:[Cut(US,2*US),Cut(2_200_000,3*US)],1:[Cut(6*US,9*US)]},[],
            30,Settings(auto_jump_cut=True,next_speech_padding=.1),duration=10*US)
        self.assertEqual(cuts,[Cut(0,900000),Cut(2*US,2_100_000),Cut(3*US,5_900_000),Cut(9*US,10*US)])

    def test_direct_rule_both_units_respect_frame_safety(self):
        for lead in (.1,.0001):
            for fps in (24,29.97,30,60):
                cuts,_=self.run_profile([Cut(0,US),Cut(2*US,10*US)],fps=fps,
                    settings=Settings(auto_jump_cut=True,next_speech_padding=lead))
                self.assertGreaterEqual(2*US-cuts[0].end,round(lead*US)-1)
                self.assertLess(2*US-cuts[0].end,round(lead*US)+US/fps+1)


if __name__=='__main__':unittest.main()
