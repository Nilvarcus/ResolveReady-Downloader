import importlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile

import logger

# Keep checks infrequent, but force one check after changing the update policy.
UPDATE_CHECK_INTERVAL = 24 * 60 * 60
LAST_CHECK_FILENAME = ".ytdlp_last_check_v3"
NIGHTLY_REPOSITORY = "yt-dlp/yt-dlp-nightly-builds"
STABLE_REPOSITORY = "yt-dlp/yt-dlp"

if getattr(sys, 'frozen', False):
    STATE_DIR = os.path.dirname(sys.executable)
else:
    STATE_DIR = os.path.dirname(os.path.abspath(__file__))

LAST_CHECK_FILE = os.path.join(STATE_DIR, LAST_CHECK_FILENAME)


def _should_check_for_update():
    """Return True if enough time has elapsed since the last verified check."""
    try:
        if os.path.exists(LAST_CHECK_FILE):
            with open(LAST_CHECK_FILE, 'r', encoding='utf-8') as marker:
                last = float(marker.read().strip())
            return (time.time() - last) >= UPDATE_CHECK_INTERVAL
    except (OSError, ValueError):
        pass
    return True


def _source_dependencies_ready():
    """Return whether source mode has usable yt-dlp and yt-dlp-ejs packages."""
    try:
        from importlib.metadata import PackageNotFoundError, version

        yt_dlp_version = version("yt-dlp")
        ejs_version = version("yt-dlp-ejs")
        return bool(yt_dlp_version and ejs_version)
    except (ImportError, PackageNotFoundError):
        return False
    except Exception:
        return False


def _valid_zipapp(path):
    """Return True when path is a readable yt-dlp zipapp."""
    try:
        with zipfile.ZipFile(path, 'r') as archive:
            return (
                archive.testzip() is None
                and 'yt_dlp/version.py' in archive.namelist()
            )
    except (OSError, zipfile.BadZipFile):
        return False


def _read_zipapp_version(path):
    """Read yt-dlp's embedded version without importing the zipapp."""
    if not _valid_zipapp(path):
        return None
    try:
        with zipfile.ZipFile(path, 'r') as archive:
            content = archive.read('yt_dlp/version.py').decode('utf-8')
        match = re.search(r"__version__\s*=\s*['\"]([^'\"]+)['\"]", content)
        return match.group(1) if match else None
    except (OSError, UnicodeDecodeError, zipfile.BadZipFile):
        return None


def _repository_api_url(repository):
    return f"https://api.github.com/repos/{repository}/releases/latest"


def _repository_download_url(repository):
    return f"https://github.com/{repository}/releases/latest/download/yt-dlp"


