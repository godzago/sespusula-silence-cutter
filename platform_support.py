"""OS-specific integration and relocatable application paths."""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import sysconfig

PLATFORM=sys.platform
VERSION='0.8.1'
SOURCE_ROOT=Path(__file__).resolve().parent


def asset_root() -> Path:
    return Path(getattr(sys,'_MEIPASS',SOURCE_ROOT))


def application_home() -> Path:
    if getattr(sys,'frozen',False):
        executable=Path(sys.executable).resolve()
        bundle=next((p for p in executable.parents if p.suffix=='.app'),None)
        return bundle.parent if bundle else executable.parent
    return SOURCE_ROOT


def state_root(app: Path | None=None) -> Path:
    if PLATFORM=='darwin' and getattr(sys,'frozen',False):
        return Path.home()/'Library/Application Support/SesPusulaMac'
    return (app or application_home())/'.state'


def runtime_python(app: Path | None=None) -> Path:
    if getattr(sys,'frozen',False):return Path(sys.executable)
    app=app or application_home()
    choices=([app/'.runtime/python.exe',app/'.venv/Scripts/python.exe'] if PLATFORM=='win32'
             else [app/'.venv/bin/python3',app/'.venv/bin/python'])
    return next((p for p in choices if p.is_file()),Path(sys.executable))


def package_roots() -> list[Path]:
    if getattr(sys,'frozen',False):return [asset_root()]
    return [Path(sysconfig.get_paths()['purelib'])]


def worker_command(python: Path,request: Path,script: Path | None=None) -> list[str]:
    if getattr(sys,'frozen',False):
        return ([str(python),'--run-script',str(script),str(request)] if script is not None
                else [str(python),'--speech-worker',str(request)])
    return [str(python),str(script or SOURCE_ROOT/'speech_worker.py'),str(request)]


def _process_probe_child(channel):
    channel.put('ok')


def multiprocessing_probe():
    """Exercise the frozen spawn entry point and the POSIX resource tracker."""
    import multiprocessing
    context=multiprocessing.get_context('spawn')
    channel=context.Queue()
    process=context.Process(target=_process_probe_child,args=(channel,))
    try:
        process.start()
        if channel.get(timeout=15)!='ok':
            raise RuntimeError('Alt süreç yanıtı geçersiz.')
        process.join(timeout=15)
        if process.exitcode!=0:
            raise RuntimeError('Alt süreç düzgün kapanmadı.')
    finally:
        if process.pid is not None:
            if process.is_alive():process.terminate()
            process.join(timeout=5)
        channel.close()
        channel.join_thread()


def capcut_indexes(home: Path | None=None) -> list[Path]:
    home=home or Path.home()
    if PLATFORM=='darwin':
        roots=[home/'Movies/CapCut/UserData/Projects',home/'Movies/CapCut/User Data/Projects',
               home/'Library/Application Support/CapCut/User Data/Projects']
    else:
        roots=[home/'AppData/Local/CapCut/User Data/Projects']
    return [root/'com.lveditor.draft/root_meta_info.json' for root in roots]


def default_capcut_index() -> Path:
    indexes=capcut_indexes()
    return next((p for p in indexes if p.is_file()),indexes[0])


def ffmpeg_path(app: Path | None=None) -> Path | None:
    app=app or application_home()
    roots=[app/'vendor/imageio_ffmpeg/binaries',asset_root()/'imageio_ffmpeg/binaries']
    spec=importlib.util.find_spec('imageio_ffmpeg')
    if spec and spec.origin:roots.append(Path(spec.origin).parent/'binaries')
    patterns=('ffmpeg*.exe',) if PLATFORM=='win32' else (('ffmpeg*macos*','ffmpeg*osx*') if PLATFORM=='darwin' else ('ffmpeg*linux*',))
    for root in roots:
        for pattern in patterns:
            for path in sorted(root.glob(pattern)):
                if path.is_file():return path
    found=shutil.which('ffmpeg')
    return Path(found) if found else None


def capcut_is_running() -> bool:
    import psutil
    for process in psutil.process_iter(['name']):
        try:
            name=(process.info['name'] or '').casefold()
            if name in ('capcut','capcut.exe','jianyingpro','jianyingpro.exe'):return True
        except psutil.NoSuchProcess:continue
    return False


def configure_environment() -> None:
    app=application_home()
    tcl=app/'.runtime/tcl'
    if PLATFORM=='win32' and (tcl/'tcl8.6').is_dir():
        os.environ['TCL_LIBRARY']=str(tcl/'tcl8.6')
        os.environ['TK_LIBRARY']=str(tcl/'tk8.6')


class AudioPlayer:
    def __init__(self):self.process=None

    def play(self,path: Path) -> None:
        self.stop()
        if PLATFORM=='win32':
            import winsound
            winsound.PlaySound(str(path),winsound.SND_FILENAME|winsound.SND_ASYNC)
        elif PLATFORM=='darwin':
            self.process=subprocess.Popen(['/usr/bin/afplay',str(path)],stdin=subprocess.DEVNULL,
                                          stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        else:raise RuntimeError('Bu işletim sisteminde ses önizleme desteklenmiyor.')

    def stop(self) -> None:
        if PLATFORM=='win32':
            import winsound
            winsound.PlaySound(None,0)
        if self.process is not None:
            if self.process.poll() is None:
                self.process.terminate()
                try:self.process.wait(timeout=2)
                except subprocess.TimeoutExpired:self.process.kill();self.process.wait()
            self.process=None


def open_folder(path: Path) -> None:
    if PLATFORM=='win32':os.startfile(str(path))
    elif PLATFORM=='darwin':subprocess.Popen(['/usr/bin/open',str(path)],stdin=subprocess.DEVNULL)
    else:raise RuntimeError('Klasörü dosya yöneticisinde elle açın.')
