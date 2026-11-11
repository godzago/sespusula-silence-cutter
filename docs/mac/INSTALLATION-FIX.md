# Mac installation fix

The original Mac source kit can treat a linked folder path and its real path as different projects. Project discovery is now consistent with the canonical paths used by `Project`, and duplicate entries are merged. The issue was reproduced with a directory junction on Windows; the original user's exact failed test remains unconfirmed because the failure details were not supplied.

Download [SesPusula-Mac-kurulum-duzeltmesi.zip](https://github.com/godzago/sespusula-silence-cutter/releases/download/macos26-arm64-v0.8.1-source/SesPusula-Mac-kurulum-duzeltmesi.zip), extract it, and double-click **SesPusula Mac Duzelt.command** on the Mac.

The command targets `~/Desktop/sespusula for mac`, checks its identity, backs up four source/test files, installs the fix, and restarts app creation. It preserves the older SesPusulaMac app and CapCut projects. You do not need to download the 545 MB source kit again if it is already installed.

If a test fails again, the full test failure is written to `KURULUM-HATASI.txt` in the source folder and automatically opened in TextEdit. Test failures still stop the build; the checks have not been disabled.

Validation: 73 tests passed on Windows, including a linked-directory regression and the visible failure-report check. The patch installer was applied to a temporary copy of the original release files and its backups/results were verified. Native execution of the corrected Mac app remains unverified.

The source changes are available as [a reviewable patch](installation-path-fix.patch).
