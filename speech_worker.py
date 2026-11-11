"""Disposable offline inference process. Parent owns cancellation and lifecycle."""
import math
import os
from pathlib import Path
import sys
import time
import wave

os.environ['HF_HUB_OFFLINE']='1'
os.environ['HF_HUB_DISABLE_TELEMETRY']='1'

import numpy as np
from silence_core import US, Cut, atomic_json, load_json
from speech_analysis import ENGINE, union_ranges


def dominant_mono(samples):
    """Select the strongest channel in short blocks; never cancel opposite-phase stereo."""
    if samples.shape[1]==1:
        return np.asarray(samples[:,0],dtype=np.float32)/32768.0
    output=np.empty(len(samples),dtype=np.float32)
    for start in range(0,len(samples),16000):
        block=np.asarray(samples[start:start+16000],dtype=np.float32)
        channel=int(np.argmax(np.mean(block*block,axis=0)))
        output[start:start+len(block)]=block[:,channel]/32768.0
    return output


def main():
    from faster_whisper import WhisperModel
    from faster_whisper.vad import get_speech_timestamps,VadOptions
    request=load_json(Path(sys.argv[1]));status=Path(request['status'])
    started=time.perf_counter();cpu=time.process_time()
    tokens=0
    def report(message):atomic_json(status,{'message':message})
    report('Yerel konuşma algılama hazırlanıyor…')
    model=None
    options=VadOptions(threshold=.35,min_speech_duration_ms=100,min_silence_duration_ms=120,speech_pad_ms=0)
    for i,task in enumerate(request['tasks']):
        report(f'Konuşma / klavye ayrımı · {i+1}/{len(request["tasks"])}')
        with wave.open(task['wav'],'rb') as audio:
            if audio.getsampwidth()!=2 or audio.getframerate()!=16000 or not 1<=audio.getnchannels()<=8:
                raise ValueError('Unsupported decoded audio format')
            channels=audio.getnchannels()
            samples=np.frombuffer(audio.readframes(audio.getnframes()),dtype='<i2').reshape(-1,channels)
        duration=task['duration_us']
        speech=[]
        for ch in range(channels):
            channel=np.asarray(samples[:,ch],dtype=np.float32)/32768.0
            for span in get_speech_timestamps(channel,vad_options=options):
                a=round(span['start']*US/16000);b=min(duration,round(span['end']*US/16000))
                if b>a:speech.append(Cut(a,b))
        speech=union_ranges(speech)
        words=[]
        if request['transcribe'] and speech:
            if model is None:
                report('Yerel Türkçe model yükleniyor…')
                model=WhisperModel(request['model'],device='cpu',compute_type='int8',cpu_threads=4,num_workers=1,local_files_only=True)
            report(f'Türkçe yazıya dökülüyor · {i+1}/{len(request["tasks"])}')
            segments,info=model.transcribe(dominant_mono(samples),language='tr',beam_size=3,
                word_timestamps=True,vad_filter=True,
                vad_parameters={'threshold':.35,'min_silence_duration_ms':350,'speech_pad_ms':180},
                condition_on_previous_text=False,temperature=0,hallucination_silence_threshold=1.0)
            for segment in segments:
                tokens+=len(segment.tokens)
                report(f'Türkçe çözümleme · {min(segment.end,duration/US):.0f} / {duration/US:.0f} sn')
                if segment.no_speech_prob>.7 and segment.avg_logprob<-1:
                    continue
                for word in segment.words or []:
                    a=max(0,round(word.start*US));b=min(duration,round(word.end*US))
                    probability=float(word.probability)
                    if 0<=a<b<=duration and math.isfinite(probability) and 0<=probability<=1:
                        words.append({'word':word.word,'start':a,'end':b,'probability':probability})
        atomic_json(Path(task['result']),{'engine':ENGINE,'speech_us':[[s.start,s.end] for s in speech],'words':words})
    import psutil
    memory=psutil.Process().memory_info()
    atomic_json(status,{'message':'Yerel analiz tamamlandı.','worker_seconds':round(time.perf_counter()-started,3),
                        'worker_cpu_seconds':round(time.process_time()-cpu,3),
                        'worker_peak_memory_bytes':getattr(memory,'peak_wset',memory.rss),'transcription_tokens':tokens})


if __name__=='__main__':
    main()
