# Resolve-Ready Downloader

A sleek, intuitive desktop application designed for video editors. It allows you to effortlessly download videos from YouTube and 1000+ other sites in up to 4K resolution and automatically transcodes them into a high-performance, editing-friendly format optimized for DaVinci Resolve.

Built with Python, `yt-dlp`, and HandBrakeCLI, wrapped in a beautiful modern GUI using **CustomTkinter**.

Detailed project documentation is available in [`doc/`](doc/README.md).

## ✨ Features

### Download & Queue
- **Download Queue System:** Paste multiple links at once (separated by commas, spaces, or newlines) and they're processed sequentially. Each item appears in a scrollable queue with color-coded status indicators (Pending, Processing, Done, Error, Cancelled).
- **Playlist Support:** Playlist URLs are automatically expanded into individual video downloads — each gets its own queue entry.
- **Duplicate Detection:** Adding a URL that's already in the queue is flagged with a warning. Videos already recorded as completed in the selected folder's `download_history.json` are skipped before download.
- **Per-Item Control:** Remove any queue item with the ✕ button, or bulk-clear all completed/error/cancelled items with the "Clear" button.
- **Cancellation:** Abort in-progress downloads at any time via the "Cancel" button — partial files are automatically cleaned up.

### Transcoding
- **Resolve-Ready Conversion:** Automatically runs downloaded footage through HandBrake using a custom `resolve_preset.json` — **CFR (constant framerate)**, H.264 encoded, 320kbps AAC stereo audio — bypassing the VFR desync and codec compatibility issues that plague phone/screen recordings in DaVinci Resolve.
- **GPU-Accelerated Encoding:** Automatically detects NVIDIA GPUs and uses the `nvenc_h264` hardware encoder for dramatically faster conversions. Falls back to `x264` (CPU) when no NVIDIA GPU is present.
- **Selectable Resolutions:** Choose between 1080p, 1440p (2K), and 2160p (4K) source qualities. If the selected limit is unavailable, the app automatically chooses the highest available quality and reports the fallback.
- **Output Collision Handling:** If a converted file already exists, a numeric suffix is automatically appended to avoid overwriting.

### Interface
- **Crimson Dark Theme:** A polished crimson-on-black UI with card-based layout, custom status dots, and themed widgets.
- **Paste Button:** Drop clipboard contents into the URL field with one click.
- **Custom Taskbar Icon:** Branded icon in the Windows taskbar and window title bar.
- **Progress Tracking:** A visual progress bar tracks both the download and conversion phases in real time.
- **Persistent Settings:** Your output folder and resolution preferences are saved to `settings.json` and restored on the next launch.

### Auto-Updater
- **yt-dlp Self-Update:** The app checks for yt-dlp nightly updates on startup (at most once per 24 hours), because nightly is the recommended channel during active YouTube breakage. If nightly fails verification, it keeps or installs a stable fallback. Downloads are validated and installed atomically so an interrupted update cannot replace a working copy.
- **Dynamic Loading:** In the `.exe` build, `yt-dlp` is loaded from an updateable zipapp, keeping the executable lightweight and allowing the downloader to update independently.
- **YouTube JavaScript Support:** Full YouTube extraction uses Deno or Node.js. The app detects `deno.exe`/`node.exe` beside the application or an executable on `PATH`; `YTDLP_JS_RUNTIME` can override the location. Some videos may additionally require browser cookies or PO-token support because of current YouTube restrictions.
- **Verified Startup:** The download button remains disabled until yt-dlp, yt-dlp-ejs, and the selected package/runtime are verified as usable.
- **Safety Lock:** The download button is disabled until the updater completes successfully, preventing crashes from premature attempts.

### Diagnostics
- **File-Based Logging:** All errors and important events are written to `error.log` via a lightweight logger — essential for diagnosing issues in windowed `.exe` builds where `print()` output is invisible.
- **JSON Download History:** Every successfully downloaded and converted video logs its identity, title, channel, URL, and completion time to `download_history.json`. Re-adding a recorded video shows an "Already downloaded" warning and skips it.

## 📁 Architecture

| File | Description |
|---|---|
| `gui_app.py` | The frontend GUI application (CustomTkinter). Run this to launch the interface. Manages the download queue, settings persistence, cancel/remove controls, and updater lifecycle. |
| `downloader.py` | The core backend logic. Handles yt-dlp interaction, HandBrake CLI dispatch, GPU detection, URL validation, playlist expansion, history logging, and cancellation. |
| `updater.py` | Nightly-first yt-dlp updater. Checks the nightly channel (at most once per 24h), validates the zipapp, and falls back to a verified stable package when needed. |
| `logger.py` | Lightweight file-based error logger (`error.log`). Critical for windowed `.exe` builds where `print()` output is swallowed. |
| `resolve_preset.json` | Custom HandBrake encoding preset ("Resolve Ready"). CFR, H.264, 320kbps AAC stereo, optimized for editing workflows. |
| `settings.json` | Persisted user settings (output folder, resolution). Created at runtime. |
| `download_history.json` | Structured log of completed downloads (identity, title, channel, URL, completion time) for the selected output folder. |
| `HandBrakeCLI.exe` & `ffmpeg.exe` | External command-line utilities used for demuxing, merging, and transcoding. |

## 🚀 Getting Started

