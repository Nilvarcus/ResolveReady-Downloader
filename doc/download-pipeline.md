# Download Pipeline

## 1. Input and URL validation

The GUI accepts one or more URLs. `_split_urls()` separates whitespace, commas, and newlines. `is_valid_url()` performs a broad HTTP/HTTPS structure check because yt-dlp supports many sites beyond YouTube.

The application does not try to maintain a hardcoded list of supported websites. yt-dlp is responsible for extractor support.

## 2. Playlist expansion

Before an item enters the queue, the app calls `extract_playlist_entries()` with yt-dlp's flat-playlist options:

- `extract_flat=True`
- `skip_download=True`
- `quiet=True`

Playlist entries are converted into individual URLs. If expansion fails, the original URL is retained as a single queue item and a warning is logged.

After expansion, each individual video URL is checked against the selected output folder's `download_history.json`. A completed match is reported as `Already downloaded` and is not added to the queue.

## 3. Resolution target

The GUI exposes three limits:

| GUI value | Height limit |
|---|---:|
| `1080p` | 1080 |
| `1440p (2K)` | 1440 |
| `2160p (4K)` | 2160 |

The downloader first prefers the highest video format at or below the limit. If no format is below the limit, it chooses the highest available format and reports the actual height.

## 4. Format inspection

The downloader first calls yt-dlp with `download=False` to inspect the available formats. It separates:

- Video-only formats: video codec present, audio codec absent.
- Audio-only formats: audio codec present, video codec absent.
- Combined formats: both video and audio codecs present.

For the default client, the downloader prefers a separate video/audio pair so the highest usable quality can be selected. For fallback clients, it prefers a combined format when available because one media URL is less likely to fail independently with HTTP 403.

The selected format becomes an exact selector such as:

```text
137+251
```

or a combined format such as:

```text
18
```

## 5. YouTube client fallback

YouTube extraction is dynamic and can change independently of this project. For YouTube URLs the current client sequence is:

1. yt-dlp's default client configuration.
2. `web_embedded`.
3. `mweb`.
4. `web_safari`.

Fallback clients are tried only for relevant HTTP 403 or format-availability failures. Non-recoverable errors are not blindly retried.

The fallback is not a guarantee that every video is downloadable. YouTube may require a browser session, cookies, or a PO token. JavaScript challenge solving and PO-token authorization are separate concerns.

## 6. yt-dlp download and FFmpeg merge

The downloader passes yt-dlp:

- An output template based on the video title.
- The exact selected format.
- `merge_output_format='mp4'`.
- The bundled or configured FFmpeg path.
- A progress hook.
- A diagnostic logger.
- A cancellation event.

When separate video and audio streams are selected, yt-dlp uses FFmpeg to merge them. The downloader then prefers yt-dlp's reported final post-processed filepath rather than assuming the first requested stream is the completed file.

## 7. HandBrake conversion

After yt-dlp's context has closed, the merged file is passed to HandBrakeCLI with:

- The `Resolve Ready` preset from `resolve_preset.json`.
- `nvenc_h264` when NVIDIA GPU detection succeeds.
- `x264` otherwise.

If NVENC returns a failure code, the application retries once with x264. This handles machines where an NVIDIA GPU exists but the driver or HandBrake build cannot initialize NVENC.

The output name follows this pattern:

```text
OriginalTitle_Handbraked.mp4
```

If that name already exists, a numbered suffix is used.

## 8. Cleanup and history

On successful conversion:

- The converted MP4 remains in the selected output directory.
- The downloaded intermediate source is deleted.
- A canonical identity, title, uploader/channel, webpage URL, completion status, and UTC completion time are added to `download_history.json` unless the identity is already present.

History is written only after HandBrake succeeds. A yt-dlp failure, cancellation, or failed conversion does not mark the video as completed.

YouTube aliases such as `youtu.be`, `watch?v=`, Shorts, and embed URLs are compared by video ID. Other websites use conservative URL normalization.

On cancellation or failure:

- `.part`, `.ytdl`, and related partial files are removed where possible.
- The original source is not deleted after an unsuccessful conversion.
- Technical details are written to `error.log`.
