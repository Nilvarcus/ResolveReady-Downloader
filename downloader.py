# ==============================================================================
# IMPORTS
# ==============================================================================
# These standard-library imports are intentionally explicit because yt-dlp is
# loaded dynamically from a zipapp in frozen builds. PyInstaller cannot see all
# of yt-dlp's imports during static analysis otherwise.
import datetime
import getpass
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from urllib.parse import parse_qsl, parse_qs, quote, unquote, urlencode, urlsplit, urlunsplit

import yt_dlp

import logger

# ==============================================================================
# CONFIGURATION & PATHS
# ==============================================================================
HANDBRAKE_PRESET_NAME = "Resolve Ready"

IS_RUNNING_AS_EXE = getattr(sys, 'frozen', False)

if IS_RUNNING_AS_EXE:
    BUNDLE_DIR = sys._MEIPASS
else:
    BUNDLE_DIR = os.path.dirname(os.path.abspath(__file__))

HANDBRAKE_CLI_PATH = os.path.join(BUNDLE_DIR, "HandBrakeCLI.exe")
HANDBRAKE_PRESET_FILE = os.path.join(BUNDLE_DIR, "resolve_preset.json")
FFMPEG_PATH = os.path.join(BUNDLE_DIR, "ffmpeg.exe")
HISTORY_FILENAME = "download_history.json"
_HISTORY_LOCK = threading.RLock()


def _find_js_runtime():
    """Return a usable Deno or Node executable for yt-dlp, if available."""
    configured = os.environ.get("YTDLP_JS_RUNTIME")
    candidates = []
    if configured:
        configured = os.path.expandvars(os.path.expanduser(configured))
        if os.path.isdir(configured):
            candidates.extend([
                os.path.join(configured, "deno.exe"),
                os.path.join(configured, "node.exe"),
                os.path.join(configured, "deno"),
                os.path.join(configured, "node"),
            ])
        else:
            candidates.append(configured)

    candidates.extend([
        os.path.join(BUNDLE_DIR, "deno.exe"),
        os.path.join(BUNDLE_DIR, "node.exe"),
        os.path.join(BUNDLE_DIR, "deno"),
        os.path.join(BUNDLE_DIR, "node"),
    ])

    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate

    return shutil.which("deno") or shutil.which("node")


def _runtime_name(runtime_path):
    """Return yt-dlp's runtime key for an executable path."""
    basename = os.path.basename(runtime_path).lower()
    return "deno" if basename.startswith("deno") else "node"


