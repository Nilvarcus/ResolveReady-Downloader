# Project Overview

## Purpose

Resolve-Ready Downloader is a Windows desktop application for editors who want to download online video and convert it into a predictable format for DaVinci Resolve.

The application combines two operations:

1. Download media through `yt-dlp`.
2. Convert the downloaded media through HandBrakeCLI using the `Resolve Ready` preset.

The conversion stage is important because downloaded media can use variable frame rate, browser-oriented codecs, or separate audio/video streams that are inconvenient in an editing workflow.

## Main features

- Multiple URLs can be pasted into a queue.
- URLs can be separated by spaces, commas, or newlines.
- Playlist URLs are expanded into individual queue items.
- Duplicate queue entries are rejected using canonical video identities.
- Videos already completed in the selected output folder are skipped before entering the queue.
- Downloads are processed sequentially.
- Download and conversion progress is shown in the GUI.
- A target quality of 1080p, 1440p, or 2160p can be selected.
- If the target is unavailable, the highest usable format is selected.
- Separate video and audio streams are merged with FFmpeg when appropriate.
- HandBrake produces a Resolve-oriented H.264/AAC MP4.
- NVIDIA NVENC is preferred when detected; x264 is the CPU fallback.
- Downloads can be cancelled and partial files are cleaned up.
- Settings, history, and error logs persist locally.
- yt-dlp nightly is attempted first while YouTube extraction is changing rapidly. A verified stable package remains the fallback.

## Runtime modes

### Source mode

Started with:

```bash
python gui_app.py
```

In source mode:

- Python imports `yt_dlp` from the active environment.
- `yt-dlp[default]` supplies yt-dlp and `yt-dlp-ejs`.
- The updater runs pip with `--pre` to try the nightly channel first.
- If nightly installation fails, the updater tries the stable package.
- `HandBrakeCLI.exe`, `ffmpeg.exe`, and `resolve_preset.json` are expected beside the source files.

### Frozen portable mode

Started with:

```text
dist/ResolveReadyDownloader/ResolveReadyDownloader.exe
```

In frozen mode:

- PyInstaller packages the GUI and supporting Python modules.
- yt-dlp itself is excluded from the executable and downloaded as `yt-dlp.zip`.
- The updater tries the latest nightly zipapp from `yt-dlp/yt-dlp-nightly-builds`.
- A candidate package is validated and imported before replacing the active package.
- The existing or newly downloaded stable zipapp is used if nightly verification fails.
- HandBrakeCLI, FFmpeg, the preset, the icon, and the detected JavaScript runtime are bundled by the active spec when available.

## Repository map

| Path | Responsibility |
|---|---|
| `gui_app.py` | CustomTkinter window, queue UI, settings, cancellation, status display, and updater lifecycle. |
| `downloader.py` | yt-dlp integration, format selection, playlist extraction, media merging, HandBrake execution, GPU detection, history, and cleanup. |
| `updater.py` | Nightly-first yt-dlp update logic, stable fallback, zipapp validation, import verification, and atomic replacement. |
| `logger.py` | Append-only local error log plus log reading and clearing helpers. |
| `resolve_preset.json` | HandBrake preset named `Resolve Ready`. |
| `requirements.txt` | Runtime and build Python dependencies. |
| `ResolveReadyDownloader.spec` | Active PyInstaller build definition. |
| `tests/test_core.py` | Offline unit tests for format selection, updater helpers, downloader flow, and HandBrake behavior. |
| `doc/` | Project documentation. |

## Local runtime files

These files are generated or updated while the program runs:

- `settings.json` — selected output directory and resolution.
- `download_history.json` — completed download identity, title, channel, URL, and timestamp entries for the selected output folder.
- `error.log` — diagnostics and tracebacks.
- `.ytdlp_last_check_v3` — timestamp of the last verified yt-dlp update check.
- `yt-dlp.zip` — active frozen-mode yt-dlp package.

They are user state, not source code.
