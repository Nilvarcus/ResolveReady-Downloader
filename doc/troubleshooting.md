# Troubleshooting

## First: confirm which build is running

The application title should include the current version, for example:

```text
Resolve-Ready Downloader v1.4
```

Use the freshly built executable:

```text
dist/ResolveReadyDownloader/ResolveReadyDownloader.exe
```

Do not diagnose a current source change by launching an older release folder or a root-level executable. Different builds can use different updater paths and bundled Python modules.

The startup log records the executable path, frozen/source mode, and bundle path.

## Old `ModuleNotFoundError: getpass`

A traceback containing:

```text
ModuleNotFoundError: No module named 'getpass'
```

usually belongs to an older frozen build whose PyInstaller analysis did not include all standard-library modules needed by the dynamically imported yt-dlp zipapp.

Fix:

1. Rebuild with `ResolveReadyDownloader.spec`.
2. Use `pyinstaller --clean --noconfirm ResolveReadyDownloader.spec`.
3. Launch the executable inside the fresh `dist/ResolveReadyDownloader/` folder.
4. Check that the error path points into that folder, not an old `dist/yt-dlp.zip` location.

Old entries can remain in `error.log` because the log is append-only.

## Nightly update behavior

At startup, the updater now tries the nightly channel first. Expected messages include:

```text
Checking yt-dlp nightly for the latest YouTube fixes...
yt-dlp nightly and YouTube support are ready.
```

If nightly cannot be downloaded or imported:

```text
WARNING: Nightly package failed verification; trying stable fallback...
Stable yt-dlp fallback is ready.
```

The update marker is `.ytdlp_last_check_v3`. Delete or rename the marker only when you intentionally need another update check; the application normally manages it.

## Deno or Node is not found

For source mode, check the runtime directly:

```bash
where deno
where node
```

Then set the explicit path if needed:

```text
YTDLP_JS_RUNTIME=C:\path\to\deno.exe
```

For a portable build, the active spec bundles a runtime found at build time. If the build machine did not have one available, rebuild after setting `YTDLP_JS_RUNTIME` or add a runtime to the build inputs.

Deno solves JavaScript challenges. It does not automatically solve browser-cookie or PO-token restrictions.

## HTTP 403 from YouTube

A 403 can mean several different things:

- The stable yt-dlp build is behind an upstream YouTube change.
- The media URL was rejected after format extraction.
- The selected YouTube client requires a PO token.
- The video requires browser cookies or account context.
- The network or IP address was challenged.

The app tries yt-dlp nightly first and then uses client fallbacks. If 403 continues after a verified nightly update, check the full diagnostics in `error.log`. The next likely requirement is browser cookies or a PO-token provider, not another arbitrary format string.

Official references:

- [yt-dlp PO Token Guide](https://github.com/yt-dlp/yt-dlp/wiki/Po-Token-Guide)
- [yt-dlp EJS Guide](https://github.com/yt-dlp/yt-dlp/wiki/EJS)
- [yt-dlp nightly builds](https://github.com/yt-dlp/yt-dlp-nightly-builds/releases)

## “Only images are available”

This means yt-dlp received thumbnails/storyboards, and possibly audio, but no usable video format for that client. It is not a HandBrake error.

The current downloader tries `web_embedded`, `mweb`, and `web_safari` fallback clients after relevant failures. If all clients expose no video, the video likely requires a browser session, cookies, a PO token, or is restricted.

## FFmpeg errors

Verify that `ffmpeg.exe` exists:

- Beside the source files in source mode.
- Inside the fresh executable bundle in frozen mode.

The downloader refuses to start a media download when its configured FFmpeg path is missing because separate video/audio formats cannot be merged reliably without it.

The required file is the FFmpeg executable, not a Python package named `ffmpeg`.

## HandBrake errors

Verify:

- `HandBrakeCLI.exe` exists.
- `resolve_preset.json` exists.
- The preset contains a `Resolve Ready` preset.
- The selected output folder is writable.

If NVENC fails, the application automatically retries with x264. A slow CPU conversion after an NVENC warning is expected fallback behavior.

## “Already downloaded” appears

The application checks the selected output directory's `download_history.json` before adding a queue item. This is expected when that file contains the same canonical video identity.

- Selecting another output directory uses that folder's history.
- YouTube URL aliases are intentionally treated as the same video.
- A failed or cancelled conversion should not create a new completed record.
- Existing old history entries without an identity field are still recognized by URL.

If the history file is malformed, the application preserves an `.invalid` copy, treats it as empty, and logs the problem.

## Queue item fails but the GUI remains responsive

Open the Error Log button in the queue header. Failed rows also expose a warning button with the last captured actionable message.

The GUI processes the queue in a worker thread and sends widget updates through a main-thread event queue. A failed item should transition to `Error` while later pending items continue.

## Cancellation leaves files behind

The downloader cleans common `.part`, `.ytdl`, `.mp4.part`, `.webm.part`, and `.m4a.part` files. A file may remain if another process has it open or if the application is terminated abruptly.

Close any media player holding the file and remove only the known partial file after confirming no download process is still running.

## Settings or history problems

Runtime state is stored beside the script or executable:

- `settings.json`
- `download_history.json`
- `error.log`
- `.ytdlp_last_check_v3`

If the application appears to ignore settings, check that you are opening the same source/executable folder that contains the state files. Frozen and source modes intentionally use different state locations.