def _runtime_version(runtime_path):
    """Return a short runtime version, or None if it cannot be started."""
    try:
        result = subprocess.run(
            [runtime_path, "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0,
        )
        if result.returncode == 0:
            return result.stdout.strip().splitlines()[0][:120]
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def _format_height(format_info):
    """Return a numeric format height, if one is available."""
    try:
        height = format_info.get('height')
        return int(height) if height else 0
    except (TypeError, ValueError):
        return 0


def _select_format(info, target_height, prefer_combined=False):
    """Select an exact format and effective height from yt-dlp metadata.

    The selector prefers the highest video format at or below the requested
    height. Fallback clients may request a combined format first because it
    avoids a second media URL that can independently receive HTTP 403.
    """
    formats = [item for item in (info or {}).get('formats', []) if item]
    videos = [
        item for item in formats
        if item.get('vcodec') not in (None, 'none')
        and item.get('acodec') in (None, 'none')
        and _format_height(item) > 0
    ]
    audios = [
        item for item in formats
        if item.get('acodec') not in (None, 'none')
        and item.get('vcodec') in (None, 'none')
        and item.get('format_id')
    ]

    def quality_key(item):
        return (
            _format_height(item),
            item.get('fps') or 0,
            item.get('tbr') or 0,
            item.get('format_id') or '',
        )

    combined = [
        item for item in formats
        if item.get('vcodec') not in (None, 'none')
        and item.get('acodec') not in (None, 'none')
        and item.get('format_id')
        and _format_height(item) > 0
    ]

    if prefer_combined and combined:
        under_limit = [item for item in combined if _format_height(item) <= target_height]
        selected = max(under_limit or combined, key=quality_key)
        return str(selected['format_id']), _format_height(selected)

    if videos and audios:
        under_limit = [item for item in videos if _format_height(item) <= target_height]
        selected_video = max(under_limit or videos, key=quality_key)
        selected_audio = max(audios, key=lambda item: (item.get('abr') or 0, item.get('tbr') or 0))
        return (
            f"{selected_video['format_id']}+{selected_audio['format_id']}",
            _format_height(selected_video),
        )

    if combined:
        under_limit = [item for item in combined if _format_height(item) <= target_height]
        selected = max(under_limit or combined, key=quality_key)
        return str(selected['format_id']), _format_height(selected)

    raise ValueError("No compatible video and audio formats were available")


def _is_403_error(error_text):
    lowered = error_text.lower()
    return "403" in lowered or "forbidden" in lowered


def _is_format_error(error_text):
    lowered = error_text.lower()
    return (
        "requested format is not available" in lowered
        or "no compatible video and audio formats" in lowered
        or "no video formats found" in lowered
        or "only images are available" in lowered
    )


def _is_youtube_url(url):
    """Return True for YouTube URLs where the JS runtime is required."""
    try:
        hostname = (urlsplit(url).hostname or "").lower().rstrip('.')
        return (
            hostname == "youtu.be"
            or hostname == "youtube.com"
            or hostname.endswith(".youtube.com")
        )
    except Exception:
        return False


def _youtube_video_id(url):
    """Extract a YouTube video ID from common URL forms."""
    try:
        parsed = urlsplit(url)
        hostname = (parsed.hostname or "").lower().rstrip('.')
        if hostname == "youtu.be":
            candidate = parsed.path.strip('/').split('/')[0]
            return unquote(candidate) if candidate else None
        if hostname == "youtube.com" or hostname.endswith('.youtube.com'):
            query = parse_qs(parsed.query)
            if query.get('v'):
                return query['v'][0]
            match = re.match(r'^/(?:shorts|embed|live)/([^/?#]+)', parsed.path)
            if match:
                return unquote(match.group(1))
    except Exception:
        pass
    return None


def canonicalize_url(url):
    """Return a stable identity string for a URL.

    YouTube URLs use their video ID so watch, short, embed, and youtu.be
    aliases compare as the same video. Other sites receive conservative URL
    normalization so meaningful query parameters are preserved.
    """
    if not isinstance(url, str) or not url.strip():
        return ""
    value = url.strip()
    youtube_id = _youtube_video_id(value)
    if youtube_id:
        return f"youtube:{youtube_id}"

    try:
        parsed = urlsplit(value)
        scheme = parsed.scheme.lower()
        hostname = (parsed.hostname or "").lower().rstrip('.')
        if not scheme or not hostname:
            return value

        try:
            port = parsed.port
        except ValueError:
            port = None
        netloc = hostname
        if parsed.username:
            credentials = quote(parsed.username, safe="")
            if parsed.password:
                credentials += ":" + quote(parsed.password, safe="")
            netloc = f"{credentials}@{netloc}"
        if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
            netloc = f"{netloc}:{port}"

        path = parsed.path or "/"
        if path != "/":
            path = path.rstrip('/')
        tracking_keys = {"fbclid", "gclid", "dclid"}
        query_items = [
            (key, val)
            for key, val in parse_qsl(parsed.query, keep_blank_values=True)
            if not key.lower().startswith("utm_") and key.lower() not in tracking_keys
        ]
        query = urlencode(sorted(query_items))
        return urlunsplit((scheme, netloc, path, query, ""))
    except Exception:
        return value


def get_download_identity(url, info=None):
    """Return the identity used for history and queue duplicate checks."""
    info = info or {}
    webpage_url = info.get('webpage_url') or url
    youtube_identity = canonicalize_url(webpage_url)
    if youtube_identity.startswith("youtube:"):
        return youtube_identity

    video_id = info.get('id')
    extractor = info.get('extractor_key') or info.get('extractor')
    if video_id and extractor:
        return f"{str(extractor).lower()}:{video_id}"
    return youtube_identity or canonicalize_url(url)


def _history_path(output_dir):
    return os.path.join(output_dir, HISTORY_FILENAME)


def _backup_invalid_history(history_path):
    """Preserve a malformed history file before it is repaired."""
    if not os.path.exists(history_path):
        return
    backup_path = f"{history_path}.invalid"
    if os.path.exists(backup_path):
        return
    counter = 1
    while os.path.exists(backup_path):
        backup_path = f"{history_path}.invalid_{counter}"
        counter += 1
    try:
        shutil.copy2(history_path, backup_path)
    except OSError:
        pass


def _load_history_unlocked(output_dir):
    history_path = _history_path(output_dir)
    if not os.path.exists(history_path):
        return []
    try:
        with open(history_path, 'r', encoding='utf-8') as history_file:
            data = json.load(history_file)
        if not isinstance(data, list):
            raise ValueError("download history must contain a JSON array")
        return [entry for entry in data if isinstance(entry, dict)]
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        _backup_invalid_history(history_path)
        logger.log(f"Could not read download history '{history_path}': {exc}")
        return []


def _history_record_identity(record):
    stored_identity = record.get('identity')
    if stored_identity:
        return str(stored_identity)
    return get_download_identity(record.get('url', ''), record)


def get_download_history_record(url, output_dir, info=None):
    """Return the matching completed history record, if one exists."""
    identity = get_download_identity(url, info)
    if not identity or not output_dir:
        return None
    with _HISTORY_LOCK:
        for record in _load_history_unlocked(output_dir):
            if _history_record_identity(record) == identity:
                return record
    return None


def is_already_downloaded(url, output_dir, info=None):
    """Return whether the selected output folder records this video as complete."""
    return get_download_history_record(url, output_dir, info) is not None


def _write_history_unlocked(output_dir, records):
    os.makedirs(output_dir, exist_ok=True)
    history_path = _history_path(output_dir)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode='w', encoding='utf-8', suffix='.tmp',
            prefix='.download-history-', dir=output_dir, delete=False,
        ) as temporary_file:
            temporary_path = temporary_file.name
            json.dump(records, temporary_file, indent=4)
            temporary_file.write("\n")
        os.replace(temporary_path, history_path)
    finally:
        if temporary_path:
            try:
                if os.path.exists(temporary_path):
                    os.remove(temporary_path)
            except OSError:
                pass


