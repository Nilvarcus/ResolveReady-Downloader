# Development and Build

## Source setup

Use a dedicated virtual environment. On Windows:

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -U pip
.venv/Scripts/python.exe -m pip install -r requirements.txt
```

Install or provide these external runtime assets:

- Deno 2.3+ is recommended for YouTube extraction.
- `HandBrakeCLI.exe`.
- `ffmpeg.exe`.
- `resolve_preset.json`.

Run the source application with:

```bash
.venv/Scripts/python.exe gui_app.py
```

If the JavaScript runtime is not on PATH:

```text
YTDLP_JS_RUNTIME=C:\path\to\deno.exe
```

## Tests

The repository has offline tests that do not download media:

```bash
python -m unittest discover -s tests -v
```

The tests cover:

- Resolution-aware format selection.
- Combined-format fallback selection.
- Image-only format classification.
- Runtime path discovery.
- Nightly updater endpoint and pip flag behavior.
- Zipapp validation.
- Final downloaded filepath handoff.
- HandBrake process output and cleanup.

Live YouTube tests are intentionally separate because they depend on network state, upstream client behavior, runtime setup, and potentially large media files.

## Active build definition

The source of truth for the portable build is:

```text
ResolveReadyDownloader.spec
```

Build it with:

```bash
pyinstaller --clean --noconfirm ResolveReadyDownloader.spec
```

The result is:

```text
dist/ResolveReadyDownloader/ResolveReadyDownloader.exe
```

Use the exact executable from the fresh build. Older release folders and stale root-level executables may contain different Python modules, updater logic, or PyInstaller imports.

## What the build includes

The executable folder contains:

- The application executable.
- Python runtime and packaged application modules.
- CustomTkinter assets.
- `HandBrakeCLI.exe`.
- `ffmpeg.exe`.
- `resolve_preset.json`.
- The application icon.
- Deno or Node when found by the spec at build time.

The build does not package yt-dlp directly. The updater downloads `yt-dlp.zip` beside the executable so yt-dlp can change independently of the main application.

## Release verification

Before distributing a build:

1. Build in a clean environment.
2. Confirm the executable title includes the current app version.
3. Launch the exact executable from the fresh `dist/ResolveReadyDownloader/` folder.
4. Confirm the startup updater reaches either nightly-ready or stable-fallback-ready.
5. Confirm the download button stays disabled if neither package can be verified.
6. Confirm Deno/Node is detected.
7. Confirm FFmpeg and HandBrake paths are valid.
8. Test one public video with a small output target.
9. Confirm separate streams merge correctly.
10. Confirm HandBrake creates the `_Handbraked.mp4` file.
11. Confirm the intermediate download is removed only after successful conversion.
12. Test cancellation and inspect for leftover `.part` files.
13. Inspect `error.log` and the generated updater marker.

## Runtime update policy

Source mode uses pip at startup. Frozen mode downloads a zipapp. Both modes prefer nightly while the current YouTube issue is active and use stable as a fallback.

The updater uses `.ytdlp_last_check_v3` to avoid unnecessary network requests after a verified update. Changing the marker filename is a deliberate way to force a one-time dependency check after updater policy changes.
