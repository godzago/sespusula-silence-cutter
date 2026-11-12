"""Remove a selected SesPusula installation after showing its exact contents.

Standard library only. CapCut projects, source media and unrelated files are
excluded. Windows cleanup runs after this Python (possibly bundled) exits.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time


DIRECTORIES = {'.models', '.packaging', '.state', '.test-output', '.venv',
               '.runtime', '.build', 'Dagitim', 'Lisanslar', 'packaging',
               'tests', 'vendor', 'wheelhouse', '__pycache__', 'Dogrulama'}
FILES = {'app.py', 'Baslat.pyw', 'entrypoint.py', 'offline_worker.py',
         'platform_support.py', 'portable_selftest.py', 'review.py',
         'silence_core.py', 'speech_analysis.py', 'speech_worker.py', 'captions.py', 'jump_cut.py',
         'timeline_markers.py', 'export_pipeline.py',
         'transcript_review.py', 'setup_local.py', 'setup_mac.py',
         'captions.py', 'export_pipeline.py', 'jump_cut.py', 'timeline_markers.py',
         'mac_target.py', 'mac_launcher.sh',
         'build_mac.py', 'build_windows_portable.py', 'prepare_mac_project.py', 'packaging_support.py', 'archive_release.py',
         'Programi Sil.py', 'Programi Sil.command', 'Programi Sil.cmd',
         'SesPusula.cmd', 'SesPusula.exe', 'SesPusula.lnk', '.gitignore',
         'README.md', 'KULLANIM.md', 'BURADAN BASLA.txt', 'GUNCELLEME.md',
         'build-info.json', 'build-status.json', 'SHA256SUMS.json',
         'requirements-lock.txt', 'requirements-mac-arm64.lock',
         'requirements-mac-x86_64.lock', 'Kur ve Ac.command',
         'Mac Uygulamasini Olustur.command', 'Test Et.command',
         'Kendini Test Et.cmd'}


def linked(path):
    return path.is_symlink() or bool(getattr(path.lstat(), 'st_file_attributes', 0) & 0x400)


def removal_plan(folder, include_state=False):
    original = Path(folder).absolute()
    if linked(original):
        raise ValueError('Yönlendirilmiş klasör kaldırılamaz.')
    root = original.resolve()
    if root == root.parent or root == Path.home().resolve():
        raise ValueError('Bir SesPusula program klasörü seçin.')
    if not all((root / name).is_file() for name in ('app.py', 'silence_core.py', 'speech_worker.py')):
        raise ValueError('Bu klasörde SesPusula kaynak dosyaları bulunamadı.')
    result = []
    for path in root.iterdir():
        if (path.name in DIRECTORIES and path.is_dir()) or (path.name in FILES and path.is_file()):
            if linked(path):
                raise ValueError(f'Yönlendirilmiş öğe kaldırılamaz: {path}')
            result.append(path)
    if include_state and sys.platform == 'darwin':
        state = Path.home() / 'Library/Application Support/SesPusulaSilenceCutter'
        if state.exists():
            if linked(state):
                raise ValueError('Ayar klasörü yönlendirilmiş; kaldırılmadı.')
            result.append(state)
    return root, sorted(result)


def remove_now(root, paths):
    """Called from a helper copied outside the selected installation."""
    allowed = set(removal_plan(root, include_state=True)[1])
    for path in paths:
        path = Path(path)
        if path not in allowed:
            raise ValueError(f'İzin verilmeyen kaldırma yolu: {path}')
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink(missing_ok=True)
    # An unknown document or media file keeps the installation folder alive.
    if not any(root.iterdir()):
        root.rmdir()


def launch_cleanup(root, paths):
    scratch = Path(tempfile.mkdtemp(prefix='sespusula-kaldir-'))
    plan = scratch / 'plan.json'
    plan.write_text(json.dumps({'root': str(root), 'paths': [str(p) for p in paths]}, ensure_ascii=False), encoding='utf-8')
    if sys.platform == 'win32':
        # The helper runs in native PowerShell throughout; no cmd/rmdir bridge.
        helper = scratch / 'remove.ps1'
        helper.write_text('''param([string]$Plan, [int]$ParentId)
$ErrorActionPreference = 'Stop'
$data = Get-Content -LiteralPath $Plan -Raw -Encoding UTF8 | ConvertFrom-Json
Wait-Process -Id $ParentId -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 500
$root = [IO.Path]::GetFullPath($data.root)
if ($root -eq [IO.Path]::GetPathRoot($root) -or $root -eq $env:USERPROFILE) { throw 'Invalid root' }
foreach ($marker in @('app.py','silence_core.py','speech_worker.py')) {
    if (-not (Test-Path -LiteralPath (Join-Path $root $marker) -PathType Leaf)) { throw 'Invalid installation' }
}
foreach ($entry in $data.paths) {
    $absolute = [IO.Path]::GetFullPath($entry)
    if ([IO.Path]::GetDirectoryName($absolute) -ne $root) { throw 'Path outside installation' }
    if ((Get-Item -LiteralPath $absolute -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Linked entry' }
}
try {
    foreach ($entry in $data.paths) { Remove-Item -LiteralPath $entry -Force -Recurse }
    if (@(Get-ChildItem -LiteralPath $root -Force).Count -eq 0) { Remove-Item -LiteralPath $root -Force }
} catch {
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.MessageBox]::Show($_.Exception.Message, 'SesPusula kaldirma hatasi') | Out-Null
}
''', encoding='utf-8-sig')
        executable = Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
        subprocess.Popen([str(executable), '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(helper),
                          '-Plan', str(plan), '-ParentId', str(os.getpid())], cwd=scratch,
                         creationflags=subprocess.CREATE_NO_WINDOW)
    else:
        helper = scratch / 'Programi Sil.py'
        shutil.copy2(Path(__file__), helper)
        subprocess.Popen([sys.executable, str(helper), '--finish', str(plan), '--parent', str(os.getpid())],
                         cwd=scratch, start_new_session=True)


def confirm_removal(window, root, paths):
    import tkinter as tk
    from tkinter import ttk
    dialog=tk.Toplevel(window)
    dialog.title('SesPusula kaldır')
    dialog.geometry('680x480')
    dialog.minsize(500,380)
    box=ttk.Frame(dialog,padding=16)
    box.pack(fill='both',expand=True)
    ttk.Label(box,text='Önce SesPusula’yı kapatın. Bu kurulum kaldırılacak:',wraplength=630).pack(anchor='w')
    ttk.Label(box,text=str(root),wraplength=630).pack(anchor='w',pady=(6,12))
    body=ttk.Frame(box);body.pack(fill='both',expand=True)
    scroll=ttk.Scrollbar(body);scroll.pack(side='right',fill='y')
    listing=tk.Text(body,wrap='word',height=10,yscrollcommand=scroll.set)
    listing.pack(fill='both',expand=True);scroll.configure(command=listing.yview)
    listing.insert('1.0','\n'.join(str(p) for p in paths));listing.configure(state='disabled')
    ttk.Label(box,text='Program, modeller ve yerel ayarlar silinir. CapCut projeleri, kaynak medyalar ve liste dışındaki dosyalar korunur.',wraplength=630).pack(anchor='w',pady=12)
    result=[]
    def choose(value):
        result.append(value);dialog.destroy()
    buttons=ttk.Frame(box);buttons.pack(fill='x')
    ttk.Button(buttons,text='Vazgeç',command=lambda:choose(False)).pack(side='right')
    ttk.Button(buttons,text='Listelenenleri sil',command=lambda:choose(True)).pack(side='right',padx=8)
    dialog.protocol('WM_DELETE_WINDOW',lambda:choose(False))
    dialog.grab_set();window.wait_window(dialog)
    return bool(result and result[0])


def main():
    parser = argparse.ArgumentParser(description='Seçilen SesPusula kurulumunu kaldır.')
    parser.add_argument('--target', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--list', action='store_true', help='Yalnızca silinecek yolları göster.')
    parser.add_argument('--include-state', action='store_true', help='Mac uygulamasının kişisel ayarlarını da kaldır.')
    parser.add_argument('--finish', type=Path, help=argparse.SUPPRESS)
    parser.add_argument('--parent', type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.finish:
        data = json.loads(args.finish.read_text(encoding='utf-8'))
        if not args.parent or args.parent <= 1:
            raise ValueError('Geçersiz üst işlem.')
        for _ in range(600):
            try:
                os.kill(args.parent, 0)
            except ProcessLookupError:
                break
            time.sleep(.1)
        else:
            raise RuntimeError('Kaldırma başlatıcısı kapanmadı.')
        time.sleep(.5)
        remove_now(Path(data['root']), data['paths'])
        return
    root, paths = removal_plan(args.target, args.include_state)
    if args.list:
        print('\n'.join(map(str, paths)))
        return
    import tkinter as tk
    window = tk.Tk()
    window.withdraw()
    try:
        if confirm_removal(window, root, paths):
            launch_cleanup(root, paths)
    finally:
        window.destroy()


if __name__ == '__main__':
    main()
