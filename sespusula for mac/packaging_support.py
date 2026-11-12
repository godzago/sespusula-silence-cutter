"""Build-time selection of application files and platform dependencies."""
from email.parser import BytesParser
import hashlib
import json
from pathlib import Path
import shutil
import stat
import zipfile


RUNTIME_SOURCES = (
    'app.py', 'entrypoint.py', 'offline_worker.py', 'platform_support.py',
    'portable_selftest.py', 'review.py', 'silence_core.py', 'speech_analysis.py',
    'speech_worker.py', 'transcript_review.py', 'Programi Sil.py',
    'captions.py', 'export_pipeline.py', 'jump_cut.py', 'timeline_markers.py',
)
MAC_BUILD_SOURCES = ('build_mac.py', 'setup_mac.py', 'mac_target.py', 'packaging_support.py')


def mac_wheels(folder: Path, architecture: str) -> list[Path]:
    """Resolve locked wheels with Mac markers, independently of the build host."""
    from packaging.markers import default_environment
    from packaging.requirements import Requirement
    from packaging.utils import canonicalize_name

    environment=default_environment()
    environment.update(sys_platform='darwin',os_name='posix',platform_system='Darwin',
                       platform_machine=architecture,python_version='3.11',
                       python_full_version='3.11.9',extra='')
    packages={}
    for path in [*folder.glob('*.whl'),*(folder.parent/'common').glob('*.whl')]:
        with zipfile.ZipFile(path) as bundle:
            entry=next(n for n in bundle.namelist() if n.endswith('.dist-info/METADATA'))
            metadata=BytesParser().parsebytes(bundle.read(entry))
        name=canonicalize_name(metadata['Name'])
        if name in packages:raise ValueError(f'Birden fazla paket sürümü: {name}')
        packages[name]=(path,metadata)
    selected=set();pending=['faster-whisper','imageio-ffmpeg','psutil','pyinstaller']
    while pending:
        requirement=Requirement(pending.pop())
        name=canonicalize_name(requirement.name)
        if name not in packages:raise ValueError(f'Mac bağımlılığı eksik: {name}')
        path,metadata=packages[name]
        if not requirement.specifier.contains(metadata['Version']):
            raise ValueError(f'Mac bağımlılık sürümü uyuşmuyor: {requirement}')
        if name in selected:continue
        selected.add(name)
        for value in metadata.get_all('Requires-Dist',[]):
            dependency=Requirement(value)
            if dependency.marker is None or dependency.marker.evaluate(environment):
                pending.append(str(dependency))
    return sorted(packages[name][0] for name in selected)


def trim_windows_package(root: Path) -> list[dict]:
    """Remove developer-only components from a verified portable installation."""
    root=root.resolve()
    if not (root/'.runtime/python.exe').is_file() or not (root/'app.py').is_file():
        raise ValueError('Windows taşınabilir paket klasörü bekleniyor.')
    # Package metadata/licenses stay available for provenance and cache identity.
    relative_paths=[
        '.runtime/Lib/test', '.runtime/Lib/idlelib', '.runtime/Lib/turtledemo',
        '.runtime/Lib/ensurepip', '.runtime/Lib/site-packages/pip',
        '.runtime/Lib/site-packages/setuptools', '.runtime/Lib/site-packages/pkg_resources',
        '.runtime/Lib/site-packages/_distutils_hack',
        '.runtime/Lib/site-packages/onnxruntime/transformers',
        '.runtime/Lib/site-packages/onnxruntime/tools',
        '.runtime/Lib/site-packages/onnxruntime/quantization',
        '.runtime/Lib/site-packages/ctranslate2/converters',
        '.runtime/Lib/site-packages/ctranslate2/specs',
        'setup_local.py', 'tests',
        '.models/whisper-small/.cache',
    ]
    removed=[]
    for relative in relative_paths:
        path=root/relative
        if not path.exists():continue
        resolved=path.resolve()
        if not resolved.is_relative_to(root) or path.is_symlink():
            raise ValueError(f'Paket dışına çıkan yol: {path}')
        size=sum(p.stat().st_size for p in path.rglob('*') if p.is_file()) if path.is_dir() else path.stat().st_size
        if path.is_dir():shutil.rmtree(path)
        else:path.unlink()
        removed.append({'path':relative,'bytes':size})
    return removed


def archive_release(root: Path, output: Path) -> dict:
    """Archive a release without local state, build products or bytecode."""
    root=root.resolve();output=output.resolve()
    if output.exists():raise FileExistsError(output)
    if not (root/'app.py').is_file():raise ValueError('SesPusula paket klasörü bekleniyor.')
    paths=[]
    legacy=set()
    if (root/'.runtime/python.exe').is_file():legacy.add('KULLANIM.md')
    elif (root/'build-status.json').is_file():legacy.add('Baslat.pyw')
    for path in root.rglob('*'):
        relative=path.relative_to(root)
        if (relative.parts[0] in ('.state','.venv','.build','.packaging','.test-output','Dagitim','.git','Dogrulama') or
                any(part in ('__pycache__','.cache') for part in relative.parts) or
                path.suffix in ('.pyc','.log') or path==output or path.name in ('SHA256SUMS.json','gpt.md','AGENTS.md') or
                (len(relative.parts)==1 and path.name in legacy)):
            continue
        if path.is_symlink():raise ValueError(f'Kaynak pakette bağlantı var: {path}')
        if path.is_file():paths.append(path)
    paths.sort()
    manifest={}
    for path in paths:
        digest=hashlib.sha256()
        with path.open('rb') as stream:
            for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
        manifest[path.relative_to(root).as_posix()]=digest.hexdigest()
    checksum=root/'SHA256SUMS.json'
    checksum.write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf-8')
    with zipfile.ZipFile(output,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=1) as archive:
        for path in [*paths,checksum]:
            name=f'{root.name}/{path.relative_to(root).as_posix()}'
            info=zipfile.ZipInfo.from_file(path,name)
            info.create_system=3
            info.external_attr=(stat.S_IFREG|(0o755 if path.suffix in ('.command','.sh') else 0o644))<<16
            info.compress_type=zipfile.ZIP_STORED if path.suffix=='.whl' else zipfile.ZIP_DEFLATED
            info._compresslevel=1
            with path.open('rb') as source,archive.open(info,'w',force_zip64=True) as target:
                shutil.copyfileobj(source,target,1024*1024)
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:raise ValueError('ZIP doğrulaması başarısız.')
    return {'files':len(paths)+1,'zip_bytes':output.stat().st_size}
