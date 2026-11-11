"""Local AI orchestration and deterministic editing suggestions. No model/network imports in UI."""
from __future__ import annotations
from dataclasses import dataclass
from collections import deque
from difflib import SequenceMatcher
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import tempfile
import threading
import time
import wave
from platform_support import runtime_python,package_roots,asset_root,state_root,worker_command

from silence_core import (APP, US, Cut, Settings, Project, UserError, Cancelled, CREATE_NO_WINDOW,
                          analysis_clips, atomic_json, load_json, run_media, normalize_cuts, silence_cut)

ENGINE='local-speech-v3'
MODEL=asset_root()/'.models/whisper-small'
CACHE=state_root(APP)/'cache'
PYTHON=runtime_python(APP)
CHUNK_US=300*US
_TURKISH_CASE=str.maketrans({'I':'ı','İ':'i'})
_NON_WORD=re.compile(r'[^a-zçğıöşü0-9]')


@dataclass
class AnalysisResult:
    cuts: list[Cut]
    proposals: list[dict]
    transcript: list[dict]
    context: dict
    metrics: dict


def union_ranges(ranges: list[Cut]) -> list[Cut]:
    merged=[]
    for item in sorted(ranges):
        if item.end<=item.start:
            continue
        if merged and item.start<=merged[-1].end:
            merged[-1]=Cut(merged[-1].start,max(merged[-1].end,item.end))
        else:
            merged.append(item)
    return merged


def non_speech_cuts(start: int, end: int, speech: list[Cut], settings: Settings, fps: float) -> list[Cut]:
    cursor=start
    gaps=[]
    for span in union_ranges([Cut(max(start,s.start),min(end,s.end)) for s in speech]):
        if span.start>cursor:
            gaps.append(Cut(cursor,span.start))
        cursor=max(cursor,span.end)
    if cursor<end:
        gaps.append(Cut(cursor,end))
    cuts=[]
    for gap in gaps:
        cut=silence_cut(gap.start,gap.end,settings,fps)
        if cut:cuts.append(cut)
    return cuts


def normalize_word(text: str) -> str:
    return _NON_WORD.sub('',text.translate(_TURKISH_CASE).lower())


def suggest_edits(words: list[dict], fps: float) -> list[dict]:
    """Possible repeated takes become markers; no spoken phrase is auto-deleted."""
    tokens_by_word={id(w):normalize_word(w['word']) for w in words}
    suggestions=[]
    def add(kind,a,b,text,score,comparison='',comparison_start=None,comparison_end=None):
        a=round(math.ceil(a*fps/US-1e-8)*US/fps)
        b=round(math.floor(b*fps/US+1e-8)*US/fps)
        if b>a:
            suggestions.append({'kind':kind,'start':a,'end':b,'text':text.strip(),
                                'score':round(score,3),'comparison':comparison,'requires_approval':False,
                                'marker_only':True,'comparison_start':comparison_start,'comparison_end':comparison_end})
    sentences=[];current=[]
    for word in sorted(words,key=lambda w:(w['start'],w['end'])):
        if current and word['start']-current[-1]['end']>1_200_000:
            sentences.append(current);current=[]
        current.append(word)
        if re.search(r'[.!?…]["\u201d\u2019]?\s*$',word['word']):
            sentences.append(current);current=[]
    if current:
        sentences.append(current)
    sentence_tokens=[[tokens_by_word[id(w)] for w in sentence if tokens_by_word[id(w)]] for sentence in sentences]
    sentence_confidence=[min(w.get('probability',0) for w in sentence) for sentence in sentences]
    # Compare only nearby sentences; bound work even on multi-hour recordings.
    for i,earlier in enumerate(sentences):
        tokens=sentence_tokens[i]
        if len(tokens)<4 or sum(map(len,tokens))<14 or sentence_confidence[i]<.5:
            continue
        for j in range(i+1,min(i+13,len(sentences))):
            later=sentences[j]
            if later[0]['start']-earlier[-1]['end']>60*US:
                break
            other=sentence_tokens[j]
            if len(other)<4 or sentence_confidence[j]<.5:
                continue
            similarity=SequenceMatcher(None,tokens,other,autojunk=False).ratio()
            if similarity>=.88:
                add('retake',earlier[0]['start'],earlier[-1]['end'],''.join(w['word'] for w in earlier),similarity,
                    ''.join(w['word'] for w in later),later[0]['start'],later[-1]['end'])
                break
    # Catch an immediately repeated short phrase even if Whisper joins both into one sentence.
    for i in range(len(words)):
        for length in range(5,1,-1):
            first=words[i:i+length];second=words[i+length:i+2*length]
            if len(second)!=length or not first:
                continue
            if second[0]['start']-first[-1]['end']>1_500_000:
                continue
            if any(right['start']-left['end']>1_500_000
                   for phrase in (first,second) for left,right in zip(phrase,phrase[1:])):
                continue
            left=[tokens_by_word[id(w)] for w in first];right=[tokens_by_word[id(w)] for w in second]
            if left==right and all(left) and min(w.get('probability',0) for w in first+second)>=.6:
                add('retake',first[0]['start'],first[-1]['end'],''.join(w['word'] for w in first),1.0,
                    ''.join(w['word'] for w in second),second[0]['start'],second[-1]['end'])
                break
    # A retake already includes any filler inside it. Show the broader decision once.
    retakes=sorted((p for p in suggestions if p['kind']=='retake'),key=lambda p:p['start'])
    result=[];recent=deque();retake_index=0;furthest_end=-1
    for proposal in sorted(suggestions,key=lambda p:(p['start'],-p['end'],p['kind'])):
        while retake_index<len(retakes) and retakes[retake_index]['start']<=proposal['start']:
            furthest_end=max(furthest_end,retakes[retake_index]['end']);retake_index+=1
        if proposal['kind']=='filler' and furthest_end>=proposal['end']:
            continue
        while recent and proposal['start']-recent[0]['start']>=50_000:
            recent.popleft()
        if any(p['kind']==proposal['kind'] and abs(p['end']-proposal['end'])<50_000 for p in recent):
            continue
        result.append(proposal);recent.append(proposal)
    return result


