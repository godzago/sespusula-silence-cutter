"""Prepare the existing offline ARM wheels and build a standalone app."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
from mac_target import require_native_mac

ROOT=Path(__file__).resolve().parent

def sha256(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
    return digest.hexdigest()

def verify_assets(root=ROOT):
    manifest=json.loads((root/'wheelhouse/arm64/manifest.json').read_text(encoding='utf-8'))
    for name,expected in manifest['sha256'].items():
        if Path(name).name!=name:raise ValueError('Gecersiz paket adi')
        path=root/'wheelhouse/arm64'/name
        if not path.is_file():path=root/'wheelhouse/common'/name
        if sha256(path)!=expected:raise ValueError(f'Paket saglama toplami gecersiz: {name}')
    model=root/'.models/whisper-small'
    manifest=json.loads((model/'local-manifest.json').read_text(encoding='utf-8'))
    for name,expected in manifest['files'].items():
        if Path(name).name!=name:raise ValueError('Gecersiz model adi')
        if sha256(model/name)!=expected:raise ValueError(f'Model saglama toplami gecersiz: {name}')

def environment_key(arch='arm64',root=ROOT):
    digest=hashlib.sha256()
    for value in (str(root.resolve()),arch,platform.python_version(),sys.executable):
        digest.update(value.encode('utf-8'));digest.update(b'\0')
    for relative in ('requirements-mac-arm64.lock','wheelhouse/arm64/manifest.json','.models/whisper-small/local-manifest.json'):
        digest.update((root/relative).read_bytes());digest.update(b'\0')
    # Revalidate runtime and GUI when source changes, even if wheels stay the same.
    for path in sorted(root.glob('*.py')):
        digest.update(path.name.encode('utf-8'));digest.update(path.read_bytes())
    return digest.hexdigest()

def environment_ready(python,checkpoint,key):
    try:
        if not python.is_file() or json.loads(checkpoint.read_text(encoding='utf-8')).get('key')!=key:return False
        result=subprocess.run([str(python),'-c',
            'import platform,sys; assert platform.machine()=="arm64"; assert sys.version_info[:2]==(3,11)'],
            capture_output=True,timeout=20)
        return result.returncode==0
    except (OSError,ValueError,AttributeError,subprocess.SubprocessError):return False

def main():
    parser=argparse.ArgumentParser()
    action=parser.add_mutually_exclusive_group()
    action.add_argument('--run',action='store_true');action.add_argument('--build',action='store_true')
    parser.add_argument('--verify',action='store_true')
    args=parser.parse_args()
    try:arch=require_native_mac()
    except RuntimeError as exc:raise SystemExit(str(exc))
    import tkinter
    python=ROOT/'.venv/bin/python3'
    checkpoint=ROOT/'.venv/.sespusula-setup.json';key=environment_key(arch)
    if args.verify or not environment_ready(python,checkpoint,key):
        checkpoint.unlink(missing_ok=True)
        verify_assets()
        if not python.exists():subprocess.run([sys.executable,'-m','venv',str(ROOT/'.venv')],check=True)
        subprocess.run([str(python),'-m','pip','install','--no-index','--only-binary=:all:',
            '--find-links',str(ROOT/'wheelhouse/arm64'),'--find-links',str(ROOT/'wheelhouse/common'),
            '--require-hashes','-r',str(ROOT/'requirements-mac-arm64.lock')],cwd=ROOT,check=True)
        subprocess.run([str(python),str(ROOT/'portable_selftest.py')],cwd=ROOT,check=True)
        checkpoint.write_text(json.dumps({'key':key,'arch':arch,'python':platform.python_version()}),encoding='utf-8')
    if args.build:subprocess.run([str(python),str(ROOT/'build_mac.py')],cwd=ROOT,check=True)
    elif args.run:subprocess.run([str(python),str(ROOT/'entrypoint.py')],cwd=ROOT,check=True)

if __name__=='__main__':main()
