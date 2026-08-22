# Resolve-Ready Downloader Documentation

This folder explains how Resolve-Ready Downloader works, what technologies it uses, and how to develop, build, and troubleshoot it.

## Documents

- [Project Overview](overview.md) — purpose, features, runtime modes, and repository map.
- [Architecture](architecture.md) — application components, lifecycle, threading, state, and data flow.
- [Download Pipeline](download-pipeline.md) — URL handling, playlist expansion, yt-dlp format selection, merging, and HandBrake conversion.
- [Technology](technology.md) — the role of Python, CustomTkinter, yt-dlp, EJS, Deno, FFmpeg, HandBrake, NVIDIA NVENC, and PyInstaller.
- [Development and Build](development-and-build.md) — source setup, tests, executable builds, runtime packaging, and release checks.
- [Troubleshooting](troubleshooting.md) — common startup, YouTube, packaging, conversion, queue, and filesystem failures.
- [Configuration and Runtime State](configuration.md) — environment variables, generated files, paths, and updater markers.

## Quick mental model

```text
User enters URL
      |
      v
GUI validates and queues URL
      |
      v
Playlist expansion (if needed)
      |
      v
yt-dlp updater verifies nightly or stable fallback
      |
      v
yt-dlp inspects formats and downloads/merges media with FFmpeg
      |
      v
HandBrake converts the merged file to the Resolve Ready preset
      |
      v
Converted MP4 is saved and the original intermediate file is removed
```

The application is a local Windows desktop program. It has no server, database, account system, or telemetry backend. Runtime state is stored in files next to the script or executable.
