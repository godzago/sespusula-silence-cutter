"""Conservative pause shortening; editorial heuristics, not a universal jump-cut standard."""
from bisect import bisect_left
from dataclasses import replace
import math
import re
from statistics import median

from silence_core import Cut, US, UserError, silence_cut


def merged_speech(start,end,speech):
    result=[]
    for s in sorted(speech):
        a,b=max(start,s.start),min(end,s.end)
        if b<=a:continue
        if result and a<=result[-1].end:result[-1]=Cut(result[-1].start,max(b,result[-1].end))
        else:result.append(Cut(a,b))
    return result


def automatic_jump_cuts(clips, speech_by_clip, words, fps, settings, duration=None):
    speech={i:merged_speech(c.start,c.end,speech_by_clip.get(i,[])) for i,c in enumerate(clips)}
    if not any(speech.values()):
        raise UserError('Konuşma bulunamadı; otomatik jump cut uygulanmadı.')
    if settings.next_speech_padding is not None:
        return direct_silence_cuts(clips,speech,fps,settings.next_speech_padding,duration)
    pauses=[b.start-a.end for spans in speech.values() for a,b in zip(spans,spans[1:])
            if 120_000<=b.start-a.end<=1_200_000]
    # Adapt only when enough short pauses exist; long dead air must not slow the profile.
    cadence=median(pauses)/US if len(pauses)>=5 else .24
    retained=round(min(.28,max(.20,cadence*.85)),3)
    threshold=round(min(.60,max(.35,retained+.12,cadence*1.4)),3)
    effective=replace(settings,minimum=threshold,maximum=None,padding=round(retained*.6,3),
                      lead_padding=round(retained*.4,3),minimum_cut=max(.08,2/fps),start=0.,end=None)
    sentence_ends=sorted(w['end'] for w in words if w.get('probability',0)>=.35 and
                         re.search(r'[.!?…]["\u201d\u2019]?\s*$',w['word']))
    cuts=[];sentence_gaps=0
    for i,clip in enumerate(clips):
        spans=speech[i];cursor=clip.start;gaps=[]
        for span in spans:
            if span.start>cursor:gaps.append(Cut(cursor,span.start))
            cursor=span.end
        if cursor<clip.end:gaps.append(Cut(cursor,clip.end))
        for gap in gaps:
            profile=effective
            index=bisect_left(sentence_ends,gap.start-250_000)
            is_sentence=(gap.start>clip.start and gap.end<clip.end and index<len(sentence_ends) and
                         sentence_ends[index]<=gap.start+100_000)
            if is_sentence:
                sentence_retained=max(.32,retained)
                profile=replace(profile,minimum=max(threshold,sentence_retained+.12),
                                padding=sentence_retained*.6,lead_padding=sentence_retained*.4)
                sentence_gaps+=1
            # Leading/trailing dead air needs protection only on the speech-facing edge.
            if gap.start==clip.start:profile=replace(profile,padding=0.)
            if gap.end==clip.end:profile=replace(profile,lead_padding=0.)
            cut=silence_cut(gap.start,gap.end,profile,fps)
            if cut:cuts.append(cut)
    return cuts,{'version':'auto-jump-v1','scope':'full-timeline','minimum_pause_seconds':threshold,
                 'retained_pause_seconds':retained,'word_tail_seconds':effective.padding,
                 'word_onset_seconds':effective.lead_padding,'minimum_cut_seconds':effective.minimum_cut,
                 'sentence_pause_seconds':.32 if sentence_ends else None,'sentence_gaps':sentence_gaps,
                 'cadence_samples':len(pauses),'cadence_adapted':len(pauses)>=5,
                 'frame_quantization':'inward','maximum_pause_seconds':None}


def direct_silence_cuts(clips,speech_by_clip,fps,onset_padding,duration=None):
    """Cut every complete silent frame until the requested lead-in before the next speech."""
    duration=duration if duration is not None else max(c.end for c in clips)
    spans=merged_speech(0,duration,[s for group in speech_by_clip.values() for s in group])
    if not spans:raise UserError('Konuşma bulunamadı; bütün kayıt silinmedi.')
    cursor=0;gaps=[]
    for span in spans:
        if span.start>cursor:gaps.append((cursor,span.start,True))
        cursor=span.end
    if cursor<duration:gaps.append((cursor,duration,False))
    cuts=[]
    for a,b,has_next_speech in gaps:
        x=round(math.ceil(a*fps/US-1e-8)*US/fps)
        y=round(math.floor((b-onset_padding*US if has_next_speech else b)*fps/US+1e-8)*US/fps)
        if y>x:cuts.append(Cut(x,y))
    return cuts,{'version':'direct-silence-v1','scope':'full-timeline','minimum_pause_seconds':onset_padding+1/fps,
                 'retained_pause_seconds':onset_padding,'word_tail_seconds':0.,'word_onset_seconds':onset_padding,
                 'minimum_cut_seconds':1/fps,'sentence_pause_seconds':None,'sentence_gaps':0,
                 'cadence_samples':0,'cadence_adapted':False,'frame_quantization':'inward',
                 'maximum_pause_seconds':None,'empty_primary_track_ranges_are_silent':True}
