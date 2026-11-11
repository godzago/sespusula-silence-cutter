import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from app import App
from silence_core import US, Settings, Cut
from review import ReviewSession
from speech_analysis import AnalysisResult
from test_update import fixture


class GuiTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='sespusula-gui-test-')
        self.root=Path(self.temp.name)
        with patch.object(App,'refresh',lambda self:None),patch('app.load_preferences',return_value={}):
            self.app=App()
        self.app.load_project(fixture(self.root/'source').folder)
        self.app.tracks.current(2)
        self.app.update()
    def tearDown(self):
        self.app.finish_close();self.temp.cleanup()

    def dialogs(self):return [w for w in self.app.winfo_children() if w.winfo_class()=='Toplevel']
    def descendants(self,w):
        result=[]
        for child in w.winfo_children():result.append(child);result.extend(self.descendants(child))
        return result

    def test_layout_small_and_large(self):
        for size in ('1120x900','940x700'):
            self.app.geometry(size);self.app.update()
            for widget in (self.app.copy_btn,self.app.analyze_btn,self.app.tree,self.app.caption_btn,self.app.caption_toggle):
                self.assertTrue(widget.winfo_viewable(),(size,widget))
                self.assertLessEqual(widget.winfo_rootx()+widget.winfo_width(),self.app.winfo_rootx()+self.app.winfo_width()+2,(size,widget))
                self.assertLessEqual(widget.winfo_rooty()+widget.winfo_height(),self.app.winfo_rooty()+self.app.winfo_height()+2,(size,widget))

    def test_full_timeline_automatic_settings_ignore_old_preferences(self):
        self.app.preferences.update(audio_settings={'start':30,'end':31,'minimum':60,'padding':4},analysis_mode='level')
        settings=self.app.get_settings()
        self.assertTrue(settings.auto_jump_cut)
        self.assertEqual(settings.validate(self.app.project.duration),(0,self.app.project.duration))
        self.assertFalse(hasattr(self.app,'vars'))
        labels=[w.cget('text') for w in self.descendants(self.app) if w.winfo_class()=='TLabel']
        self.assertNotIn('Başlangıç (sn)',labels);self.assertNotIn('Bitiş (sn)',labels)

    def test_prealigned_project_analysis_needs_no_sync_step(self):
        original=self.app.project.data.copy()
        result=AnalysisResult([Cut(2*US,3*US)],[],[],{'engine':'test'},{})
        with patch('app.save_settings'),patch('app.analyze_speech',return_value=result) as analyze:
            with patch.object(self.app,'job',side_effect=lambda kind,fn:self.app.events.put(('done',kind,fn()))):
                self.app.start_analysis()
            self.app.after_cancel(self.app._drain_after);self.app.drain();self.app.update()
            self.assertEqual(analyze.call_args.args[1],2)
        self.assertEqual(self.app.project.data,original)
        self.assertEqual(self.app.review_session.selected_cuts(),[Cut(2*US,3*US)])
        self.assertNotIn('disabled',self.app.copy_btn.state())

    def test_sync_controls_removed_and_caption_generation_available(self):
        self.assertFalse(hasattr(self.app,'start_sync'))
        self.assertFalse(hasattr(self.app,'sync_btn'))
        self.assertFalse(hasattr(self.app,'webcam'))
        result=AnalysisResult([],[],[{'word':'Merhaba.','start':0,'end':US}],{}, {})
        with patch('app.analyze_speech',return_value=result) as analyze:
            with patch.object(self.app,'job',side_effect=lambda kind,fn:self.app.events.put(('done',kind,fn()))):
                self.app.start_captions()
            self.app.after_cancel(self.app._drain_after);self.app.drain();self.app.update()
        self.assertEqual(analyze.call_args.args[1],2)
        self.assertEqual(len(self.dialogs()),0)
        self.assertTrue(self.app.caption_enabled);self.assertTrue(self.app.captions_ready())


    def test_caption_editor_save_and_stale_after_cut_change(self):
        self.app.caption_words=[{'word':'Merhaba','start':0,'end':500000},
                                {'word':'dünya.','start':600000,'end':US}]
        self.app.show_captions();self.app.update();dialog=self.dialogs()[0]
        widgets=self.descendants(dialog)
        editor=next(w for w in widgets if w.winfo_class()=='Text')
        editor.delete('1.0','end');editor.insert('1.0','Düzeltilmiş altyazı.')
        save=next(w for w in widgets if w.winfo_class()=='TButton' and w.cget('text')=='Kaydet ve kullan')
        self.assertLessEqual(save.winfo_rooty()+save.winfo_height(),dialog.winfo_rooty()+dialog.winfo_height())
        save.invoke();self.app.update()
        self.assertTrue(self.app.caption_enabled);self.assertTrue(self.app.captions_ready())
        self.assertEqual(self.app.caption_cues[0]['text'],'Düzeltilmiş altyazı.')
        self.assertNotIn('disabled',self.app.copy_btn.state())
        self.app.review_session=ReviewSession(self.app.project,2,Settings(),[Cut(2*US,3*US)],self.root/'reviews')
        self.app.update_buttons()
        self.assertFalse(self.app.captions_ready());self.assertNotIn('disabled',self.app.copy_btn.state())
        self.assertEqual(self.app.caption_btn.cget('text'),'Altyazı · otomatik')

    def test_caption_disable_preserves_review(self):
        self.app.review_session=ReviewSession(self.app.project,2,Settings(),[Cut(2*US,3*US)],self.root/'reviews')
        review=self.app.review_session
        self.app.caption_words=[{'word':'Merhaba.','start':0,'end':US}]
        self.app.show_captions();self.app.update();dialog=self.dialogs()[0]
        disable=next(w for w in self.descendants(dialog) if w.winfo_class()=='TButton' and w.cget('text')=='Altyazıyı kapat')
        disable.invoke();self.app.update()
        self.assertFalse(self.app.caption_enabled);self.assertIs(self.app.review_session,review)

    def test_stale_caption_can_be_disabled_without_regeneration(self):
        self.app.caption_enabled=True;self.app.caption_cues=[];self.app.update_buttons()
        self.app.caption_toggle.invoke();self.app.update()
        self.assertFalse(self.app.caption_enabled)

    def test_analysis_with_repeat_marker_is_immediately_exportable_without_approval(self):
        self.app.pending_track=2;self.app.pending_settings=self.app.get_settings()
        result=AnalysisResult([Cut(US,2*US)],[{'kind':'retake','start':3*US,'end':4*US,'text':'tekrar'}],[],{}, {})
        self.app.events.put(('done','analysis',result))
        self.app.after_cancel(self.app._drain_after);self.app.drain();self.app.update()
        self.assertEqual(self.app.review_session.decisions,['correct','marker'])
        self.assertEqual(self.app.review_session.selected_cuts(),[Cut(US,2*US)])
        self.assertNotIn('disabled',self.app.copy_btn.state())
        self.assertNotIn('onay bekliyor',self.app.summary.get().lower())
        self.assertFalse(hasattr(self.app,'reset_btn'))

    def test_copy_click_dispatches_export_when_caption_times_are_stale(self):
        self.app.review_session=ReviewSession(self.app.project,2,self.app.get_settings(),[Cut(US,2*US)],self.root/'reviews')
        self.app.enabled=self.app.review_session.enabled;self.app.caption_enabled=True
        self.app.caption_words=[{'word':'Merhaba.','start':0,'end':500000,'probability':.95}]
        self.app.caption_signature='old';self.app.update_buttons()
        with patch('app.export_copy') as export:
            with patch.object(self.app,'job',side_effect=lambda kind,fn:fn()):self.app.write_copy()
        self.assertTrue(export.called)
        self.assertFalse(export.call_args.kwargs['captions_current'])
        self.assertTrue(export.call_args.kwargs['caption_enabled'])
        self.assertEqual(export.call_args.args[2],[Cut(US,2*US)])

    def test_caption_signature_cache_is_reused_and_invalidated_by_cut_changes(self):
        review=ReviewSession(self.app.project,2,self.app.get_settings(),[Cut(US,2*US)],self.root/'reviews')
        self.app.review_session=review
        with patch('app.json.dumps',wraps=json.dumps) as serialize:
            first=self.app.current_caption_signature()
            for _ in range(10):self.assertEqual(self.app.current_caption_signature(),first)
            self.assertEqual(serialize.call_count,1)
            review.mark(0,'wrong')
            self.assertNotEqual(self.app.current_caption_signature(),first)
            self.assertEqual(serialize.call_count,2)


if __name__=='__main__':unittest.main()