def _latest_release_tag(repository):
    """Return a repository's latest release tag, or None on network failure."""
    request = urllib.request.Request(
        _repository_api_url(repository),
        headers={"User-Agent": "ResolveReadyDownloader/1.4"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        data = json.loads(response.read().decode('utf-8'))
    return data.get('tag_name')


def _download_zipapp(download_url, zip_path):
    """Download and validate a zipapp before atomically replacing the candidate."""
    zip_dir = os.path.dirname(os.path.abspath(zip_path)) or os.getcwd()
    os.makedirs(zip_dir, exist_ok=True)
    temporary_path = None
    request = urllib.request.Request(
        download_url,
        headers={"User-Agent": "ResolveReadyDownloader/1.4"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            with tempfile.NamedTemporaryFile(
                mode='wb',
                prefix='.yt-dlp-',
                suffix='.download',
                dir=zip_dir,
                delete=False,
            ) as temporary_file:
                temporary_path = temporary_file.name
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    temporary_file.write(chunk)

        if not _valid_zipapp(temporary_path):
            raise ValueError("Downloaded yt-dlp package is not a valid zipapp")
        os.replace(temporary_path, zip_path)
    finally:
        if temporary_path:
            try:
                if os.path.exists(temporary_path):
                    os.remove(temporary_path)
            except OSError:
                pass


def _record_check_time():
    """Persist the current time as the last successful update check."""
    try:
        with open(LAST_CHECK_FILE, 'w', encoding='utf-8') as marker:
            marker.write(str(time.time()))
    except OSError:
        pass


def _clear_loaded_yt_dlp():
    """Remove partially imported yt-dlp modules before trying another package."""
    for module_name in list(sys.modules):
        if module_name == "yt_dlp" or module_name.startswith("yt_dlp."):
            del sys.modules[module_name]


def _install_zipapp_importer(zip_path):
    """Make imports resolve from the updateable yt-dlp zipapp."""
    if not os.path.exists(zip_path):
        return False
    if zip_path not in sys.path:
        sys.path.insert(0, zip_path)

    import importlib.machinery

    class YtDlpZipFinder:
        @classmethod
        def find_spec(cls, fullname, path=None, target=None):
            if fullname == "yt_dlp" or fullname.startswith("yt_dlp."):
                return importlib.machinery.PathFinder.find_spec(fullname, path, target)
            return None

    if not any(
        isinstance(finder, type) and finder.__name__ == "YtDlpZipFinder"
        for finder in sys.meta_path
    ):
        sys.meta_path.insert(0, YtDlpZipFinder)
    return True


def _verify_zipapp_importable(zip_path):
    """Verify that the packaged zipapp can be imported by this interpreter."""
    if not _valid_zipapp(zip_path) or not _install_zipapp_importer(zip_path):
        return False
    try:
        importlib.invalidate_caches()
        module = importlib.import_module("yt_dlp")
        return bool(getattr(module, "__version__", None) or getattr(module, "version", None))
    except Exception:
        logger.log_exception(f"yt-dlp zipapp import verification failed: {zip_path}")
        _clear_loaded_yt_dlp()
        return False


def _backup_path(target_path):
    directory = os.path.dirname(os.path.abspath(target_path)) or os.getcwd()
    descriptor, path = tempfile.mkstemp(prefix='.yt-dlp-stable-', dir=directory)
    os.close(descriptor)
    os.remove(path)
    return path


def _promote_and_verify(candidate_path, target_path):
    """Replace the active zipapp only if the candidate imports successfully."""
    backup = None
    try:
        if os.path.exists(target_path):
            backup = _backup_path(target_path)
            os.replace(target_path, backup)
        os.replace(candidate_path, target_path)
        _clear_loaded_yt_dlp()
        if _verify_zipapp_importable(target_path):
            if backup and os.path.exists(backup):
                os.remove(backup)
            return True
    except Exception:
        logger.log_exception(f"yt-dlp candidate promotion failed: {candidate_path}")

    _clear_loaded_yt_dlp()
    try:
        if os.path.exists(target_path):
            os.remove(target_path)
        if backup and os.path.exists(backup):
            os.replace(backup, target_path)
    except OSError:
        pass
    return False


def _attempt_frozen_channel(channel, repository, zip_path, latest_tag=None, status_callback=None):
    """Try to install one frozen-build channel, returning whether it is ready."""
    current_version = _read_zipapp_version(zip_path)
    if current_version and latest_tag and current_version == latest_tag:
        return _verify_zipapp_importable(zip_path)

    candidate_path = f"{zip_path}.{channel}.candidate"
    try:
        if status_callback:
            status_callback(f"Downloading yt-dlp {channel} update ({latest_tag or 'latest'})...")
        _download_zipapp(_repository_download_url(repository), candidate_path)
        return _promote_and_verify(candidate_path, zip_path)
    except Exception as exc:
        logger.log(f"yt-dlp {channel} update failed: {exc}")
        try:
            if os.path.exists(candidate_path):
                os.remove(candidate_path)
        except OSError:
            pass
        return False


def _run_source_pip_update(pre_release):
    """Install the requested channel and return (success, diagnostic)."""
    command = [sys.executable, "-m", "pip", "install", "-U"]
    if pre_release:
        command.append("--pre")
    command.append("yt-dlp[default]")
    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=180,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0,
        )
        if not _source_dependencies_ready():
            return False, "yt-dlp or yt-dlp-ejs is unavailable after pip completed"
        return True, result.stdout.strip()[-500:]
    except Exception as exc:
        details = str(exc)
        if 'result' in locals() and result.stderr:
            details = f"{details}: {result.stderr.strip()[-500:]}"
        return False, details


def _finish(finish_callback, success, error_message):
    """Call the completion callback with the verified readiness result."""
    if finish_callback:
        finish_callback(success, error_message)


def check_and_update_ytdlp(status_callback=None, finish_callback=None):
    """Install nightly yt-dlp first, retaining stable as a verified fallback."""
    success = False
    error_message = None

    try:
        if not getattr(sys, 'frozen', False):
            dependencies_ready = _source_dependencies_ready()
            if not _should_check_for_update() and dependencies_ready:
                if status_callback:
                    status_callback("yt-dlp nightly/stable fallback is ready (recently verified).")
                success = True
                return

            if status_callback:
                status_callback("Checking yt-dlp nightly for the latest YouTube fixes...")

            nightly_ok, nightly_details = _run_source_pip_update(pre_release=True)
            if nightly_ok:
                _record_check_time()
                success = True
                if status_callback:
                    status_callback("yt-dlp nightly and YouTube support are ready.")
                return

            logger.log(f"yt-dlp nightly source update failed: {nightly_details}")
            if status_callback:
                status_callback("WARNING: Nightly update failed; trying stable yt-dlp fallback...")

            stable_ok, stable_details = _run_source_pip_update(pre_release=False)
            if stable_ok:
                _record_check_time()
                success = True
                if status_callback:
                    status_callback("Stable yt-dlp fallback is ready.")
                return

            error_message = f"Nightly and stable yt-dlp updates failed: {stable_details}"
            if status_callback:
                status_callback(f"ERROR: {error_message}")
            logger.log(error_message)
            return

        app_dir = os.path.dirname(sys.executable)
        zip_path = os.path.join(app_dir, "yt-dlp.zip")

        if _valid_zipapp(zip_path) and not _should_check_for_update():
            if _verify_zipapp_importable(zip_path):
                if status_callback:
                    status_callback("yt-dlp nightly/stable fallback is ready (recently verified).")
                success = True
                return

        if status_callback:
            status_callback("Checking yt-dlp nightly for the latest YouTube fixes...")

        try:
            nightly_tag = _latest_release_tag(NIGHTLY_REPOSITORY)
        except Exception as exc:
            nightly_tag = None
            logger.log(f"Nightly release check failed: {exc}")

        if _attempt_frozen_channel(
            "nightly",
            NIGHTLY_REPOSITORY,
            zip_path,
            nightly_tag,
            status_callback,
        ):
            _record_check_time()
            success = True
            if status_callback:
                status_callback("yt-dlp nightly and YouTube support are ready.")
            return

        if status_callback:
            status_callback("WARNING: Nightly package failed verification; trying stable fallback...")

        try:
            stable_tag = _latest_release_tag(STABLE_REPOSITORY)
        except Exception as exc:
            stable_tag = None
            logger.log(f"Stable release check failed: {exc}")

        if _valid_zipapp(zip_path) and _verify_zipapp_importable(zip_path):
            _record_check_time()
            success = True
            if status_callback:
                status_callback("Existing stable yt-dlp fallback is ready.")
            return

        if _attempt_frozen_channel(
            "stable",
            STABLE_REPOSITORY,
            zip_path,
            stable_tag,
            status_callback,
        ):
            _record_check_time()
            success = True
            if status_callback:
                status_callback("Stable yt-dlp fallback is ready.")
            return

        error_message = "Neither yt-dlp nightly nor the stable fallback could be verified"
        if status_callback:
            status_callback(f"ERROR: {error_message}")
    except Exception as exc:
        error_message = f"Updater error: {exc}"
        if status_callback:
            status_callback(f"ERROR: {error_message}")
        logger.log_exception("updater.py top-level error")
    finally:
        _finish(finish_callback, success, error_message)