def _valid_result(data: dict, duration: int) -> bool:
    if data.get('engine')!=ENGINE or not isinstance(data.get('speech_us'),list) or not isinstance(data.get('words'),list):
        return False
    try:
        for a,b in data['speech_us']:
            if type(a) is not int or type(b) is not int or not 0<=a<b<=duration:
                return False
        for w in data['words']:
            if (type(w['start']) is not int or type(w['end']) is not int or not 0<=w['start']<w['end']<=duration or
                    not isinstance(w['word'],str) or not isinstance(w['probability'],(float,int)) or
                    not math.isfinite(w['probability']) or not 0<=w['probability']<=1):
                return False
    except (TypeError,ValueError,KeyError):
        return False
    return True


def _cache_read(path: Path, duration: int) -> dict | None:
    try:
        if path.is_file() and path.stat().st_size<=32*1024*1024:
            data=load_json(path)
            if _valid_result(data,duration):
                return data
    except (OSError,UserError):
        pass
    return None


def _valid_wav(path: Path, duration: int) -> bool:
    try:
        with wave.open(str(path),'rb') as f:
            if not (f.getframerate()==16000 and f.getsampwidth()==2 and 1<=f.getnchannels()<=8 and
                    f.getnframes()>0 and abs(f.getnframes()/16000-duration/US)<=.05):
                return False
            # A valid header can survive an interrupted/truncated file write.
            f.setpos(f.getnframes()-1)
            return len(f.readframes(1))==2*f.getnchannels()
    except (OSError,EOFError,wave.Error):
        return False


def prune_cache(cache: Path=CACHE, limit: int=512*1024*1024) -> None:
    """Only app-owned, content-keyed cache files may be removed."""
    if not cache.exists():
        return
    files=[]
    try:paths=list(cache.iterdir())
    except OSError:return
    for path in paths:
        if not re.fullmatch(r'[0-9a-f]{64}-(audio\.wav|speech\.json|text\.json)',path.name):continue
        try:
            if path.is_file():
                stamp=path.stat();files.append((stamp.st_mtime,stamp.st_size,path))
        except OSError:continue
    total=sum(size for _,size,_ in files)
    for _,size,path in sorted(files):
        if total<=limit:
            break
        try:
            path.unlink();total-=size
        except OSError:
            continue