### Using the Portable Application (Recommended)
If you generated or downloaded the standalone application folder:
1. Install Deno (recommended) and ensure `deno` is available on `PATH`, or place `deno.exe` beside `ResolveReadyDownloader.exe`.
2. Navigate to your `dist` folder.
3. Double-click `ResolveReadyDownloader.exe`.
4. On first launch, the app automatically checks yt-dlp nightly first and falls back to stable if needed — the download button is disabled until this completes.

If Deno is installed elsewhere, set `YTDLP_JS_RUNTIME` to the full path of `deno.exe` before launching the app.

### Running from Source
1. Ensure you have Python 3.10+ installed.
2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```
   This installs `yt-dlp` with its default YouTube EJS support. Install Deno separately and ensure it is available on `PATH`.
3. Verify you have `HandBrakeCLI.exe`, `ffmpeg.exe`, and `resolve_preset.json` in the project root. The app icon (`Nilvarcus-Resolve-Downloader-icon.ico`) is optional — the app runs fine without it.
4. Launch the application:
   ```bash
   python gui_app.py
   ```

## 🔄 Dependency Maintenance

The app deliberately separates dependencies that can be updated safely while it is running from dependencies that are compiled into the executable:

| Dependency | Update policy |
|---|---|
| `yt-dlp` + `yt-dlp-ejs` | Nightly is attempted first at startup, at most once per day. If nightly fails, source mode installs stable and portable mode keeps/installs a verified stable zipapp. |
| Deno or Node.js | External runtime. Keep Deno updated separately; the app detects it from `PATH` or beside the executable. |
| CustomTkinter | Bundled into the executable. Update it when creating a new release, not from inside a running app. |
| PyInstaller | Build-time dependency. Update it before rebuilding a release. |
| FFmpeg and HandBrakeCLI | External binaries bundled/copied into each release. Replace them when creating a new release. |

Before producing a new release, use a clean virtual environment and refresh the build dependencies:

```bash
python -m pip install -U pip
python -m pip install -U -r requirements.txt
```

Do not blindly run `pip install -U -r requirements.txt` from inside a running frozen app. It cannot update the already-bundled CustomTkinter code and can leave a source installation in a partially tested state. Rebuild and test a new executable instead.

## 🛠️ Building an Executable

Build a standalone `.exe` using PyInstaller. The command below bundles `HandBrakeCLI.exe`, `ffmpeg.exe`, and the preset, while **excluding** `yt-dlp` (which is downloaded dynamically at runtime by the auto-updater, keeping the `.exe` lightweight):

```bash
pyinstaller --clean --noconfirm --onedir --windowed \
  --add-data "HandBrakeCLI.exe;." \
  --add-data "resolve_preset.json;." \
  --add-data "ffmpeg.exe;." \
  --collect-all customtkinter \
  --exclude-module yt_dlp \
  --collect-submodules http \
  --collect-submodules email \
  --collect-submodules xml \
  --collect-submodules html \
  --collect-submodules concurrent \
  --collect-submodules urllib \
  --collect-submodules collections \
  --collect-submodules importlib \
  --collect-submodules asyncio \
  --hidden-import optparse \
  --hidden-import netrc \
  --hidden-import shlex \
  --hidden-import tokenize \
  --hidden-import quopri \
  --hidden-import fileinput \
  --hidden-import zipimport \
  --hidden-import bisect \
  --hidden-import heapq \
  --hidden-import array \
  --hidden-import getpass \
  --hidden-import shutil \
  --hidden-import mimetypes \
  --hidden-import pkgutil \
  --hidden-import sysconfig \
  --hidden-import contextvars \
  --hidden-import hmac \
  --hidden-import secrets \
  --hidden-import calendar \
  --hidden-import glob \
  --hidden-import inspect \
  --hidden-import locale \
  --hidden-import textwrap \
  --hidden-import uuid \
  --hidden-import msvcrt \
  --name "ResolveReadyDownloader" \
  "gui_app.py"
```

> **Why all the `--hidden-import` flags?** Because `yt-dlp` is excluded from the bundle (it's loaded dynamically at runtime via a zipapp), PyInstaller's static analysis never traces yt-dlp's imports. This means standard-library modules that yt-dlp depends on — most critically `getpass`, `http.cookies`, `http.cookiejar`, and `http.client` — can be left out of the build, causing a `ModuleNotFoundError` at runtime. The explicit imports in `downloader.py` and the flags below make the frozen build robust; the `--collect-submodules` flags grab every submodule of the relevant packages.

The active spec automatically bundles the Deno or Node executable found through `YTDLP_JS_RUNTIME` or `PATH`. If no runtime is found during the build, place a compatible `deno.exe` in the project root and add this optional flag to the build command:

```bash
--add-data "deno.exe;."
```

If you have the app icon (`Nilvarcus-Resolve-Downloader-icon.ico`) in the project root, add `--icon "Nilvarcus-Resolve-Downloader-icon.ico"` and `--add-data "Nilvarcus-Resolve-Downloader-icon.ico;."` to the command. The first sets the `.exe` icon; the second bundles it so the app window can display it at runtime.

The active reproducible build definition is `ResolveReadyDownloader.spec`; prefer rebuilding it with:

```bash
pyinstaller --clean --noconfirm ResolveReadyDownloader.spec
```

This produces a `dist/ResolveReadyDownloader/` folder with the executable and bundled assets. Always test the freshly generated executable rather than an older release folder.
