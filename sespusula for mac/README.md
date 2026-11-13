# SesPusula for Mac

**The current SesPusula workflow, with the dark Bento interface, prepared for Apple Silicon and macOS 26.**

SesPusula removes silence from CapCut projects using your clean microphone. It applies matching cuts across supported tracks, adds optional Turkish subtitles, and marks possible repeats. It creates a separate project copy and keeps your original recording files unchanged.

This folder is a **Mac build kit**, not an already compiled `.app`. The final application must be built on a Mac. After that, you can use the resulting app without Python or Terminal.

## Make the app once

### Using the Git checkout

Git contains the Mac source files, not the offline dependencies or model. Download and extract the [Mac build kit](https://github.com/godzago/sespusula-silence-cutter/releases/tag/macos26-arm64-v0.8.1-source), then copy this folder's tracked source files over the extracted kit, preserving its `wheelhouse/` and `.models/` folders. The source here already includes the linked-folder installation fix. A Git checkout alone cannot perform the offline build.

The bundled-assets and validation fields in `build-status.json` describe the prepared offline kit; those assets are excluded from Git. Native Mac execution remains unverified.

1. Copy this whole folder to your Mac. If transferring from Windows, use the supplied source ZIP so `.command` launch permissions are preserved.
2. If Python 3.11 with Tk is not already installed, install the macOS universal2 version from [python.org](https://www.python.org/downloads/macos/). This is only a build requirement.
3. Double-click **`Mac Uygulamasini Olustur.command`**.
4. Wait for dependency checks, tests, packaging, and the application's own offline self-test. The first build takes longer than later launches.
5. Finder opens the result: **`Dagitim/arm64/SesPusula.app`**.
6. Drag **`SesPusula.app`** to Applications, then open it like a normal app.

If Finder does not run a source command, open Terminal, type `bash `, drag `Mac Uygulamasini Olustur.command` into the window, and press Enter.

The build uses the included offline wheels and Whisper model. Once Python is installed, package installation and normal processing do not require internet access. The output ZIP contains only the standalone app and is created at `Dagitim/arm64/SesPusula-0.8.1-macOS26-arm64.zip`.

The local build uses ad-hoc signing. It is not Developer ID signed or notarized. macOS may require an explicit first-open approval for an app transferred from another computer.

## Daily workflow

1. Align your camera, screen recording, and clean microphone in CapCut.
2. Open SesPusula and choose your CapCut project and microphone track.
3. Select **Analiz et**. The whole timeline is analyzed.
4. Optionally review cuts, prepare Turkish subtitles, or mark possible repeated takes.
5. Save and close CapCut, then select **CapCut kopyası oluştur**.
6. Open the new project copy in CapCut and review it before exporting.

Silence is cut until 100 ms before the next detected speech, with inward video-frame rounding. Repeats are markers, never automatic deletions. Review is optional; there is no approval queue. Audio levels and existing alignment are preserved.

## Target and validation

The intended target is **native arm64 on macOS 26 or later**, including M1–M5 and MacBook Neo. There is no chip-name whitelist. Intel/Rosetta builds are rejected to avoid mixing architectures. Speech processing uses CPU/int8; this package does not add Metal or Neural Engine acceleration.

Shared tests, Mac adapter simulations, wheel dependency resolution, model/wheel hashes, and archive permissions are checked on Windows. **The new app has not yet been built or run on macOS.** A successful older Mac version does not verify this new version. The Mac build runs the test suite and validates the actual frozen app before creating the distributable ZIP.

After your first Mac build, follow [MAC-TEST.md](MAC-TEST.md). Passing the automated app self-test does not prove that the CapCut output looks or sounds correct.

CapCut JSON version 360000 and one active timeline are supported. Speed ramps, compound clips, reverse playback, keyframes, transitions, word-timed captions, and unsupported effects may block output. Keep all source media at their original paths.

## Local data

The new standalone app stores its settings, cache, and reviews in `~/Library/Application Support/SesPusulaSilenceCutter`. It uses a different bundle identifier and settings folder from the old SesPusulaMac app. Existing Mac source and app files are not automatically replaced.

Windows executables, the Windows runtime, user media, private reviews, and previous build artifacts are not included. Full source-kit archives also exclude local state and test reports with local file paths.

SesPusula is an independent project and is not affiliated with CapCut. A license for the application's own source has not yet been selected.

[Türkçe başlangıç rehberi](BURADAN-BASLA.md)
