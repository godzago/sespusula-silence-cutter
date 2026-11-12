"""Native Apple Silicon build requirements, with no model imports."""
import platform
import sys

MINIMUM_MACOS=(26,0)
TARGET_ARCH='arm64'

def require_native_mac():
    if sys.platform!='darwin':
        raise RuntimeError('Bu adim gercek bir Mac uzerinde calistirilir. Windows .app derleyemez.')
    if platform.machine()!=TARGET_ARCH:
        raise RuntimeError('Apple Silicon arm64 Python gerekli. Rosetta/Intel Python yerine python.org universal2 Python 3.11 kullanin.')
    if sys.version_info[:2]!=(3,11):
        raise RuntimeError('Bir kez kurulum icin Tk iceren Python 3.11 gerekli. Olusan .app ayri Python istemez.')
    try:version=tuple(int(part) for part in platform.mac_ver()[0].split('.')[:2])
    except ValueError:version=()
    if version<MINIMUM_MACOS:
        raise RuntimeError('Bu paket macOS 26 veya ustunu hedefler.')
    return TARGET_ARCH
