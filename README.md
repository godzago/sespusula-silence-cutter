# SesPusula — Silence Cutter for CapCut

SesPusula removes silence from pre-aligned CapCut recordings. It analyzes your clean microphone and applies matching cuts across supported audio and video tracks, saving a separate project copy.

![SesPusula desktop interface](docs/images/sespusula-app.png)

The interface is in Turkish. Normal analysis runs locally.

## What it does

- Automatically cuts silence across aligned tracks, with optional review.
- Marks possible repeated takes without deleting them.
- Creates optional editable Turkish subtitles and SRT files.
- Keeps the original project and source media unchanged.

I built it for my UlasCS videos. In my own workflow, an editing stage fell from about six hours to 30 minutes. This is personal experience, not a benchmark or a guaranteed result.

## Installation

### Windows

If you already have the complete portable package, open `SesPusula.exe` or `SesPusula.cmd`. Keep `.runtime`, `.models`, and `vendor` with the app.

**This repository contains source code, not the complete Windows portable package.** To run from source, install Python 3.11 with Tk and FFmpeg, then:

```powershell
git clone https://github.com/godzago/sespusula-silence-cutter.git
cd sespusula-silence-cutter
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
```

Make `ffmpeg` available on your `PATH`. Prepare the local speech model:

1. Download `config.json`, `model.bin`, `tokenizer.json`, and `vocabulary.txt` from [the pinned faster-whisper-small revision](https://huggingface.co/Systran/faster-whisper-small/tree/536b0662742c02347bc0e980a01041f333bce120).
2. Put them in `.models/whisper-small/`.
3. Copy [docs/model-manifest.json](docs/model-manifest.json) into that folder as `local-manifest.json`.

Launch with:

```powershell
.\.venv\Scripts\python.exe entrypoint.py
```

The existing Windows portable environment is tested; a fresh source installation has not yet been verified. Windows portable build scripts are not included.

### Mac — Apple Silicon, macOS 26+

The [Mac release](https://github.com/godzago/sespusula-silence-cutter/releases/tag/macos26-arm64-v0.8.1-source) is a **source/build kit, not a ready-made `.app`**. It includes the offline dependencies and model that Git excludes.

Download and extract the kit, then overlay the current files from [`sespusula for mac/`](sespusula%20for%20mac/README.md), preserving `wheelhouse/` and `.models/`. Install Python 3.11 with Tk and run `Mac Uygulamasini Olustur.command`. The output is `Dagitim/arm64/SesPusula.app`.

If you use the original release without the current sources, apply the [installation fix](docs/mac/INSTALLATION-FIX.md) first. See the [Mac guide](sespusula%20for%20mac/README.md) for build steps and troubleshooting.

**The current Mac app has not been built or run on a Mac.** Windows tests of its source do not verify native Mac operation.

## Usage

1. Align your recordings in CapCut and save the project.
2. Open SesPusula, select the project, and choose the clean microphone track.
3. Click **Analiz et** to analyze the whole timeline.
4. Optionally review cuts, add Turkish subtitles, or mark possible repeats.
5. Save and close CapCut, then click **CapCut kopyası oluştur**.
6. Open the new copy in CapCut and check the result before exporting.

Keep source media at its original location: the copy still references those files. SesPusula preserves existing alignment and audio levels; align the recordings yourself before analysis.

Silence cuts stop 100 ms before the next detected speech and round inward to full video frames. Start/end silence and gaps between microphone clips are included. If no speech is detected, the whole recording is not automatically deleted. Detection can make mistakes; review the output.

## Compatibility

- Version **0.8.1**; CapCut JSON **360000**, one active timeline. Developed with Windows CapCut **9.6.0.4097**.
- Supports normal-speed audio/video, images, and basic text within its compatibility checks.
- Speed ramps, reverse playback, compound clips, keyframes, transitions, word-timed captions, and unsupported effects may block output.
- Uses Silero VAD and Whisper small, with Turkish transcription on CPU/int8.
- Automated JSON/SRT checks passed. Playback, subtitle/marker appearance, and export inside CapCut remain unverified.

## Development and privacy

Windows tests (a desktop session is required for GUI tests):

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Local settings, caches, reviews, models, credentials, and recordings should stay outside Git. For bug reports, include the app version, CapCut version, and error message; remove personal paths and recording content.

Third-party notices: [Lisanslar](Lisanslar/). A license for the application's own source has not yet been selected. SesPusula is independent and is not affiliated with CapCut.

[Turkish usage guide](docs/README.tr.md)
