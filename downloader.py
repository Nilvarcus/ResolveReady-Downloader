# ==============================================================================
# IMPORTS
# ==============================================================================
import yt_dlp
import sys
import os
import subprocess
import re
import json
import threading

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

    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        encoding='utf-8',
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
    )

    cancelled = False
    for line in iter(process.stdout.readline, ''):
        # Check for cancellation during encoding
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

    if cancelled:
        try:
            process.terminate()
            process.wait(timeout=5)
        except Exception:
            try:
                process.kill()
            except Exception:
                pass
        if progress_callback:
            progress_callback("Conversion cancelled.")
        # Clean up partial output
        try:
            if os.path.exists(output_filepath):
                os.remove(output_filepath)
        except OSError:
            pass
        return False

    process.stdout.close()
    return_code = process.wait()

    if return_code == 0:
        if progress_callback:
            progress_callback("Successfully encoded! File saved safely.")
        try:
            os.remove(source_filepath)
        except OSError as e:
            if progress_callback:
                progress_callback(f"WARNING: Failed to delete original file '{source_filepath}'. {e}")
            logger.log(f"Failed to delete source file after conversion: {e}")
        return True
    else:
        if progress_callback:
            progress_callback(f"Encoding failed. HandBrake exited with error code {return_code}.")
        logger.log(f"HandBrake encoding failed (code {return_code}) for {source_filepath}")
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

    # Determine resolution format string
    format_str = 'bestvideo[height<=1080]+bestaudio/best'
    if resolution == "1440p (2K)":
        format_str = 'bestvideo[height<=1440]+bestaudio/best'
    elif resolution == "2160p (4K)":
        format_str = 'bestvideo[height<=2160]+bestaudio/best'

    yt_dlp_options = {
        'format': format_str,
        'outtmpl': os.path.join(output_dir, '%(title)s.%(ext)s'),
        'merge_output_format': 'mp4',

        'progress_hooks': [ytdlp_progress_hook],
        'quiet': True,
        'no_color': True,
        'no_warnings': True,
    }

    info = None
    try:
        with yt_dlp.YoutubeDL(yt_dlp_options) as ydl:
            if progress_callback:
                progress_callback("Initializing download connection...")
            info = ydl.extract_info(url, download=True)

            # Write metadata to history file (with dedup)
            try:
                title = info.get('title', 'Unknown Title')
                channel = info.get('uploader', 'Unknown Channel')
                video_url = info.get('webpage_url', url)
                history_file = os.path.join(output_dir, "download_history.json")

                history_data = []
                if os.path.exists(history_file):
                    try:
                        with open(history_file, 'r', encoding='utf-8') as f:
                            history_data = json.load(f)
                    except json.JSONDecodeError:
                        pass

                # Dedup: skip if this URL already exists in history
                if not any(entry.get('url') == video_url for entry in history_data):
                    history_data.append({
                        "title": title,
                        "channel": channel,
                        "url": video_url
                    })
                    with open(history_file, 'w', encoding='utf-8') as f:
                        json.dump(history_data, f, indent=4)
            except Exception as e:
                logger.log(f"Failed to log history: {e}")

    except DownloadCancelled:
        if progress_callback:
            progress_callback("Download cancelled.")
        # Clean up partial download files
        _cleanup_partial_files(output_dir, info)
        return False
    except Exception as e:
        if progress_callback:
            progress_callback(f"AN UNEXPECTED ERROR OCCURRED: {e}")
        logger.log_exception(f"download_youtube_video error for {url}")
        _cleanup_partial_files(output_dir, info)
        return False

    # ---- Check for cancellation before starting conversion ----
    if cancel_event and cancel_event.is_set():
        if progress_callback:
            progress_callback("Cancelled before conversion started.")
        return False

    # Now run HandBrake OUTSIDE of yt-dlp's context
    # This ensures yt-dlp has properly closed all its sockets and files
    filepath = None
    if info:
        if 'requested_downloads' in info and len(info['requested_downloads']) > 0:
            filepath = info['requested_downloads'][0].get('filepath')

        if not filepath:
            try:
                filename = ydl.prepare_filename(info)
                base, _ = os.path.splitext(filename)
                filepath = base + '.mp4'
            except Exception:
                pass

    if filepath and os.path.exists(filepath):
        if filepath.lower().endswith('.mp4'):
            success = run_handbrake_conversion(
                filepath, output_dir, progress_callback,
                progress_bar_callback, cancel_event
            )
            if not success:
                return False
        else:
            if progress_callback:
                progress_callback(f"ERROR: Downloaded file is not MP4: {filepath}")
            return False
    else:
        if progress_callback:
            progress_callback("ERROR: Could not locate downloaded file for conversion.")
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
