# ==============================================================================
# IMPORTS
# ==============================================================================
import yt_dlp
import sys
import os
import subprocess
import re

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

def run_handbrake_conversion(source_filepath, output_dir, progress_callback=None, progress_bar_callback=None):
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
            if progress_bar_callback:
                match = re.search(r'(\d+(?:\.\d+)?)\s*%', line)
                if match:
                    try:
                        progress_bar_callback(float(match.group(1)) / 100.0)
                    except ValueError:
                        pass

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


def download_youtube_video(url, output_dir, resolution="1080p", progress_callback=None, progress_bar_callback=None):
    """
    Downloads a YouTube video using yt-dlp and hands it to Handbrake.
    """
    
    def handbrake_postprocessor_hook(d):
        if d['status'] == 'finished':
            filepath = d.get('info_dict', {}).get('filepath')
            if filepath and os.path.exists(filepath):
                if filepath.lower().endswith('.mp4'):
                    run_handbrake_conversion(filepath, output_dir, progress_callback, progress_bar_callback)

    def ytdlp_progress_hook(d):
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
        
        'postprocessor_hooks': [handbrake_postprocessor_hook],
        'progress_hooks': [ytdlp_progress_hook],
        'quiet': True,
        'no_color': True,
        'no_warnings': True,
    }

    try:
        with yt_dlp.YoutubeDL(yt_dlp_options) as ydl:
            if progress_callback:
                progress_callback(f"Initializing download connection...")
            info = ydl.extract_info(url, download=True)
            
            # Write metadata to history file
            try:
                import json
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
                
                history_data.append({
                    "title": title,
                    "channel": channel,
                    "url": video_url
                })
                
                with open(history_file, 'w', encoding='utf-8') as f:
                    json.dump(history_data, f, indent=4)
            except Exception as e:
                print(f"Failed to log history: {e}")

        if progress_callback:
            progress_callback("All Tasks Completed Successfully!")
        if progress_bar_callback:
            progress_bar_callback(1.0)
            
    except Exception as e:
        if progress_callback:
            progress_callback(f"AN UNEXPECTED ERROR OCCURRED: {e}")