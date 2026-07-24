# Resolve-Ready Downloader

A sleek, intuitive desktop application designed for video editors. It allows you to effortlessly download videos from YouTube and 1000+ other sites in up to 4K resolution and automatically transcodes them into a high-performance, editing-friendly format optimized for DaVinci Resolve.

Built with Python, `yt-dlp`, and HandBrakeCLI, wrapped in a beautiful modern GUI using **CustomTkinter**.

## ✨ Features

### Download & Queue
- **Download Queue System:** Paste multiple links at once (separated by commas, spaces, or newlines) and they're processed sequentially. Each item appears in a scrollable queue with color-coded status indicators (Pending, Processing, Done, Error, Cancelled).
- **Playlist Support:** Playlist URLs are automatically expanded into individual video downloads — each gets its own queue entry.
- **Duplicate Detection:** Adding a URL that's already in the queue is flagged with a warning.
- **Per-Item Control:** Remove any queue item with the ✕ button, or bulk-clear all completed/error/cancelled items with the "Clear" button.
- **Cancellation:** Abort in-progress downloads at any time via the "Cancel" button — partial files are automatically cleaned up.

### Transcoding
- **Resolve-Ready Conversion:** Automatically runs downloaded footage through HandBrake using a custom `resolve_preset.json` — **CFR (constant framerate)**, H.264 encoded, 320kbps AAC stereo audio — bypassing the VFR desync and codec compatibility issues that plague phone/screen recordings in DaVinci Resolve.
- **GPU-Accelerated Encoding:** Automatically detects NVIDIA GPUs and uses the `nvenc_h264` hardware encoder for dramatically faster conversions. Falls back to `x264` (CPU) when no NVIDIA GPU is present.
- **Selectable Resolutions:** Choose between 1080p, 1440p (2K), and 2160p (4K) source qualities.
- **Output Collision Handling:** If a converted file already exists, a numeric suffix is automatically appended to avoid overwriting.

### Interface
- **Crimson Dark Theme:** A polished crimson-on-black UI with card-based layout, custom status dots, and themed widgets.
- **Paste Button:** Drop clipboard contents into the URL field with one click.
- **Custom Taskbar Icon:** Branded icon in the Windows taskbar and window title bar.
- **Progress Tracking:** A visual progress bar tracks both the download and conversion phases in real time.
- **Persistent Settings:** Your output folder and resolution preferences are saved to `settings.json` and restored on the next launch.

### Auto-Updater
- **yt-dlp Self-Update:** The app automatically checks for `yt-dlp` updates on startup (at most once per 24 hours), pulling the latest version from GitHub to stay ahead of site changes.
- **Dynamic Loading:** In the `.exe` build, `yt-dlp` is loaded from an updateable zipapp, keeping the executable lightweight and allowing the downloader to update independently.
- **Safety Lock:** The download button is disabled until the updater completes, preventing crashes from premature attempts.

### Diagnostics
- **File-Based Logging:** All errors and important events are written to `error.log` via a lightweight logger — essential for diagnosing issues in windowed `.exe` builds where `print()` output is invisible.
- **JSON Download History:** Every successful download logs its Title, Channel, and URL to `download_history.json` (deduplicated by URL).

## 📁 Architecture

| File | Description |
|---|---|
| `gui_app.py` | The frontend GUI application (CustomTkinter). Run this to launch the interface. Manages the download queue, settings persistence, cancel/remove controls, and updater lifecycle. |
| `downloader.py` | The core backend logic. Handles yt-dlp interaction, HandBrake CLI dispatch, GPU detection, URL validation, playlist expansion, history logging, and cancellation. |
| `updater.py` | Auto-updater for yt-dlp. Checks GitHub for the latest release (at most once per 24h), downloads the zipapp, and installs a custom import finder so `yt_dlp` resolves from the updateable zip. |
| `logger.py` | Lightweight file-based error logger (`error.log`). Critical for windowed `.exe` builds where `print()` output is swallowed. |
| `resolve_preset.json` | Custom HandBrake encoding preset ("Resolve Ready"). CFR, H.264, 320kbps AAC stereo, optimized for editing workflows. |
| `settings.json` | Persisted user settings (output folder, resolution). Created at runtime. |
| `download_history.json` | Structured log of all downloads (title, channel, URL). Deduplicated by URL. |
| `HandBrakeCLI.exe` & `ffmpeg.exe` | External command-line utilities used for demuxing, merging, and transcoding. |

## 🚀 Getting Started

### Using the Portable Application (Recommended)
If you generated or downloaded the standalone application folder, all dependencies are fully packaged inside!
1. Navigate to your `dist` folder.
2. Double-click `ResolveReadyDownloader.exe`.
3. On first launch, the app automatically downloads the latest `yt-dlp` core — the download button is disabled until this completes.

### Running from Source
1. Ensure you have Python 3.10+ installed.
2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Verify you have `HandBrakeCLI.exe`, `ffmpeg.exe`, and `resolve_preset.json` in the project root. The app icon (`Nilvarcus-Resolve-Downloader-icon.ico`) is optional — the app runs fine without it.
4. Launch the application:
   ```bash
   python gui_app.py
   ```

## 🛠️ Building an Executable

Build a standalone `.exe` using PyInstaller. The command below bundles `HandBrakeCLI.exe`, `ffmpeg.exe`, and the preset, while **excluding** `yt-dlp` (which is downloaded dynamically at runtime by the auto-updater, keeping the `.exe` lightweight):

```bash
pyinstaller --noconfirm --onedir --windowed \
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
  --hidden-import imghdr \
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

> **Why all the `--hidden-import` flags?** Because `yt-dlp` is excluded from the bundle (it's loaded dynamically at runtime via a zipapp), PyInstaller's static analysis never traces yt-dlp's imports. This means dozens of standard-library modules that yt-dlp depends on — most critically `http.cookies`, `http.cookiejar`, and `http.client` — are silently left out of the build, causing a `ModuleNotFoundError` at runtime. The `--collect-submodules` flags grab every submodule of those packages automatically (far more robust than listing each one by hand), and the `--hidden-import` flags cover top-level stdlib modules that yt-dlp uses but the app itself never imports directly.

If you have the app icon (`Nilvarcus-Resolve-Downloader-icon.ico`) in the project root, add `--icon "Nilvarcus-Resolve-Downloader-icon.ico"` and `--add-data "Nilvarcus-Resolve-Downloader-icon.ico;."` to the command. The first sets the `.exe` icon; the second bundles it so the app window can display it at runtime.

This produces a `dist/ResolveReadyDownloader/` folder with the executable and bundled assets.
