# Configuration and Runtime State

## Environment variables

### `YTDLP_JS_RUNTIME`

Optional explicit path to Deno or Node.js.

Examples:

```text
YTDLP_JS_RUNTIME=C:\Tools\deno\deno.exe
```

A directory can also be supplied; the downloader searches it for `deno.exe`, `node.exe`, `deno`, or `node`.

The runtime is used by yt-dlp's EJS challenge solver. It is not the same as FFmpeg or HandBrake.

## User settings

`settings.json` contains:

```json
{
    "output_dir": "C:\\Videos",
    "resolution": "1080p"
}
```

The GUI writes this file when the output folder or resolution changes.

## Download history

`download_history.json` is a JSON array. Successfully downloaded and converted videos add:

```json
{
    "identity": "youtube:VIDEO_ID",
    "title": "Video title",
    "channel": "Uploader name",
    "url": "https://example.com/video",
    "status": "completed",
    "completed_at": "2026-08-18T15:30:00+00:00"
}
```

The file belongs to the selected output folder. Entries are deduplicated by canonical identity. Legacy records without `identity` are still checked using their stored URL.

## Already-downloaded checks

When a URL is added, the application checks the selected output folder's history before creating a queue item. YouTube watch, short, embed, and `youtu.be` aliases are matched by video ID. A match produces an `Already downloaded` warning and skips the URL.

A video downloaded into another output folder is not considered a duplicate because each output folder owns its own history file.

## Error log

`error.log` is a timestamped text log. It contains:

- Startup paths and build mode.
- Updater failures.
- yt-dlp retry diagnostics.
- Download tracebacks.
- HandBrake failures.
- File cleanup warnings.

The GUI can open, refresh, and clear the log. Clearing it removes diagnostic history, so save a copy first when investigating a recurring problem.

## Update marker

`.ytdlp_last_check_v3` stores a Unix timestamp for the last successful dependency verification. It prevents the updater from hitting GitHub and pip on every launch.

The marker is deliberately versioned. A new marker filename forces a one-time check after changing updater logic or switching update channels.

## Frozen application paths

Frozen mode uses two path categories:

- Bundled resources: `sys._MEIPASS` / the PyInstaller internal bundle.
- Writable runtime state: the directory containing `ResolveReadyDownloader.exe`.

Expected bundled resources include:

```text
HandBrakeCLI.exe
ffmpeg.exe
resolve_preset.json
deno.exe or node.exe
```

The actual runtime filename may preserve the case used by the build system.

Expected writable files beside the executable include:

```text
yt-dlp.zip
settings.json
download_history.json
error.log
.ytdlp_last_check_v3
```