def record_completed_download(url, output_dir, info=None):
    """Record a successful download/conversion exactly once."""
    info = info or {}
    video_url = info.get('webpage_url') or url
    record = {
        "identity": get_download_identity(video_url, info),
        "title": info.get('title', 'Unknown Title'),
        "channel": info.get('uploader', 'Unknown Channel'),
        "url": video_url,
        "status": "completed",
        "completed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    with _HISTORY_LOCK:
        records = _load_history_unlocked(output_dir)
        if any(_history_record_identity(existing) == record["identity"] for existing in records):
            return False
        records.append(record)
        _write_history_unlocked(output_dir, records)
    return True


class _YtDlpLogger:
    """Routes yt-dlp diagnostics without exposing every retry as a new error."""

    def __init__(self, progress_callback=None, diagnostics=None, show_errors=False):
        self.progress_callback = progress_callback
        self.diagnostics = diagnostics if diagnostics is not None else []
        self.show_errors = show_errors

    def debug(self, message):
        # yt-dlp sends verbose diagnostics here; keep the GUI readable.
        pass

    def warning(self, message):
        self.diagnostics.append(f"WARNING: {message}")
        if self.progress_callback:
            self.progress_callback(f"WARNING: {message}")

    def error(self, message):
        self.diagnostics.append(f"ERROR: {message}")
        if self.show_errors and self.progress_callback:
            self.progress_callback(f"ERROR: {message}")

# ==============================================================================
# EXCEPTIONS
# ==============================================================================

class DownloadCancelled(Exception):
    """Raised inside yt-dlp progress hooks to abort an in-progress download."""
    pass

# ==============================================================================
# GPU DETECTION (cached)
# ==============================================================================

# Cache the GPU detection result so we don't spawn nvidia-smi on every conversion.
_NVIDIA_GPU_CACHE = None
_NVIDIA_GPU_LOCK = threading.Lock()


def has_nvidia_gpu():
    """
    Detects whether an NVIDIA GPU is present by checking for nvidia-smi.
    Used to decide whether nvenc_h264 (hardware) or x264 (software) encoding
    should be used for HandBrake. The result is cached after the first call.
    """
    global _NVIDIA_GPU_CACHE
    if _NVIDIA_GPU_CACHE is not None:
        return _NVIDIA_GPU_CACHE
    with _NVIDIA_GPU_LOCK:
        # Double-check in case another thread set it while we waited.
        if _NVIDIA_GPU_CACHE is not None:
            return _NVIDIA_GPU_CACHE
        try:
            result = subprocess.run(
                ["nvidia-smi", "-L"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            _NVIDIA_GPU_CACHE = result.returncode == 0 and result.stdout.strip() != b''
        except Exception:
            _NVIDIA_GPU_CACHE = False
        return _NVIDIA_GPU_CACHE


# ==============================================================================
# URL VALIDATION
# ==============================================================================

# Broad pattern: matches http(s):// URLs. yt-dlp supports 1000+ sites, so we
# only validate the basic structure rather than restricting to YouTube.
_URL_RE = re.compile(
    r'^https?://[^\s<>"{}|\\^`\[\]]+$',
    re.IGNORECASE
)

def is_valid_url(url):
    """Returns True if the string looks like a valid http/https URL."""
    if not url or not isinstance(url, str):
        return False
    return bool(_URL_RE.match(url.strip()))


def extract_playlist_entries(url):
    """
    If the URL is a playlist (yt-dlp supports many sites), extract the
    individual video URLs without downloading them.

    Returns a list of video URL strings. If the URL is a single video or
    extraction fails, returns [url] (the original).
    """
    if not is_valid_url(url):
        return [url]

    # yt-dlp flat-playlist mode is fast: it lists entries without downloading.
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
        'skip_download': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if info and info.get('_type') == 'playlist':
                entries = info.get('entries', [])
                urls = []
                for entry in entries:
                    if entry is None:
                        continue
                    entry_url = entry.get('url') or entry.get('webpage_url')
                    if not entry_url and entry.get('id'):
                        # Reconstruct from the extractor
                        extractor = entry.get('ie_key') or info.get('extractor')
                        if extractor:
                            try:
                                ex = ydl.get_info_extractor(extractor)
                                entry_url = ex._create_url(entry['id']) if hasattr(ex, '_create_url') else None
                            except Exception:
                                entry_url = None
                    if entry_url:
                        urls.append(entry_url)
                if urls:
                    return urls
    except Exception as e:
        logger.log_exception("extract_playlist_entries failed; treating as single video")
        # Fall through — return original so the normal download path can handle it

    return [url]


# ==============================================================================
# CORE FUNCTIONS
# ==============================================================================

def run_handbrake_conversion(source_filepath, output_dir, progress_callback=None,
                             progress_bar_callback=None, cancel_event=None,
                             use_nvenc=None):
    """
    Converts a single video file using HandBrake CLI.

    If use_nvenc is True, the nvenc_h264 encoder is used (requires NVIDIA GPU).
    If use_nvenc is False, x264 (software) is used.
    If use_nvenc is None, the encoder is auto-detected.

    Returns True on success, False on failure or cancellation.
    """
    if not os.path.exists(HANDBRAKE_CLI_PATH) or not os.path.exists(HANDBRAKE_PRESET_FILE):
        if progress_callback:
            progress_callback("ERROR: HandBrakeCLI.exe or resolve_preset.json could not be found.")
        return False

    # Auto-detect encoder if not explicitly specified
    if use_nvenc is None:
        use_nvenc = has_nvidia_gpu()

    encoder_name = "nvenc_h264" if use_nvenc else "x264"
    if progress_callback:
        progress_callback(f"Starting HandBrake conversion (encoder: {encoder_name})...")

    os.makedirs(output_dir, exist_ok=True)

    base_filename = os.path.splitext(os.path.basename(source_filepath))[0]

    # ---- Output collision handling ----
    # If the target file already exists, append a number to avoid overwriting.
    output_filepath = os.path.join(output_dir, f"{base_filename}_Handbraked.mp4")
    if os.path.exists(output_filepath):
        counter = 1
        while os.path.exists(os.path.join(output_dir, f"{base_filename}_Handbraked_{counter}.mp4")):
            counter += 1
        output_filepath = os.path.join(output_dir, f"{base_filename}_Handbraked_{counter}.mp4")
        if progress_callback:
            progress_callback(f"Output file exists — saving as {os.path.basename(output_filepath)}")

    command = [
        HANDBRAKE_CLI_PATH,
        "-i", source_filepath,
        "-o", output_filepath,
        "--preset-import-file", HANDBRAKE_PRESET_FILE,
        "-Z", HANDBRAKE_PRESET_NAME,
        "--encoder", encoder_name,
    ]

    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            encoding='utf-8',
            errors='replace',
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0,
        )
    except OSError as exc:
        message = f"ERROR: Could not start HandBrakeCLI: {exc}"
        if progress_callback:
            progress_callback(message)
        logger.log_exception("HandBrake process startup failed")
        return False

    cancelled = False
    output_error = None
    try:
        for line in iter(process.stdout.readline, ''):
            if cancel_event and cancel_event.is_set():
                cancelled = True
                break

            if "Encoding: task" in line:
                if progress_callback:
                    progress_callback(line.strip())
                if progress_bar_callback:
                    match = re.search(r'(\d+(?:\.\d+)?)\s*%', line)
                    if match:
                        try:
                            progress_bar_callback(float(match.group(1)) / 100.0)
                        except ValueError:
                            pass
    except Exception as exc:
        output_error = exc
    finally:
        try:
            process.stdout.close()
        except Exception:
            pass

    if cancelled or output_error:
        try:
            process.terminate()
            process.wait(timeout=5)
        except Exception:
            try:
                process.kill()
                process.wait(timeout=5)
            except Exception:
                pass
        if output_error:
            if progress_callback:
                progress_callback(f"ERROR: Could not read HandBrake output: {output_error}")
            logger.log_exception("HandBrake output processing failed")
        else:
            if progress_callback:
                progress_callback("Conversion cancelled.")
        try:
            if os.path.exists(output_filepath):
                os.remove(output_filepath)
        except OSError:
            pass
        return False

    return_code = process.wait()

    if return_code == 0 and os.path.exists(output_filepath):
        if progress_callback:
            progress_callback("Successfully encoded! File saved safely.")
        try:
            os.remove(source_filepath)
        except OSError as exc:
            if progress_callback:
                progress_callback(f"WARNING: Failed to delete original file '{source_filepath}'. {exc}")
            logger.log(f"Failed to delete source file after conversion: {exc}")
        return True

    if progress_callback:
        progress_callback(f"Encoding failed. HandBrake exited with error code {return_code}.")
    logger.log(f"HandBrake encoding failed (code {return_code}) for {source_filepath}")
    try:
        if os.path.exists(output_filepath):
            os.remove(output_filepath)
    except OSError:
        pass

    # A visible NVIDIA GPU does not guarantee that this HandBrake build or
    # driver can initialize NVENC. Retry once with the CPU encoder instead of
    # failing the entire queue item.
    if use_nvenc:
        if progress_callback:
            progress_callback("WARNING: NVENC failed; retrying with the x264 CPU encoder...")
        return run_handbrake_conversion(
            source_filepath,
            output_dir,
            progress_callback,
            progress_bar_callback,
            cancel_event,
            use_nvenc=False,
        )
    return False


def download_youtube_video(url, output_dir, resolution="1080p",
                           progress_callback=None, progress_bar_callback=None,
                           cancel_event=None):
    """
    Downloads a video using yt-dlp and hands it to Handbrake.

    A cancel_event (threading.Event) can be passed to allow cancellation.
    When set, the download/conversion is aborted as soon as possible.

    Returns True on full success (download + conversion), False on failure or
    cancellation.
    """
    # ---- URL validation ----
    if not is_valid_url(url):
        if progress_callback:
            progress_callback("ERROR: Please enter a valid URL (must start with http:// or https://).")
        return False

    def ytdlp_progress_hook(d):
        # Check for cancellation during download
        if cancel_event and cancel_event.is_set():
            # Raise to break out of extract_info
            raise DownloadCancelled("Download cancelled by user.")

        if d['status'] == 'downloading':
            percent = d.get('_percent_str', 'N/A').strip()
            speed = d.get('_speed_str', 'N/A').strip()
            eta = d.get('_eta_str', 'N/A').strip()
            msg = f"Downloading... {percent} at {speed} | ETA: {eta}"
            if progress_callback:
                progress_callback(msg)
            if progress_bar_callback:
                match = re.search(r'(\d+(?:\.\d+)?)\s*%', percent)
                if match:
                    try:
                        progress_bar_callback(float(match.group(1)) / 100.0)
                    except ValueError:
                        pass
        elif d['status'] == 'finished':
            if progress_callback:
                progress_callback("Download complete. Preparing for Conversion...")
            if progress_bar_callback:
                progress_bar_callback(1.0)

    resolution_limits = {
        "1080p": 1080,
        "1440p (2K)": 1440,
        "2160p (4K)": 2160,
    }
    target_height = resolution_limits.get(resolution, 1080)
    os.makedirs(output_dir, exist_ok=True)

    if not os.path.isfile(FFMPEG_PATH):
        message = f"ERROR: FFmpeg was not found at {FFMPEG_PATH}."
        if progress_callback:
            progress_callback(message)
        logger.log(message)
        return False

    js_runtime = _find_js_runtime()
    runtime_version = _runtime_version(js_runtime) if js_runtime else None
    if _is_youtube_url(url) and not js_runtime and progress_callback:
        progress_callback(
            "WARNING: Deno or Node.js was not found. Install Deno 2.3+ or set YTDLP_JS_RUNTIME."
        )
    elif _is_youtube_url(url) and js_runtime and not runtime_version and progress_callback:
        progress_callback(
            f"WARNING: JavaScript runtime could not be started: {js_runtime}"
        )

    base_options = {
        'outtmpl': os.path.join(output_dir, '%(title)s.%(ext)s'),
        'merge_output_format': 'mp4',
        'ffmpeg_location': FFMPEG_PATH,
        'progress_hooks': [ytdlp_progress_hook],
        'quiet': True,
        'no_color': True,
        'no_warnings': False,
    }
    if js_runtime:
        base_options['js_runtimes'] = {
            _runtime_name(js_runtime): {'path': js_runtime}
        }

    info = None
    download_info = None
    selected_height = None
    diagnostics = []
    try:
        # Inspect formats first. This avoids repeatedly guessing selectors and
        # lets the app report a real fallback height.
        client_attempts = [("default", None, False)]
        if _is_youtube_url(url):
            # These clients are tried only after the default media URL fails.
            # Fallback clients prefer a combined format to avoid a second URL
            # receiving an independent 403 response.
            client_attempts.extend([
                ("web_embedded", {
                    'youtube': {'player_client': ['web_embedded']}
                }, True),
                ("mweb", {
                    'youtube': {'player_client': ['mweb']}
                }, True),
                ("web_safari", {
                    'youtube': {'player_client': ['web_safari']}
                }, True),
            ])

        last_error = None
        for attempt_number, (client_name, extractor_args, prefer_combined) in enumerate(client_attempts):
            attempt_diagnostics = []
            metadata_options = dict(base_options)
            metadata_options.update({
                'skip_download': True,
                'logger': _YtDlpLogger(
                    progress_callback,
                    attempt_diagnostics,
                    show_errors=False,
                ),
            })
            if extractor_args:
                metadata_options['extractor_args'] = extractor_args

            try:
                if progress_callback:
                    if attempt_number == 0:
                        progress_callback("Inspecting available formats...")
                    else:
                        progress_callback(
                            f"Retrying YouTube with the {client_name} media client..."
                        )

                with yt_dlp.YoutubeDL(metadata_options) as metadata_ydl:
                    info = metadata_ydl.extract_info(url, download=False)
                format_selector, selected_height = _select_format(
                    info,
                    target_height,
                    prefer_combined=prefer_combined,
                )

                download_options = dict(base_options)
                download_options.update({
                    'format': format_selector,
                    'logger': _YtDlpLogger(
                        progress_callback,
                        attempt_diagnostics,
                        show_errors=False,
                    ),
                })
                if extractor_args:
                    download_options['extractor_args'] = extractor_args

                if progress_callback:
                    progress_callback(f"Downloading selected format {format_selector}...")
                with yt_dlp.YoutubeDL(download_options) as download_ydl:
                    download_info = download_ydl.extract_info(url, download=True)
                diagnostics.extend(attempt_diagnostics)
                info = download_info or info
                break
            except DownloadCancelled:
                raise
            except Exception as exc:
                last_error = exc
                diagnostics.extend(attempt_diagnostics)
                error_text = str(exc)
                is_last_attempt = attempt_number == len(client_attempts) - 1
                if is_last_attempt or not (_is_403_error(error_text) or _is_format_error(error_text)):
                    raise
                _cleanup_partial_files(output_dir, info)
                if progress_callback:
                    if _is_403_error(error_text):
                        progress_callback(
                            "YouTube rejected the selected media URL (HTTP 403); trying another client..."
                        )
                    else:
                        progress_callback(
                            "The first client did not expose a compatible format; trying another client..."
                        )
        else:
            if last_error:
                raise last_error

        if selected_height and selected_height != target_height and progress_callback:
            if selected_height < target_height:
                progress_callback(
                    f"Requested {target_height}p unavailable — using {selected_height}p."
                )
            else:
                progress_callback(
                    f"No format up to {target_height}p available — using {selected_height}p."
                )

    except DownloadCancelled:
        if progress_callback:
            progress_callback("Download cancelled.")
        # Clean up partial download files
        _cleanup_partial_files(output_dir, info)
        return False
    except Exception as e:
        error_text = str(e)
        if _is_youtube_url(url) and _is_403_error(error_text):
            message = (
                "ERROR: YouTube rejected the media request (HTTP 403). "
                "Deno/EJS may be missing, or this video requires browser cookies "
                "or a PO-token provider. Update yt-dlp and check the diagnostics."
            )
        elif _is_format_error(error_text):
            if any("only images are available" in item.lower() for item in diagnostics):
                message = (
                    "ERROR: YouTube exposed thumbnails/audio but no usable video format. "
                    "The video requires another client, browser cookies, or PO-token support."
                )
            else:
                message = (
                    "ERROR: YouTube exposed no compatible video/audio format for the "
                    "available clients. Try browser cookies or a PO-token provider."
                )
        elif "FFmpeg was not found" in error_text:
            message = error_text
        else:
            message = f"ERROR: Download failed: {e}"
        if progress_callback:
            progress_callback(message)
        if diagnostics:
            logger.log("yt-dlp attempt diagnostics for %s:\n%s" % (
                url,
                "\n".join(diagnostics[-20:]),
            ))
        logger.log_exception(f"download_youtube_video error for {url}")
        _cleanup_partial_files(output_dir, info)
        return False

    # ---- Check for cancellation before starting conversion ----
    if cancel_event and cancel_event.is_set():
        if progress_callback:
            progress_callback("Cancelled before conversion started.")
        return False

    # Run HandBrake after yt-dlp has fully closed its context. Prefer yt-dlp's
    # post-processed filepath; requested_downloads can contain only one side of
    # a separate video/audio pair and must not be treated as the final file.
    filepath = None
    if info:
        candidates = [
            info.get('filepath'),
            info.get('_filename'),
            info.get('filename'),
        ]
        requested_downloads = info.get('requested_downloads') or []
        if len(requested_downloads) == 1:
            candidates.append(requested_downloads[0].get('filepath'))
        for candidate in candidates:
            if candidate and os.path.isfile(candidate) and not candidate.endswith('.part'):
                filepath = candidate
                break

    if filepath and os.path.exists(filepath):
        success = run_handbrake_conversion(
            filepath, output_dir, progress_callback,
            progress_bar_callback, cancel_event
        )
        if not success:
            return False

        try:
            record_completed_download(url, output_dir, info)
        except Exception:
            logger.log_exception(f"Failed to record completed download for {url}")
    else:
        message = (
            "ERROR: yt-dlp completed, but did not report the final merged file. "
            "Check that FFmpeg is available and retry."
        )
        if progress_callback:
            progress_callback(message)
        logger.log(message)
        return False

    if progress_callback:
        progress_callback("All Tasks Completed Successfully!")
    if progress_bar_callback:
        progress_bar_callback(1.0)
    return True


# ==============================================================================
# HELPERS
# ==============================================================================

def _cleanup_partial_files(output_dir, info):
    """
    Best-effort removal of .part / .ytdl / .mp4.part files left behind by a
    cancelled or failed download so they don't block future runs.
    """
    if not output_dir or not os.path.isdir(output_dir):
        return
    try:
        for fname in os.listdir(output_dir):
            if fname.endswith(('.part', '.ytdl', '.mp4.part', '.webm.part', '.m4a.part')):
                try:
                    os.remove(os.path.join(output_dir, fname))
                except OSError:
                    pass
    except Exception:
        pass
