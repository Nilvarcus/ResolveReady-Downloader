# Technology

## Python

Python is the application language. It provides:

- GUI integration through Tkinter and CustomTkinter.
- Threading and synchronization for background work.
- Subprocess management for FFmpeg, HandBrakeCLI, pip, and JavaScript runtimes.
- JSON persistence for settings and download history.
- Zipapp inspection and dynamic imports for frozen-mode yt-dlp updates.

Python 3.10+ is the project baseline. The release build is produced with the Python installation used to run PyInstaller.

## CustomTkinter and Tkinter

CustomTkinter is a themed widget layer over Tkinter. It supplies the dark interface, cards, buttons, option menus, progress bar, text boxes, and scrollable queue.

Tkinter is single-threaded from the application's perspective. The project therefore performs downloads and conversions in worker threads, while a main-thread event queue applies UI changes.

## yt-dlp

yt-dlp is the extraction and download engine. It provides:

- Site-specific extractors.
- Playlist metadata.
- Format metadata.
- Media URL resolution.
- Download progress hooks.
- Video/audio merging through FFmpeg.
- Browser and client-specific extraction behavior.

The application uses the yt-dlp Python API in source mode and dynamically imports an updateable zipapp in frozen mode.

The project currently attempts yt-dlp nightly first because upstream recommends nightly while active site breakage is being fixed. A stable fallback remains available.

Official references:

- [yt-dlp repository](https://github.com/yt-dlp/yt-dlp)
- [yt-dlp nightly builds](https://github.com/yt-dlp/yt-dlp-nightly-builds/releases)

## yt-dlp EJS and JavaScript runtimes

Modern YouTube extraction needs JavaScript challenge solving. yt-dlp uses the companion `yt-dlp-ejs` package together with a JavaScript runtime.

Deno is preferred. Node.js is also supported by the application. Runtime lookup order is:

1. `YTDLP_JS_RUNTIME`.
2. A runtime beside the application bundle.
3. A runtime found on `PATH`.

The active PyInstaller spec bundles a runtime found through `YTDLP_JS_RUNTIME` or `PATH` during the build.

EJS support does not guarantee that every YouTube media URL is authorized. PO-token and browser-session restrictions are separate from JavaScript challenge solving.

Reference: [yt-dlp EJS setup guide](https://github.com/yt-dlp/yt-dlp/wiki/EJS)

## FFmpeg

FFmpeg is the media utility used by yt-dlp to merge separate video and audio streams and perform related media operations. It is not the Python package named `ffmpeg`; the project needs the executable binary.

The downloader passes the configured bundled path through yt-dlp's `ffmpeg_location` option and verifies that the file exists before a download begins.

## HandBrakeCLI

HandBrakeCLI performs the final Resolve-oriented transcode. The project supplies a custom JSON preset named `Resolve Ready`.

The preset is intended to produce:

- Constant frame rate output.
- H.264 video.
- AAC stereo audio at the configured bitrate.
- MP4 output suitable for an editing workflow.

HandBrake is intentionally invoked after yt-dlp finishes and closes its network resources.

## NVENC and x264

The app checks for `nvidia-smi` once and caches the result. If an NVIDIA GPU is detected, HandBrake is first called with `nvenc_h264`.

GPU presence alone does not prove that NVENC will work. Driver, hardware, and HandBrake support can still differ. A non-zero NVENC conversion result triggers one x264 retry.

## PyInstaller

PyInstaller creates the Windows onedir application. The active `ResolveReadyDownloader.spec`:

- Includes HandBrakeCLI, FFmpeg, the preset, and the icon.
- Includes a detected Deno or Node executable when available.
- Collects CustomTkinter assets.
- Adds hidden standard-library imports needed by dynamically loaded yt-dlp code.
- Excludes `yt_dlp` so it can update independently at runtime.

Frozen applications resolve bundled resources through `sys._MEIPASS` and writable state beside `sys.executable`.

## Local persistence

The project intentionally uses simple files instead of a database:

- JSON for settings and download history.
- Plain text for error logs and updater timestamps.
- A zipapp for the mutable frozen-mode yt-dlp package.

This keeps the portable build easy to copy and inspect.
