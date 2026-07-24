import sys
import os
import subprocess
import urllib.request
import json
import time

import logger

# How often (in seconds) to actually hit the network for an update check.
# Default: check at most once per day. Running the check every single launch
# is wasteful and can block startup on slow connections.
UPDATE_CHECK_INTERVAL = 24 * 60 * 60  # 24 hours

if getattr(sys, 'frozen', False):
    STATE_DIR = os.path.dirname(sys.executable)
else:
    STATE_DIR = os.path.dirname(os.path.abspath(__file__))

LAST_CHECK_FILE = os.path.join(STATE_DIR, ".ytdlp_last_check")


def _should_check_for_update():
    """Returns True if enough time has elapsed since the last update check."""
    try:
        if os.path.exists(LAST_CHECK_FILE):
            last = float(open(LAST_CHECK_FILE, 'r').read().strip())
            return (time.time() - last) >= UPDATE_CHECK_INTERVAL
    except Exception:
        pass
    return True


def _record_check_time():
    """Persist the current time as the last update-check timestamp."""
    try:
        with open(LAST_CHECK_FILE, 'w') as f:
            f.write(str(time.time()))
    except Exception:
        pass


def check_and_update_ytdlp(status_callback=None, finish_callback=None):
    """
    Checks for yt-dlp updates and installs them.
    Runs in a background thread. Calls callbacks to update the GUI.

    To avoid hitting the network on every single launch, an actual update
    check is performed at most once per day (tracked via .ytdlp_last_check).
    If the yt-dlp zipapp is missing entirely it is always downloaded.
    """
    try:
        if not getattr(sys, 'frozen', False):
            # Running from source (.py). Use pip to update — but only once per day.
            if not _should_check_for_update():
                if status_callback:
                    status_callback("yt-dlp update check skipped (recently checked).")
                return

            if status_callback:
                status_callback("Checking for yt-dlp updates (pip)...")

            try:
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-U", "yt-dlp"],
                    check=True,
                    capture_output=True,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
                )
                _record_check_time()
                if status_callback:
                    status_callback("yt-dlp is up to date.")
            except Exception as e:
                if status_callback:
                    status_callback(f"Failed to update yt-dlp via pip: {e}")
                logger.log(f"yt-dlp pip update failed: {e}")
        else:
            # Running as compiled executable (.exe). Use dynamic zipapp approach.
            app_dir = os.path.dirname(sys.executable)
            zip_path = os.path.join(app_dir, "yt-dlp.zip")

            # If the zipapp already exists and we checked recently, skip the
            # network round-trip entirely — the app stays responsive.
            if os.path.exists(zip_path) and not _should_check_for_update():
                if status_callback:
                    status_callback("yt-dlp is ready.")
                _install_zipapp_importer(zip_path)
                return

            if status_callback:
                status_callback("Checking for yt-dlp updates...")

            # Fetch latest release info from GitHub
            latest_version = None
            try:
                req = urllib.request.Request("https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest")
                with urllib.request.urlopen(req, timeout=10) as response:
                    data = json.loads(response.read().decode())
                    latest_version = data.get('tag_name')
            except Exception as e:
                if status_callback:
                    status_callback(f"Warning: Could not check GitHub for updates ({e})")
                logger.log(f"GitHub update check failed: {e}")

            # Determine current version if zip exists
            current_version = None
            if os.path.exists(zip_path):
                try:
                    import zipfile
                    with zipfile.ZipFile(zip_path, 'r') as z:
                        with z.open('yt_dlp/version.py') as f:
                            content = f.read().decode()
                            import re
                            match = re.search(r"__version__\s*=\s*['\"]([^'\"]+)['\"]", content)
                            if match:
                                current_version = match.group(1)
                except Exception:
                    pass

            if latest_version and current_version != latest_version:
                if status_callback:
                    status_callback(f"Downloading yt-dlp update ({latest_version})...")

                download_url = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp"
                try:
                    urllib.request.urlretrieve(download_url, zip_path)
                    _record_check_time()
                    if status_callback:
                        status_callback("yt-dlp update complete!")
                except Exception as e:
                    if status_callback:
                        status_callback(f"Failed to download update: {e}")
                    logger.log(f"yt-dlp zipapp download failed: {e}")
            elif not os.path.exists(zip_path) and not latest_version:
                # If we couldn't check version but the file doesn't exist at all, we must download it
                if status_callback:
                    status_callback("Downloading yt-dlp core components...")
                download_url = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp"
                try:
                    urllib.request.urlretrieve(download_url, zip_path)
                    _record_check_time()
                    if status_callback:
                        status_callback("yt-dlp components installed!")
                except Exception as e:
                    if status_callback:
                        status_callback(f"Critical Error: Failed to download yt-dlp ({e})")
                    logger.log(f"yt-dlp core download failed: {e}")
            else:
                _record_check_time()
                if status_callback:
                    status_callback("yt-dlp is up to date.")

            _install_zipapp_importer(zip_path)
    except Exception as e:
        if status_callback:
            status_callback(f"Updater Error: {e}")
        logger.log_exception("updater.py top-level error")
    finally:
        if finish_callback:
            finish_callback()


def _install_zipapp_importer(zip_path):
    """
    Adds the yt-dlp zipapp to sys.path and installs a custom meta-path finder
    so that yt_dlp imports resolve from the (updateable) zipapp rather than a
    possibly-stale PyInstaller-bundled copy.
    """
    if not os.path.exists(zip_path):
        return
    if zip_path not in sys.path:
        sys.path.insert(0, zip_path)

    import importlib.machinery

    class YtDlpZipFinder:
        @classmethod
        def find_spec(cls, fullname, path=None, target=None):
            if fullname.startswith("yt_dlp"):
                return importlib.machinery.PathFinder.find_spec(fullname, path, target)
            return None

    if not any(isinstance(f, type) and f.__name__ == "YtDlpZipFinder" for f in sys.meta_path):
        sys.meta_path.insert(0, YtDlpZipFinder)
