# Project: Resolve-Ready Downloader

## Project Overview
A Python desktop GUI application that downloads videos from the internet (YouTube and 1000+ other sites via yt-dlp) and transcodes them into a format optimized for DaVinci Resolve editing. It leverages `yt-dlp` for robust video downloading and `HandBrakeCLI` for efficient video transcoding. A custom HandBrake preset (`resolve_preset.json`) ensures output files are "Resolve Ready" — constant framerate (CFR), H.264 encoded, with normalized audio — bypassing the VFR desync and codec compatibility issues that plague phone/screen recordings in Resolve.

The app is distributable as a standalone executable using PyInstaller, bundling `HandBrakeCLI.exe`, `ffmpeg.exe`, and the custom preset file. `yt-dlp` is loaded dynamically from a zipapp at runtime, allowing it to be auto-updated independently of the main executable.

## Technologies Used
- **Python 3.10+**: The core programming language.
- **`yt-dlp`**: Video downloader supporting YouTube and 1000+ sites. Loaded from an updateable zipapp in the `.exe` build.
- **`HandBrakeCLI`**: Command-line video transcoder. Uses `nvenc_h264` (NVIDIA GPU) when available, falls back to `x264` (CPU) otherwise.
- **`customtkinter`**: Modern dark-mode GUI framework (Tkinter wrapper).
- **`subprocess` module**: Spawns HandBrakeCLI processes.
- **`PyInstaller`**: Packages the app into a standalone Windows executable.

## Architecture

### Core Files
- **`gui_app.py`**: The frontend GUI application (CustomTkinter). Run this to launch the interface. Manages the download queue, settings persistence, cancel/remove controls, and updater lifecycle.
- **`downloader.py`**: The core backend logic. Handles yt-dlp interaction, HandBrake CLI dispatch, GPU detection, URL validation, playlist expansion, history logging, and cancellation.
- **`updater.py`**: Auto-updater for yt-dlp. Checks GitHub for the latest release (at most once per 24h), downloads the zipapp, and installs a custom import finder so `yt_dlp` resolves from the updateable zip.
- **`logger.py`**: Lightweight file-based error logger (`error.log`). Critical for windowed `.exe` builds where `print()` output is swallowed.
- **`resolve_preset.json`**: Custom HandBrake encoding preset ("Resolve Ready"). Uses CFR (constant framerate), H.264, 320kbps AAC stereo audio, optimized for editing workflows.
- **`settings.json`**: Persisted user settings (output folder, resolution). Created at runtime.
- **`download_history.json`**: Structured log of all downloads (title, channel, URL). Deduplicated by URL.

### Bundled Binaries
- **`HandBrakeCLI.exe`**: Video transcoder binary.
- **`ffmpeg.exe`**: Used by yt-dlp for merging/demuxing.

## Building and Running

### Running from Source
1. Ensure Python 3.10+ is installed.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Verify `HandBrakeCLI.exe`, `ffmpeg.exe`, and `resolve_preset.json` are in the project root.
4. Launch the application:
   ```bash
   python gui_app.py
   ```

### Building the Executable (PyInstaller)
The project uses `ResolveReadyDownloader.spec` (the current, active spec):
```bash
pyinstaller ResolveReadyDownloader.spec
```
This produces a `dist/ResolveReadyDownloader/` folder with the executable and bundled assets. Note: `yt_dlp` is **excluded** from the bundle (`excludes=['yt_dlp']`) and is instead downloaded as a zipapp by `updater.py` on first run, keeping the `.exe` lightweight and updateable.

> **Note:** `YouTubeDownloader.spec` is a legacy spec that bundles `yt_dlp` directly. It is retained for reference but `ResolveReadyDownloader.spec` is the recommended build target.

### Running the Executable
```bash
./dist/ResolveReadyDownloader/ResolveReadyDownloader.exe
```

## Development Conventions

### Path Handling
All modules use `getattr(sys, 'frozen', False)` to dynamically resolve paths:
- **Frozen (`.exe`)**: `sys._MEIPASS` for bundled resources, `os.path.dirname(sys.executable)` for user-writable files (settings, history, logs, yt-dlp zip).
- **Source (`.py`)**: `os.path.dirname(os.path.abspath(__file__))` for everything.

### Output Structure
- Downloaded videos are stored temporarily in the user-selected output directory.
- Converted videos are saved to the same directory with a `_Handbraked.mp4` suffix.
- The original downloaded file is deleted after successful conversion.
- If a `_Handbraked.mp4` file already exists, a numeric suffix is appended to avoid overwrites.

### Error Handling & Logging
- All exceptions and important errors are written to `error.log` via `logger.py`.
- This is essential because the built `.exe` runs in windowed mode (`console=False`), where `print()` output is invisible.
- The download function returns `True`/`False` to indicate success/failure, which the GUI uses to show correct queue status (green=done, red=error, gray=cancelled).

### Video Format & Encoding
- Downloads the best available video up to the selected resolution (1080p, 1440p/2K, or 2160p/4K) merged with best audio.
- Converts to MP4 using the "Resolve Ready" HandBrake preset: **CFR (constant framerate)** to fix VFR desyncs, H.264 encoded via `nvenc_h264` (NVIDIA) or `x264` (CPU fallback), 320kbps AAC stereo audio.

### Queue System
- Multiple URLs can be added to the queue and are processed sequentially.
- Supports batch paste (multiple URLs separated by newlines/commas/whitespace).
- Supports playlist URLs (auto-expanded into individual video downloads).
- Each queue item can be removed before processing starts.
- Completed/error items can be bulk-cleared via the "Clear Completed" button.
- In-progress downloads can be cancelled via the "Cancel" button.

### Auto-Updater
- On startup, `updater.py` checks for yt-dlp updates (at most once per 24 hours).
- For source runs: uses `pip install -U yt-dlp`.
- For `.exe` runs: downloads the latest zipapp from GitHub releases.
- The UI is disabled (download button greyed out) until the updater completes, preventing premature download attempts.
