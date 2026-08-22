# Architecture

## High-level components

```text
+-----------------------+
| gui_app.py            |
| CustomTkinter UI      |
| queue and settings    |
+-----------+-----------+
            |
            | calls after updater readiness
            v
+-----------------------+       +----------------------+
| downloader.py         |------>| updater.py           |
| yt-dlp + FFmpeg       |       | nightly/stable setup |
| HandBrake + history  |       +----------------------+
+-----------+-----------+
            |
            v
+-----------------------+       +----------------------+
| yt-dlp / yt-dlp-ejs  |       | HandBrakeCLI.exe     |
| Deno or Node.js       |       | resolve_preset.json  |
+-----------------------+       +----------------------+
```

`logger.py` is used by all major components and writes diagnostics to `error.log`.

## Application startup

1. `gui_app.py` imports the lightweight updater and logger modules.
2. The main window and controls are created.
3. The download button starts disabled.
4. A background updater thread checks yt-dlp.
5. The updater tries nightly first and verifies that the package is usable.
6. If nightly fails, source mode tries stable pip dependencies or frozen mode verifies/installs a stable zipapp.
7. The updater completion callback receives a success flag and optional error message.
8. Only after success does the GUI import `downloader.py` and enable the download button.

This order prevents the GUI from importing an absent or broken yt-dlp package.

## Queue lifecycle

Each queue item contains an ID, URL, resolution, output directory, status, UI row, and last error.

The normal state sequence is:

```text
pending -> processing -> done
                    -> error
                    -> cancelled
```

Important rules:

- Only one queue item is processed at a time.
- The active item cannot be removed until it is cancelled.
- Completed, failed, and cancelled items can be removed individually or cleared together.
- A warning button exposes the captured error for failed items.

## Threading model

Tkinter widgets must be changed on the Tk main thread. Long-running work must not block that thread.

The application uses:

- A worker thread for updater work.
- A worker thread for playlist expansion.
- A worker thread for sequential queue processing.
- A `queue.Queue` event bridge for worker-to-UI callbacks.
- A queue lock protecting shared queue state.

Workers report status and progress by placing callbacks into the UI event queue. A periodic Tk callback drains that queue and updates widgets safely.

## Downloader boundaries

`downloader.py` deliberately separates yt-dlp and HandBrake:

1. yt-dlp extracts metadata and downloads/merges the media.
2. The yt-dlp context closes.
3. The final merged filepath is located.
4. HandBrakeCLI converts that file.

Keeping HandBrake outside yt-dlp's context avoids mixing network cleanup, media post-processing, and a second subprocess in one yt-dlp operation.

## Filesystem conventions

In source mode, resources and runtime state resolve relative to the project file.

In frozen mode:

- Bundled read-only resources resolve through `sys._MEIPASS`.
- User-writable state resolves beside `sys.executable`.
- The active yt-dlp zipapp is beside the executable.

This distinction matters when diagnosing a package that appears to update in one folder while the application is running from another.

## Error flow

1. yt-dlp warnings and errors are collected by `_YtDlpLogger`.
2. Recoverable attempt diagnostics are kept out of the main error display.
3. The downloader classifies 403, unavailable-format, runtime, FFmpeg, and general failures.
4. The final actionable message is sent to the GUI callback.
5. The full technical context is written to `error.log`.
6. The queue item stores the last meaningful error and changes to `error`.

The log is append-only unless the user clears it from the Error Log window, so older failures may remain visible.
