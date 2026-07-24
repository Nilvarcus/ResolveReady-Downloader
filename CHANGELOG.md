# Changelog

## [1.3] - The Queue & Quality Update

A major overhaul spanning backend reliability, GPU-accelerated transcoding, a complete UI redesign, and a self-updating yt-dlp engine. This release consolidates dozens of improvements into one comprehensive update.

### 🎨 Complete UI Redesign
- **Crimson Dark Theme:** The entire interface has been rebuilt with a sleek crimson-on-black palette, card-based layout, and custom-styled widgets (status dots, rounded cards, themed buttons).
- **Branded Header:** Added a crimson accent strip, stylized title, and tagline for a polished, professional look.
- **Custom Taskbar Icon:** The app now displays its own branded icon in the Windows taskbar (via AppUserModelID) and window title bar.
- **Paste Button:** A dedicated "Paste" button next to the URL field lets you drop clipboard contents with one click.
- **Truncated Path Display:** Long output folder paths are now intelligently truncated with an ellipsis so they never overflow the layout.

### 📥 Download Queue System
- **Sequential Processing:** Paste multiple links and they are processed one-by-one automatically. Supports batch paste (URLs separated by newlines, commas, or spaces).
- **Queue GUI Display:** A scrollable queue area shows every item with a color-coded status dot and label (Pending, Processing, Done, Error, Cancelled).
- **Per-Item Removal:** Click the ✕ on any queue row to remove it. Pending, completed, error, and cancelled items can all be removed individually.
- **Bulk Clear:** The "Clear" button removes all done, error, and cancelled items in one action.
- **Duplicate Detection:** Adding a URL that's already in the queue is detected and flagged with a warning — no more accidental double-downloads.
- **Playlist Expansion:** Playlist URLs are automatically expanded into individual video downloads, each appearing as its own queue item.
- **Streamlined Workflow:** The URL entry field clears automatically after adding to the queue for rapid bulk pasting.

### 🛡️ Core Stability & Reliability
- **Fixed ".parts" File Bug:** Resolved a critical issue where subsequent downloads in a queue would fail or stall, leaving only `.parts` files. The download-to-conversion pipeline was refactored so `yt-dlp` cleanly terminates its network connections before HandBrake begins processing.
- **Decoupled Execution:** Moved HandBrake execution outside of `yt-dlp`'s internal post-processor hooks, preventing thread-blocking and network timeouts.
- **Proper Return Values:** `download_youtube_video()` now returns `True`/`False` so the GUI can accurately reflect success, failure, or cancellation for each queue item.
- **Output Collision Handling:** If a `_Handbraked.mp4` file already exists, a numeric suffix is automatically appended to avoid overwriting previous conversions.
- **Partial File Cleanup:** Cancelled or failed downloads now clean up leftover `.part` / `.ytdl` files so they don't block future runs.
- **History Deduplication:** The `download_history.json` log now skips duplicate URLs instead of creating repeated entries.

### 🚀 GPU-Accelerated Transcoding
- **NVIDIA GPU Auto-Detection:** HandBrake now automatically detects NVIDIA GPUs via `nvidia-smi` and uses the `nvenc_h264` hardware encoder for dramatically faster conversions. Falls back to `x264` (CPU) when no NVIDIA GPU is present.
- **Cached Detection:** GPU detection runs once and caches the result (thread-safe), so it doesn't re-scan hardware on every conversion.
- **CFR Framerate Fix:** Updated the HandBrake preset to use **CFR (constant framerate)** with auto-detection, fixing the VFR (variable framerate) desync issues that plague phone and screen recordings inside DaVinci Resolve.

### 🔄 Intelligent Auto-Updater
- **yt-dlp Self-Update:** The application now automatically checks for `yt-dlp` updates on startup (at most once per 24 hours), pulling the latest version directly from GitHub releases to stay ahead of YouTube's frequent changes.
- **Dynamic Dependency Loading:** For the `.exe` build, `yt-dlp` is loaded dynamically from a local zipapp via a custom import finder, allowing the core downloader to be updated independently of the main application executable.
- **Reduced Executable Size:** By excluding `yt-dlp` from the PyInstaller bundle, the base `.exe` is significantly smaller and more lightweight.
- **Smart Safety Lock:** The "Add to Queue" button is disabled while the updater verifies and updates core dependencies, preventing crashes from premature download attempts.
- **Real-Time Status Feedback:** The status bar provides live feedback during the startup update check (e.g., "Checking for updates...", "Downloading core components...").

