"""Word-timed Turkish captions and editable, ordinary CapCut text clips."""
from __future__ import annotations

from bisect import bisect_right
import json
import math
import os
from pathlib import Path
import re
import textwrap

from silence_core import US, UserError, normalize_cuts, uid

GENERATED_TRACK_NAME='SesPusula · Otomatik altyazı'


def line_width(data):
    canvas=data.get('canvas_config') or {}
    return 28 if canvas.get('height',1080)>canvas.get('width',1920) else 42


def wrap_caption(text, width=42):
    clean=' '.join(text.split())
    if not clean:raise UserError('Altyazı metni boş olamaz.')
    if len(clean)>width*2:
        raise UserError(f'Bir altyazı en fazla {width*2} karakter olmalı; uzun metni ayrı satırlara bölün.')
    lines=textwrap.wrap(clean,width=width,break_long_words=True,break_on_hyphens=False)
    if len(lines)>2:raise UserError('Altyazı iki satıra sığmıyor; metni kısaltın.')
    return '\n'.join(lines)


def build_captions(words, cuts, duration, fps=30, width=42):
    """Remove cut words, map retained words, and break captions at every edit join."""
    cuts=normalize_cuts(cuts,duration)
    starts=[c.start for c in cuts];ends=[c.end for c in cuts];prefix=[0]
    for c in cuts:prefix.append(prefix[-1]+c.duration)
    retained=[]
    for word in words:
        if (not isinstance(word,dict) or not isinstance(word.get('word'),str) or
            type(word.get('start')) is not int or type(word.get('end')) is not int or
            not 0<=word['start']<word['end']<=duration):
            raise UserError('Altyazı için kelime zamanları geçersiz; metni yeniden çıkarın.')
        a,b=word['start'],word['end'];i=bisect_right(ends,a)
        if i<len(cuts) and starts[i]<b:continue
        text=' '.join(word['word'].split())
        if not text:continue
        retained.append({'start':a-prefix[i],'end':b-prefix[i],'word':text,'section':i})
    retained.sort(key=lambda w:(w['start'],w['end']))
    result=[];current=[];out_duration=duration-prefix[-1]
    frame=US/fps
    def finish():
        if not current:return
        # Never extend captions into removed speech or past the output duration.
        a=max(result[-1]['end'] if result else 0,round(math.floor(current[0]['start']/frame+1e-8)*frame))
        b=min(out_duration,round(math.ceil(max(w['end'] for w in current)/frame-1e-8)*frame))
        if b>a:result.append({'start':a,'end':b,'text':wrap_caption(' '.join(w['word'] for w in current),width)})
        current.clear()
    for word in retained:
        proposed=' '.join(w['word'] for w in [*current,word])
        overflow=False
        try:wrap_caption(proposed,width)
        except UserError:overflow=True
        if current and (overflow or len(current)>=10 or word['section']!=current[-1]['section'] or
                        word['start']-current[-1]['end']>600_000 or word['end']-current[0]['start']>4_500_000):
            finish()
        if len(word['word'])>width*2:
            raise UserError('Bir kelime altyazı sınırını aşıyor; konuşma metnini kontrol edin.')
        current.append(word)
        if re.search(r'[.!?…]["\u201d\u2019]?$',word['word']):finish()
    finish()
    return result


def validate_captions(cues, duration, width=42):
    if not isinstance(cues,list) or not cues:raise UserError('Eklenecek altyazı yok.')
    previous=0;validated=[]
    for cue in cues:
        if (not isinstance(cue,dict) or type(cue.get('start')) is not int or type(cue.get('end')) is not int or
            not previous<=cue['start']<cue['end']<=duration or not isinstance(cue.get('text'),str)):
            raise UserError('Altyazı zamanları geçersiz, çakışıyor veya çıktı süresini aşıyor.')
        validated.append({'start':cue['start'],'end':cue['end'],'text':wrap_caption(cue['text'],width)})
        previous=cue['end']
    return validated


def local_font():
    candidates=[Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts/arialbd.ttf',
                Path('/System/Library/Fonts/Supplemental/Arial Bold.ttf')]
    return next((p.as_posix() for p in candidates if p.is_file()),'')


