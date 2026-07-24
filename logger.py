# ==============================================================================
# LOGGING UTILITY
# ==============================================================================
# Lightweight file-based logger. In windowed (console=False) PyInstaller builds,
# print() output is silently swallowed, making debugging impossible in the wild.
# This module writes errors and important events to error.log next to the
# executable / script so there is always a diagnostic trail.
# ==============================================================================
import sys
import os
import datetime

if getattr(sys, 'frozen', False):
    LOG_DIR = os.path.dirname(sys.executable)
else:
    LOG_DIR = os.path.dirname(os.path.abspath(__file__))

LOG_FILE = os.path.join(LOG_DIR, "error.log")


def log(message, level="ERROR"):
    """
    Append a timestamped message to error.log.
    Also prints to console (harmless when running from source; swallowed when frozen).
    """
    try:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{timestamp}] [{level}] {message}\n"
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line)
        print(line, end="")
    except Exception:
        # If even logging fails, there's nothing more we can do safely.
        pass


def log_exception(context=""):
    """
    Convenience wrapper that logs the current exception with a context label.
    """
    import traceback
    try:
        exc_type, exc_value, exc_tb = sys.exc_info()
        tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        log(f"{context}\n{tb_text}" if context else tb_text, level="ERROR")
    except Exception:
        pass
