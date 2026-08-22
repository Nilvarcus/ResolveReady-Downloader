# Changelog

## [1.4] - Dependency Stability, Adaptive Quality & Download Protection

Released: 2026-08-18

This release focuses on keeping the downloader reliable as YouTube and its surrounding tooling continue to change. It adds safer dependency updates, stronger frozen-build packaging, better YouTube error recovery, and adaptive quality selection.

### 🔄 Dependency & Runtime Maintenance
- **Automatic yt-dlp/EJS Maintenance:** Source installations now update and repair both `yt-dlp` and `yt-dlp-ejs` through the `yt-dlp[default]` dependency group; the updater prefers nightly while YouTube breakage is active.
- **Nightly Recovery with Stable Fallback:** Source and portable builds try yt-dlp nightly first, verify it before use, and fall back to a verified stable package when nightly installation or import fails.
- **Verified Startup Gate:** The GUI keeps downloads disabled until nightly or stable yt-dlp dependencies are confirmed usable.
- **Validated Portable Updates:** The executable validates each downloaded yt-dlp zipapp before installing it.
- **Atomic yt-dlp Replacement:** Updates are downloaded to a temporary file and moved into place only after validation, preserving the previous working version if an update is interrupted or corrupt.
- **Forced Repair Check:** The updater uses a versioned check marker so updater repairs are not silently skipped because of an old daily-check marker.
- **JavaScript Runtime Detection:** Deno or Node.js is detected beside the application, through `PATH`, or through the `YTDLP_JS_RUNTIME` environment variable.
- **Dependency Policy Documentation:** Documented which dependencies update at runtime and which must be refreshed during release builds.

### ▶️ YouTube Reliability
- **HTTP 403 Recovery:** YouTube downloads that receive a 403 from the default media client retry through `web_embedded`, `mweb`, and `web_safari` fallback clients, preferring combined formats when appropriate.
- **Visible yt-dlp Warnings:** yt-dlp warnings and errors are routed into the application status bar instead of being hidden.
- **Actionable Failure Messages:** YouTube 403 failures now explain the likely causes, including outdated yt-dlp, missing Deno, browser-cookie requirements, and PO-token restrictions.
- **Safer Partial Updates:** Invalid or incomplete yt-dlp packages are rejected instead of being loaded by the application.

### 🎞️ Adaptive Quality Selection
- **Requested Quality Preference:** The downloader first selects the highest available format at or below the chosen target resolution.
- **Highest-Available Fallback:** If no format exists under the selected target, the downloader falls back to the highest available quality rather than failing.
- **Format Selector Retry:** If YouTube rejects the resolution-aware selector, the downloader retries with yt-dlp's standard `bestvideo+bestaudio/best` selector before reporting failure.
- **Fallback Status Reporting:** The status bar reports the actual selected height, for example: `Requested 1080p unavailable — using 720p.`
- **Audio Preservation:** All fallback paths continue to prefer separate video and audio streams and merge them through FFmpeg before HandBrake conversion.

### 📦 Packaging & Build Reliability
- **Fixed Missing `getpass`:** Explicitly retained dynamically imported standard-library modules required by the updateable yt-dlp zipapp in PyInstaller builds.
- **Clean Rebuild Process:** Updated the documented PyInstaller command to use a clean analysis and removed the obsolete Python 3.14 `imghdr` hidden import.
- **Fresh Portable Build:** Rebuilt `dist/ResolveReadyDownloader/ResolveReadyDownloader.exe` with the dependency and quality fixes.
- **FFmpeg Bundle Configuration:** The packaged downloader now resolves `ffmpeg.exe` from the application bundle for merging and conversion.

### 🧰 Diagnostics & Error Handling
- **Per-Item Error Details:** Failed queue items expose their captured error message through a dedicated warning button.
- **Error Log Viewer:** Added an in-app error-log window with refresh and clear controls.
- **Improved Error Capture:** Download callbacks retain the last meaningful failure message for queue-level troubleshooting.
- **Completed-Download Protection:** Videos already recorded in the selected output folder's `download_history.json` are reported as already downloaded and skipped before queue admission.
- **Canonical Video Identity:** YouTube URL aliases are matched by video ID instead of exact URL text, and canonical identities prevent duplicates inside the active queue.
- **Post-Conversion History:** History entries are written only after HandBrake conversion succeeds, preventing failed or cancelled items from being marked complete.
- **Atomic History Repair:** Malformed history files are preserved as `.invalid` backups and history rewrites use atomic replacement.

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