### 🔧 Cancellation & Control
- **Download Cancellation:** In-progress downloads can be aborted via the "Cancel" button, which signals `yt-dlp` and HandBrake to stop as soon as possible.
- **Cancelled Item Removal:** Fixed a bug where cancelled items were stuck in the queue — they can now be removed individually (✕) or bulk-cleared alongside done/error items.

### 📝 Logging & Diagnostics
- **File-Based Error Logger:** Added `logger.py`, a lightweight logger that writes timestamped errors and tracebacks to `error.log`. This is essential for diagnosing issues in windowed `.exe` builds where `print()` output is invisible.
- **Comprehensive Error Capture:** All critical paths (downloads, conversions, history writes, updater failures) now log exceptions with full context.

### ⚙️ Settings & Persistence
- **Settings Save/Load:** User preferences (output folder and resolution) are now persisted to `settings.json` and restored on the next launch.
- **Resolution Memory:** The selected quality (1080p / 2K / 4K) is remembered between sessions.

### 📦 Build & Packaging
- **New PyInstaller Spec:** Added `ResolveReadyDownloader.spec` as the active build target, bundling `HandBrakeCLI.exe`, `ffmpeg.exe`, the preset, and the app icon while excluding `yt_dlp` (loaded dynamically at runtime).
- **Requirements File:** Added `requirements.txt` for clean dependency installation from source.
- **Legacy Spec Retained:** `YouTubeDownloader.spec` is kept for reference but the new spec is the recommended build target.

---

## [1.2] - Progress & History Overhaul

### 📊 Progress Tracking & UI Cleanup
- **Visual Progress Bar:** Added a dedicated progress bar at the bottom of the window, providing real-time feedback for both the downloading (yt-dlp) and conversion (HandBrake) phases.
- **Improved Layout:** Cleaned up the GUI layout to ensure all elements fit perfectly, anchoring the progress bar securely at the bottom.
- **Removed Subtitle Downloads:** Stripped out the subtitle download toggle and logic to eliminate persistent "HTTP 429: Too Many Requests" errors and streamline the core download process.

### 📝 History & Logging
- **JSON History Log:** Replaced the legacy `.txt` history log with a structured `download_history.json` file. Each download now automatically logs the Video Title, Channel Name, and URL for easier reading and programmatic use.
- **Enhanced Progress Parsing:** Implemented regex-based output parsing for HandBrake CLI to provide much more accurate percentage updates in the GUI.

## [1.1] - Resolve-Ready GUI Update

### 🚀 Major Features & UI Redesign
- **Brand New GUI:** Completely rebuilt the user interface from the ground up using CustomTkinter! The app now features a gorgeous, fully-responsive Dark Mode window, leaving the clunky terminal behind.
- **Asynchronous Processing:** Long downloads and intensive HandBrake CLI conversions now run silently in a background thread. Your app window will stay buttery smooth and won't lock up or freeze anymore.
- **Selectable Resolutions:** Added a new dropdown allowing you to pull source videos in **1080p, 1440p (2K), or 2160p (4K)** seamlessly.
- **Custom Destinations:** Say goodbye to being forced into a default `Handbraked` subfolder! You can now use a clean picker menu to dump both your raw subtitles and Resolve-Ready `.mp4` files into any designated folder on your PC.

### ✨ Additions & Fixes
- **YouTube Automatic Transcripts:** Integrated a brand-new toggle exclusively for downloading English subtitles (`.srt` or `.vtt`) alongside your footage. Perfect for rapid video editing and captioning workflows.
- **Fixed "HTTP 403 Forbidden" Crashes:** Dynamically updated the `yt-dlp` core engine to permanently bypass YouTube's recent heavy API rate-limiting blocks.
- **Improved Codebase:** Refactored the messy `src-1.0.py` script into a streamlined, import-ready `downloader.py` module.
- **Full Documentation & Packaging:** Added a comprehensive `README.md` file outlining setup details, and deployed a fully autonomous, portable `.exe` folder.
