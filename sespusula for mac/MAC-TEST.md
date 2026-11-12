# First native Mac test

The build verifies source tests, arm64 output, app metadata, local code signing, bundled dependencies, multiprocessing, Whisper loading, offline VAD, and GUI creation. It stops before writing a successful build report if a required step fails.

Record the chip/model, exact macOS version, and CapCut version when testing. One successful Neo test does not establish a tested M1–M5 device matrix.

## 1. Build and launch

- Run `Mac Uygulamasini Olustur.command`.
- Confirm `Dagitim/arm64/mac-native-self-test.json` contains `"passed": true`.
- Confirm `Dagitim/arm64/build-report.json` exists and reports `arm64`.
- Copy `SesPusula.app` to Applications and open it from there. This checks relocation independently of the source folder.
- Check the new design at the normal display size and in a smaller window. No main action should disappear below the window.

## 2. Editing and source protection

- Start with a short, already aligned project containing camera, screen, and clean-microphone tracks.
- Select the correct microphone and analyze it. Speech should stay; silence should be selected without an approval queue.
- Listen to a cut and its edited preview. Keep it, then add it back. Duration cards must update.
- If repeats are detected, they must remain markers and must not delete speech.
- Generate captions, edit a line, and export a copy with CapCut saved and closed.
- Open the original and the new project separately. The original must remain unchanged.

## 3. CapCut playback and export

- Check several cuts near the start, middle, end, and around a five-minute analysis boundary.
- Check for clipped words, lip-sync changes, or unexpected audio-level changes.
- Check editable captions and SRT timing. Regenerating captions should replace the tool's previous caption layer.
- Check repeat markers when present.
- Export a short video in CapCut and watch/listen to it.

Send the two generated JSON reports and `.build/son-islem.log` if the build fails. Remove personal paths before sharing reports publicly. Do not send private recordings unless needed and explicitly chosen.