def run_worker(tasks: list[dict], transcribe: bool, cancel: threading.Event, progress, worker_script: Path|None=None) -> dict:
    if cancel.is_set():
        raise Cancelled('İşlem iptal edildi.')
    if not PYTHON.is_file():
        raise UserError('Yerel konuşma ortamı bulunamadı. Kurulum betiğini çalıştırın.')
    with tempfile.TemporaryDirectory(prefix='sessizlik-ai-') as temp:
        request=Path(temp)/'request.json';log=Path(temp)/'worker.log';status=Path(temp)/'status.json'
        atomic_json(request,{'engine':ENGINE,'tasks':tasks,'transcribe':transcribe,'model':str(MODEL),'status':str(status)})
        env=os.environ.copy()
        env.update(HF_HUB_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',TOKENIZERS_PARALLELISM='false',OMP_NUM_THREADS='4')
        with log.open('wb') as output:
            proc=subprocess.Popen(worker_command(PYTHON,request,worker_script),
                                  stdin=subprocess.DEVNULL,stdout=output,stderr=output,env=env,creationflags=CREATE_NO_WINDOW)
            previous=''
            try:
                while proc.poll() is None:
                    if cancel.wait(.12):
                        raise Cancelled('İşlem iptal edildi.')
                    if status.exists():
                        try:
                            current=load_json(status).get('message','')
                            if current!=previous:
                                progress(current);previous=current
                        except UserError:
                            pass
                if cancel.is_set():
                    raise Cancelled('İşlem iptal edildi.')
                if proc.returncode:
                    detail=log.read_text(encoding='utf-8',errors='replace')[-1800:]
                    raise UserError('Yerel konuşma analizi tamamlanamadı:\n'+detail)
                return load_json(status) if status.exists() else {}
            finally:
                if proc.poll() is None:
                    # Windows venv launchers can own another Python process.
                    # Stop descendants too, then wait until inference has stopped.
                    import psutil
                    try:children=psutil.Process(proc.pid).children(recursive=True)
                    except psutil.NoSuchProcess:children=[]
                    for child in reversed(children):
                        try:child.kill()
                        except psutil.NoSuchProcess:pass
                    if proc.poll() is None:proc.kill()
                    psutil.wait_procs(children,timeout=3)
                proc.wait()


def analyze_speech(project: Project, track: int, settings: Settings, cancel: threading.Event,
                   progress=lambda _:None, transcribe: bool=True, cache: Path=CACHE, suggest: bool=True) -> AnalysisResult:
    started=time.perf_counter()
    clips=analysis_clips(project,track,settings)
    if transcribe and not (MODEL/'local-manifest.json').is_file():
        raise UserError('Türkçe konuşma modeli eksik. Önce yerel model kurulumunu çalıştırın.')
    manifest=load_json(MODEL/'local-manifest.json') if transcribe else {}
    revision=manifest.get('revision','vad-only')
    model_files=[MODEL/name for name in manifest.get('files',{})]
    for root in package_roots():model_files+=sorted((root/'faster_whisper/assets').glob('*.onnx'))
    model_state=[]
    for path in model_files:
        if not path.is_file():
            raise UserError(f'Yerel model dosyası eksik: {path.name}')
        stamp=path.stat();model_state.append([str(path),stamp.st_size,stamp.st_mtime_ns])
    runtime=sorted({p.name for root in package_roots() for p in root.glob('*.dist-info')})
    chunks=[];tasks=[];scheduled=set();cached=0;audio_cached=0;decoded=0
    cache.mkdir(parents=True,exist_ok=True)
    for parent,clip in enumerate(clips):
        for core_start in range(clip.start,clip.end,CHUNK_US):
            if cancel.is_set():
                raise Cancelled('İşlem iptal edildi.')
            core_end=min(core_start+CHUNK_US,clip.end)
            left=max(clip.start,core_start-US);right=min(clip.end,core_end+US)
            source_start=clip.source_start+left-clip.start
            stat=clip.path.stat()
            source_identity={'source':str(clip.path),'size':stat.st_size,'mtime_ns':stat.st_mtime_ns,
                             'start_us':source_start,'duration_us':right-left}
            identity=dict(source_identity,engine=ENGINE,model_revision=revision,transcribe=transcribe,
                          model_state=model_state,runtime=runtime)
            key=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()
            result_path=cache/(key+('-text.json' if transcribe else '-speech.json'))
            result=_cache_read(result_path,right-left)
            if result is not None:
                cached+=1
            elif key not in scheduled:
                audio_key=hashlib.sha256(json.dumps(dict(source_identity,format='pcm-s16le-16000-v1'),sort_keys=True).encode()).hexdigest()
                wav=cache/(audio_key+'-audio.wav')
                # A cache WAV is committed only after FFmpeg completed successfully.
                if not _valid_wav(wav,right-left):
                    progress(f'Ses hazırlanıyor · {parent+1}/{len(clips)}')
                    fd,tmp=tempfile.mkstemp(suffix='.wav',dir=cache);os.close(fd)
                    try:
                        run_media(['-y','-ss',f'{source_start/US:.6f}','-t',f'{(right-left)/US:.6f}',
                                   '-i',str(clip.path),'-map','0:a:0','-vn','-ar','16000','-c:a','pcm_s16le',tmp],
                                  cancel,expected_duration=right-left)
                        os.replace(tmp,wav)
                        decoded+=1
                    finally:
                        Path(tmp).unlink(missing_ok=True)
                else:
                    audio_cached+=1
                tasks.append({'wav':str(wav),'result':str(result_path),'duration_us':right-left})
                scheduled.add(key)
            chunks.append({'parent':parent,'left':left,'core_start':core_start,'core_end':core_end,
                           'result_path':result_path,'duration':right-left,'result':result})
    metrics={}
    if tasks:
        metrics=run_worker(tasks,transcribe,cancel,progress)
    else:
        progress('Önceki yerel analiz yeniden kullanılıyor.')
    speech_by_clip={i:[] for i in range(len(clips))};words=[]
    for chunk in chunks:
        data=chunk['result'] or _cache_read(chunk['result_path'],chunk['duration'])
        if data is None:
            raise UserError('Konuşma analizi sonucu eksik veya bozuk; işlem uygulanmadı.')
        left=chunk['left'];a=chunk['core_start'];b=chunk['core_end']
        for x,y in data['speech_us']:
            x=max(a,left+x);y=min(b,left+y)
            if y>x:
                speech_by_clip[chunk['parent']].append(Cut(x,y))
        for word in data['words']:
            x=left+word['start'];y=left+word['end']
            if a<=(x+y)//2<b:
                clip=clips[chunk['parent']]
                item=dict(word,start=max(clip.start,x),end=min(clip.end,y))
                if item['end']>item['start']:
                    words.append(item)
                    # Recognized words protect quiet speech that VAD may have missed.
                    if item['probability']>=.35:
                        guard=0 if settings.next_speech_padding is not None else 40000
                        speech_by_clip[chunk['parent']].append(Cut(max(clip.start,x-guard),min(clip.end,y+guard)))
    if not any(speech_by_clip.values()):
        raise UserError('Konuşma bulunamadı. Temiz mikrofon kaynağını kontrol edin; tüm kayıt silinmedi.')
    jump_context=None
    if settings.auto_jump_cut:
        from jump_cut import automatic_jump_cuts
        cuts,jump_context=automatic_jump_cuts(clips,speech_by_clip,words,project.fps,settings,project.duration)
    else:
        cuts=[]
        for i,clip in enumerate(clips):
            cuts.extend(non_speech_cuts(clip.start,clip.end,speech_by_clip[i],settings,project.fps))
    words.sort(key=lambda w:(w['start'],w['end']))
    proposals=suggest_edits(words,project.fps) if transcribe and suggest else []
    project.assert_unchanged()
    if cancel.is_set():
        raise Cancelled('İşlem iptal edildi.')
    metrics.update(elapsed_seconds=round(time.perf_counter()-started,3),cache_hits=cached,chunks=len(chunks),
                   audio_cache_hits=audio_cached,decoded_chunks=decoded,worker_tasks=len(tasks))
    context={'engine':ENGINE,'postprocess_revision':'speech-boundary-v2','transcribe':transcribe,'suggest':transcribe and suggest,'model_revision':revision,'language':'tr',
             'model_state':model_state,'runtime':runtime}
    if jump_context:context['jump_cut']=jump_context
    result=AnalysisResult(normalize_cuts(cuts,project.duration),proposals,words,context,metrics)
    prune_cache(cache)
    return result