def text_material(text, font):
    # Field names match ordinary text materials in the supported local JSON schema.
    style={'fill':{'content':{'render_type':'solid','solid':{'color':[1.,1.,1.],'alpha':1.}}},
           'font':{'path':font,'id':'','name':'Arial'},'size':8.,'bold':True,
           'range':[0,len(text.encode('utf-16-le'))//2],
           'strokes':[{'content':{'solid':{'color':[0.,0.,0.],'alpha':1.}},'width':.06}]}
    return {'id':uid(),'type':'text','name':'','content':json.dumps({'text':text,'styles':[style]},ensure_ascii=False),
            'base_content':'','recognize_text':'','recognize_task_id':'','recognize_model':'','punc_model':'',
            'words':{'start_time':[],'end_time':[],'text':[]},'current_words':{'start_time':[],'end_time':[],'text':[]},
            'global_alpha':1.,'text_color':'#FFFFFF','text_alpha':1.,'font_name':'Arial','font_title':'Arial',
            'font_size':8.,'font_path':font,'font_id':'','font_resource_id':'','font_url':'','fonts':[],
            'alignment':1,'typesetting':0,'line_feed':1,'line_spacing':.02,'letter_spacing':0.,
            'border_color':'#000000','border_alpha':1.,'border_width':.06,'border_mode':0,
            'has_shadow':False,'background_style':0,'background_color':'','background_alpha':0.,
            'bold_width':.008,'italic_degree':0,'underline':False,'initial_scale':1.,'is_rich_text':False,
            'text_size':30,'check_flag':7,'sub_type':0,'add_type':0,'operation_type':0,'recognize_type':0,
            'is_lyric_effect':False,'text_to_audio_ids':[],'relevance_segment':[],'group_id':'',
            'combo_info':{'text_templates':[]},'is_words_linear':False,'use_effect_default_color':False,
            'fixed_width':-1.,'fixed_height':-1.,'line_max_width':.82,'force_apply_line_max_width':True,
            'oneline_cutoff':False,'autoAdaptCanvasEnabled':False,'language':'tr','sub_template_id':-1}


def add_caption_track(data, cues):
    cues=validate_captions(cues,data['duration'],line_width(data))
    texts=data['materials'].setdefault('texts',[])
    if not isinstance(texts,list):raise UserError('Projenin metin materyali listesi geçersiz.')
    replaced_ids={s['material_id'] for t in data['tracks'] if t.get('type')=='text' and t.get('name')==GENERATED_TRACK_NAME
                  for s in t.get('segments',[])}
    data['tracks']=[t for t in data['tracks'] if not (t.get('type')=='text' and t.get('name')==GENERATED_TRACK_NAME)]
    still_used={s.get('material_id') for t in data['tracks'] for s in t.get('segments',[])}
    texts[:]=[m for m in texts if m['id'] not in replaced_ids or m['id'] in still_used]
    render=max([s.get('render_index',0) for t in data['tracks'] for s in t.get('segments',[])]+[14000])+1000
    track_index=max([s.get('track_render_index',0) for t in data['tracks'] for s in t.get('segments',[])]+[len(data['tracks'])])+1
    font=local_font();segments=[]
    for cue in cues:
        material=text_material(cue['text'],font);texts.append(material)
        segments.append({'id':uid(),'material_id':material['id'],'source_timerange':None,
            'target_timerange':{'start':cue['start'],'duration':cue['end']-cue['start']},
            'render_timerange':{'start':0,'duration':0},'extra_material_refs':[],
            'clip':{'scale':{'x':1.,'y':1.},'rotation':0.,'transform':{'x':0.,'y':-.78},
                    'flip':{'vertical':False,'horizontal':False},'alpha':1.},
            'uniform_scale':{'on':True,'value':1.},'render_index':render,'track_render_index':track_index,
            'speed':1.,'volume':1.,'last_nonzero_volume':1.,'visible':True,'state':0,'track_attribute':0,
            'reverse':False,'is_loop':False,'group_id':'','common_keyframes':[],'keyframe_refs':[],
            'caption_info':None,'lyric_keyframes':None,'responsive_layout':{'enable':False},
            'enable_lut':False,'enable_adjust':False,'enable_hsl':False,'source':'segmentsourcenormal'})
    data['tracks'].append({'id':uid(),'type':'text','name':GENERATED_TRACK_NAME,
                           'is_default_name':False,'attribute':0,'flag':0,'segments':segments})
    return cues


def srt_text(cues):
    def timestamp(value):
        ms=round(value/1000);hours,ms=divmod(ms,3600000);minutes,ms=divmod(ms,60000);seconds,ms=divmod(ms,1000)
        return f'{hours:02}:{minutes:02}:{seconds:02},{ms:03}'
    return '\n\n'.join(f'{i}\n{timestamp(c["start"])} --> {timestamp(c["end"])}\n{c["text"]}' for i,c in enumerate(cues,1))+'\n'
