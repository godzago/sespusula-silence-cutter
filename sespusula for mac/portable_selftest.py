"""Check the shipped runtime, Tk, FFmpeg and both local inference engines."""
import argparse
import hashlib
import importlib
import json
import platform
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import traceback
import wave

from platform_support import application_home,asset_root,state_root,configure_environment,runtime_python,VERSION


def runtime_boundary():
    if getattr(sys,'frozen',False) and sys.platform=='darwin':
        return next(path for path in Path(sys.executable).resolve().parents if path.suffix=='.app')
    return application_home().resolve()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--report',type=Path)
    parser.add_argument('--require-contained-runtime',action='store_true')
    args=parser.parse_args()
    configure_environment()
    output=args.report or state_root()/'portable-self-test.json'
    report={'passed':False,'version':VERSION,'platform':sys.platform,'architecture':platform.machine(),
            'macos':platform.mac_ver()[0] if sys.platform=='darwin' else None,
            'frozen':bool(getattr(sys,'frozen',False)),
            'application_home':str(application_home()),'python':sys.executable,
            'python_prefix':sys.prefix,'python_base_prefix':sys.base_prefix,'sys_path':list(sys.path)}
    try:
        command=([sys.executable] if getattr(sys,'frozen',False) else
                 [str(runtime_python()),str(application_home()/'entrypoint.py')])
        subprocess.run([*command,'--process-probe'],capture_output=True,text=True,timeout=40,check=True)
        report['multiprocessing_spawn_verified']=True
        def blocked(*a,**kw):raise RuntimeError('Test attempted network access')
        socket.socket.connect=blocked;socket.socket.connect_ex=blocked;socket.create_connection=blocked
        modules={name:importlib.import_module(name) for name in ('tkinter','numpy','psutil','av','ctranslate2','onnxruntime','faster_whisper')}
        report['module_paths']={name:str(module.__file__) for name,module in modules.items()}
        if args.require_contained_runtime:
            boundary=runtime_boundary()
            report['contained_runtime_root']=str(boundary)
            assert Path(sys.base_prefix).resolve().is_relative_to(boundary),'External Python base prefix'
            assert all(Path(p).resolve().is_relative_to(boundary) for p in report['module_paths'].values()),'External dependency'
            assert all(Path(p).resolve().is_relative_to(boundary) for p in sys.path),'External Python search path'
        from silence_core import ffmpeg_executable,load_json,US
        from speech_analysis import MODEL,run_worker
        version=subprocess.run([ffmpeg_executable(),'-version'],capture_output=True,text=True,check=True)
        report['ffmpeg']=ffmpeg_executable();report['ffmpeg_version']=version.stdout.splitlines()[0]
        manifest=load_json(MODEL/'local-manifest.json')
        for name,expected in manifest['files'].items():
            digest=hashlib.sha256()
            with (MODEL/name).open('rb') as data:
                for block in iter(lambda:data.read(1024*1024),b''):digest.update(block)
            assert digest.hexdigest()==expected,f'Model checksum mismatch: {name}'
        report['model_checksums_verified']=True
        from faster_whisper import WhisperModel
        model=WhisperModel(str(MODEL),device='cpu',compute_type='int8',cpu_threads=4,local_files_only=True)
        report['whisper_model_loaded']=True
        import numpy as np
        segments,_=model.transcribe(np.zeros(16000,dtype=np.float32),language='tr',
                                   beam_size=1,word_timestamps=True,vad_filter=False)
        list(segments)
        report['whisper_transcription_pipeline_verified']=True
        del model
        with tempfile.TemporaryDirectory(prefix='sespusula-selftest-') as scratch:
            root=Path(scratch);audio=root/'silence.wav';result=root/'result.json'
            with wave.open(str(audio),'wb') as wav:
                wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(16000);wav.writeframes(b'\0'*32000)
            metrics=run_worker([{'wav':str(audio),'result':str(result),'duration_us':US}],False,threading.Event(),lambda _:None,
                               worker_script=asset_root()/'offline_worker.py')
            data=load_json(result);assert data['speech_us']==[] and data['words']==[]
            report['vad_worker_offline_verified']=True;report['worker_python']=str(runtime_python());report['worker_metrics']=metrics
        from unittest.mock import patch
        from app import App
        with patch.object(App,'refresh',lambda self:None),patch('app.load_preferences',return_value={}):
            app=App();app.withdraw()
            try:
                report['tcl_library']=app.tk.eval('info library')
                report['tk_library']=str(app.tk.getvar('tk_library'))
                report['tcl_version']=app.tk.eval('info patchlevel')
                app.update_idletasks()
            finally:app.finish_close()
        report['gui_created']=True;report['passed']=True
    except Exception as error:
        report['error']=str(error);report['traceback']=traceback.format_exc()
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if sys.stdout:print(json.dumps({'passed':report['passed'],'report':str(output),'error':report.get('error')},ensure_ascii=True))
    if not report['passed']:raise SystemExit(1)


if __name__=='__main__':main()
