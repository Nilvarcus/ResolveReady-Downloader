# ==============================================================================
# IMPORTS
# ==============================================================================
import yt_dlp
import sys
import os
import subprocess

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
# CORE FUNCTIONS
# ==============================================================================

def run_handbrake_conversion(source_filepath, output_dir, progress_callback=None):
    """
    Converts a single video file using HandBrake CLI.
    """
    if not os.path.exists(HANDBRAKE_CLI_PATH) or not os.path.exists(HANDBRAKE_PRESET_FILE):
        if progress_callback:
            progress_callback("\nERROR: HandBrakeCLI.exe or resolve_preset.json could not be found.")
        return

    if progress_callback:
        progress_callback(f"Starting HandBrake conversion...")

    os.makedirs(output_dir, exist_ok=True)

    base_filename = os.path.splitext(os.path.basename(source_filepath))[0]
    output_filepath = os.path.join(output_dir, f"{base_filename}_Handbraked.mp4")

    command = [
        HANDBRAKE_CLI_PATH,
        "-i", source_filepath,
        "-o", output_filepath,
        "--preset-import-file", HANDBRAKE_PRESET_FILE,
        "-Z", HANDBRAKE_PRESET_NAME
    ]

    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        encoding='utf-8',
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
    )

    for line in iter(process.stdout.readline, ''):
        if "Encoding: task" in line:
            if progress_callback:
                progress_callback(line.strip())

    process.stdout.close()
    return_code = process.wait()

    if return_code == 0:
        if progress_callback:
            progress_callback(f"Successfully encoded! File saved safely.")
        try:
            os.remove(source_filepath)
        except OSError as e:
            if progress_callback:
                progress_callback(f"ERROR: Failed to delete original file '{source_filepath}'. {e}")
    else:
        if progress_callback:
            progress_callback(f"Encoding failed. HandBrake exited with error code {return_code}.")


def download_youtube_video(url, output_dir, resolution="1080p", download_transcripts=True, progress_callback=None):
    """
    Downloads a YouTube video using yt-dlp and hands it to Handbrake.
    """
    
    def handbrake_postprocessor_hook(d):
        if d['status'] == 'finished':
            filepath = d.get('info_dict', {}).get('filepath')
            if filepath and os.path.exists(filepath):
                if filepath.lower().endswith('.mp4'):
                    run_handbrake_conversion(filepath, output_dir, progress_callback)

    def ytdlp_progress_hook(d):
        if d['status'] == 'downloading':
            percent = d.get('_percent_str', 'N/A').strip()
            speed = d.get('_speed_str', 'N/A').strip()
            eta = d.get('_eta_str', 'N/A').strip()
            msg = f"Downloading... {percent} at {speed} | ETA: {eta}"
            if progress_callback:
                progress_callback(msg)
        elif d['status'] == 'finished':
            if progress_callback:
                progress_callback("Download complete. Preparing for Conversion...")

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
        
        # Subtitles
        'writesubtitles': download_transcripts,
        'writeautomaticsub': download_transcripts,
        'subtitleslangs': ['en'] if download_transcripts else [],
        'subtitlesformat': 'srt/vtt/best' if download_transcripts else '',
        
        'postprocessor_hooks': [handbrake_postprocessor_hook],
        'progress_hooks': [ytdlp_progress_hook],
        'quiet': True,
        'no_warnings': True,
    }

    try:
        with yt_dlp.YoutubeDL(yt_dlp_options) as ydl:
            if progress_callback:
                progress_callback(f"Initializing download connection...")
            ydl.download([url])
        if progress_callback:
            progress_callback("All Tasks Completed Successfully!")
    except Exception as e:
        if progress_callback:
            progress_callback(f"AN UNEXPECTED ERROR OCCURRED: {e}")