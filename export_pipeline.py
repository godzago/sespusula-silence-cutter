"""Prepare captions and repeat markers from the final cuts, then write one project copy."""
from captions import build_captions, line_width
from silence_core import Settings, UserError, create_copy, load_json
from speech_analysis import analyze_speech, suggest_edits
from timeline_markers import repeat_markers


def export_copy(project,track,cuts,cancel,progress=lambda _:None,*,caption_enabled=False,
                captions_current=False,caption_words=None,caption_cues=None,mark_repeats=True,
                proposals=None,review=None,**copy_options):
    project.assert_unchanged()
    repeat_analysis_complete=proposals is not None
    words=list(caption_words or []);proposals=list(proposals or [])
    if not words and ((caption_enabled and not captions_current) or (mark_repeats and not repeat_analysis_complete)):
        progress('Çıktı için Türkçe metin ve tekrar işaretleri hazırlanıyor…')
        result=analyze_speech(project,track,Settings(),cancel,progress,transcribe=True,suggest=mark_repeats)
        words=result.transcript;proposals.extend(result.proposals)
        repeat_analysis_complete=mark_repeats
    if mark_repeats and words and not repeat_analysis_complete:proposals.extend(suggest_edits(words,project.fps))
    markers=repeat_markers(proposals) if mark_repeats else []
    refreshed=False;cues=None
    if caption_enabled:
        if captions_current and caption_cues:cues=list(caption_cues)
        else:
            progress('Altyazı zamanları son kesimlere göre otomatik yenileniyor…')
            cues=build_captions(words,cuts,project.duration,project.fps,line_width(project.data));refreshed=True
            if not cues:raise UserError('Kalan konuşmadan altyazı oluşturulamadı. Altyazıyı kapatıp tekrar deneyin.')
    output=create_copy(project,cuts,cancel,review=review,captions=cues,markers=markers,**copy_options)
    return {'path':output,'words':words,'caption_cues':cues or [],'captions_refreshed':refreshed,
            'marker_count':len(load_json(output/'sessizlik_raporu.json')['repeat_markers'])}
