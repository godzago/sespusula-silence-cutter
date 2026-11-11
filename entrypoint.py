"""GUI and inference entry point, also usable from a native frozen app."""
from pathlib import Path
import runpy
import sys
import traceback

def main():
    # PyInstaller must divert multiprocessing/resource-tracker children before
    # importing the GUI or interpreting their Python flags as project paths.
    import multiprocessing
    multiprocessing.freeze_support()
    from platform_support import configure_environment,state_root
    configure_environment()
    if sys.argv[1:]==['--process-probe']:
        from platform_support import multiprocessing_probe
        return multiprocessing_probe()
    if len(sys.argv)>1 and sys.argv[1]=='--speech-worker':
        sys.argv=[sys.argv[0],*sys.argv[2:]]
        from speech_worker import main as worker_main
        return worker_main()
    if len(sys.argv)>2 and sys.argv[1]=='--run-script':
        script=Path(sys.argv[2]);sys.argv=[str(script),*sys.argv[3:]]
        return runpy.run_path(str(script),run_name='__main__')
    if len(sys.argv)>1 and sys.argv[1]=='--self-test':
        sys.argv=[sys.argv[0],*sys.argv[2:]]
        from portable_selftest import main as test_main
        return test_main()
    import argparse
    parser=argparse.ArgumentParser(prog='SesPusula')
    parser.add_argument('--project')
    parser.add_argument('folder',nargs='?')
    args=parser.parse_args()
    if args.project and args.folder:
        parser.error('Proje klasörünü yalnızca bir kez belirtin.')
    try:
        from app import App
        App(args.project or args.folder).mainloop()
    except Exception:
        folder=state_root();folder.mkdir(parents=True,exist_ok=True)
        log=folder/'baslatma_hatasi.log';log.write_text(traceback.format_exc(),encoding='utf-8')
        try:
            from tkinter import messagebox
            messagebox.showerror('SesPusula',f'Uygulama açılamadı. Ayrıntılar:\n{log}')
        except Exception:
            if sys.stderr:sys.stderr.write(log.read_text(encoding='utf-8'))
        raise SystemExit(1)


if __name__=='__main__':main()
