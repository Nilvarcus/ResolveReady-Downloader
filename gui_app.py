import customtkinter as ctk
import tkinter.filedialog as fd
import threading
import queue
import os
import sys
import json
import re
import ctypes

import updater
import logger

# ==============================================================================
# THEME & APPEARANCE
# ==============================================================================
# We use the built-in dark-blue theme as a base and override colours on each
# widget explicitly. This avoids the fragility of a custom theme JSON file
# (which must list every property CustomTkinter expects or it raises KeyError).
ctk.set_default_color_theme("dark-blue")
ctk.set_appearance_mode("Dark")

# ── Crimson palette ──────────────────────────────────────────────────────────
# Centralised color constants so every widget references the same scheme.
CRIMSON        = "#DC143C"
CRIMSON_DARK   = "#9B0F2A"
CRIMSON_BRIGHT = "#FF2D55"
CRIMSON_GLOW   = "#FF4D6D"
BG_DEEP        = "#0A0A0A"
BG_CARD        = "#141414"
BG_CARD_LIGHT  = "#1C1C1C"
BG_INPUT       = "#111111"
TEXT_PRIMARY   = "#E8E8E8"
TEXT_SECONDARY = "#888888"
TEXT_DIM       = "#555555"
BORDER_SUBTLE  = "#222222"
STATUS_OK      = "#2ECC71"
STATUS_ERROR   = "#E74C3C"
STATUS_WARN    = "#F39C12"
STATUS_CANCEL  = "#666666"
STATUS_PENDING = "#555555"

# Font family — falls back gracefully if Segoe UI isn't available
FONT_FAMILY = "Segoe UI"
APP_VERSION = "1.4"

# ==============================================================================
# SETTINGS PERSISTENCE
# ==============================================================================
if getattr(sys, 'frozen', False):
    STATE_DIR = os.path.dirname(sys.executable)
else:
    STATE_DIR = os.path.dirname(os.path.abspath(__file__))

SETTINGS_FILE = os.path.join(STATE_DIR, "settings.json")


def load_settings():
    """Load persisted settings (output_dir, resolution) from settings.json."""
    defaults = {"output_dir": STATE_DIR, "resolution": "1080p"}
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                defaults["output_dir"] = data.get("output_dir", defaults["output_dir"])
                defaults["resolution"] = data.get("resolution", defaults["resolution"])
    except Exception:
        pass
    return defaults


def save_settings(output_dir, resolution):
    """Persist settings to settings.json so they survive app restarts."""
    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump({"output_dir": output_dir, "resolution": resolution}, f, indent=4)
    except Exception as e:
        logger.log(f"Failed to save settings: {e}")


# ==============================================================================
# CUSTOM WIDGETS
# ==============================================================================

class StatusDot(ctk.CTkLabel):
    """A small circular status indicator that changes color with state."""

    def __init__(self, master, color=STATUS_PENDING, size=10, **kwargs):
        self._size = size
        self._color = color
        super().__init__(master, text="", width=size, height=size, **kwargs)
        self._update_appearance()

    def _update_appearance(self):
        """Render the dot using a Unicode circle with the current color."""
        super().configure(text="\u25CF", text_color=self._color,
                          font=ctk.CTkFont(family=FONT_FAMILY, size=self._size + 2))

    def set_color(self, color):
        self._color = color
        self._update_appearance()


class CardFrame(ctk.CTkFrame):
    """A card-style container with a subtle border and rounded corners."""

    def __init__(self, master, title=None, **kwargs):
        super().__init__(
            master,
            fg_color=BG_CARD,
            corner_radius=12,
            border_width=1,
            border_color=BORDER_SUBTLE,
            **kwargs
        )
        if title:
            self._title_label = ctk.CTkLabel(
                self, text=title,
                font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
                text_color=CRIMSON,
                anchor="w"
            )
            self._title_label.pack(anchor="w", padx=18, pady=(14, 8))


class QueueRow(ctk.CTkFrame):
    """A single queue item row with a status dot, label, error button, and remove button."""

    def __init__(self, master, url, item_id, on_remove, on_show_error=None, **kwargs):
        super().__init__(
            master,
            fg_color=BG_CARD_LIGHT,
            corner_radius=8,
            border_width=0,
            **kwargs
        )

        self.item_id = item_id
        self._url = url  # Store for clean status updates
        self._on_show_error = on_show_error

        # Status dot
        self.dot = StatusDot(self, color=STATUS_PENDING, size=9)
        self.dot.pack(side="left", padx=(10, 8), pady=8)

        # URL label (starts with "Pending" prefix for consistency)
        self.label = ctk.CTkLabel(
            self, text=f"Pending  \u00B7  {url}",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color=TEXT_SECONDARY,
            anchor="w"
        )
        self.label.pack(side="left", fill="x", expand=True, padx=(0, 8), pady=8)

        # Error details button — hidden by default, shown only on error status
        self.error_btn = ctk.CTkButton(
            self, text="\u26A0", width=28, height=24,
            fg_color="transparent", hover_color=BG_DEEP,
            text_color=STATUS_ERROR,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            corner_radius=6,
            command=lambda: on_show_error(item_id) if on_show_error else None
        )
        # Packed dynamically in set_status when status == 'error'

        # Remove button
        self.remove_btn = ctk.CTkButton(
            self, text="\u2715", width=28, height=24,
            fg_color="transparent", hover_color=BG_DEEP,
            text_color=TEXT_DIM,
            font=ctk.CTkFont(family=FONT_FAMILY, size=10),
            corner_radius=6,
            command=lambda: on_remove(item_id)
        )
        self.remove_btn.pack(side="right", padx=(0, 8), pady=8)

    def set_status(self, status_text, color):
        """Update the row's visual state.

        Internal status values are lowercase ('pending', 'processing',
        'done', 'error', 'cancelled'). The display text is capitalized
        here so the user sees a clean label like "Done" instead of "done".
        The ⚠ button is shown only when the item has errored.
        """
        self.dot.set_color(color)
        display = status_text.capitalize() if status_text else status_text
        self.label.configure(
            text=f"{display}  \u00B7  {self._url}",
            text_color=color if status_text != "pending" else TEXT_SECONDARY
        )

        # Show or hide the error details button
        if status_text == "error":
            self.error_btn.pack(side="right", padx=(0, 4), pady=8)
        else:
            self.error_btn.pack_forget()


# ==============================================================================
# MAIN APPLICATION
# ==============================================================================

class YoutubeDownloaderApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # ── Window setup ─────────────────────────────────────────────────────
        self.title(f"Resolve-Ready Downloader v{APP_VERSION}")
        self.geometry("620x810")
        self.resizable(False, False)
        self.configure(fg_color=BG_DEEP)

        # Set AppUserModelID for Windows Taskbar Icon
        try:
            myappid = 'nilvarcus.resolveready.downloader.1.3'
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception:
            pass

        # Window Icon
        icon_file = "Nilvarcus-Resolve-Downloader-icon.ico"
        if getattr(sys, 'frozen', False):
            icon_path = os.path.join(sys._MEIPASS, icon_file)
        else:
            icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), icon_file)

        try:
            self.iconbitmap(icon_path)
        except Exception as e:
            logger.log(f"Could not load icon: {e}")

        # ── State ────────────────────────────────────────────────────────────
        logger.log(
            f"Starting Resolve-Ready Downloader v{APP_VERSION}; "
            f"frozen={getattr(sys, 'frozen', False)}; "
            f"executable={sys.executable}; "
            f"bundle={getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))}; "
            f"updater_version=1.4",
            level="INFO",
        )
        self.download_queue = []
        self._queue_lock = threading.RLock()
        self._ui_events = queue.Queue()
        self.is_processing = False
        self.current_cancel_event = None
        self._queue_counter = 0
        self.after(50, self._drain_ui_events)

        settings = load_settings()
        self.selected_output_dir = settings["output_dir"]
        self._saved_resolution = settings["resolution"]

        # ── Build UI ─────────────────────────────────────────────────────────
        self._build_header()
        self._build_input_section()
        self._build_output_section()
        self._build_actions()
        self._build_status_bar()
        self._build_queue_section()

        # Start the updater thread
        threading.Thread(
            target=updater.check_and_update_ytdlp,
            kwargs={'status_callback': self.update_status, 'finish_callback': self._on_updater_finished},
            daemon=True
        ).start()

    # ──────────────────────────────────────────────────────────────────────────
    # UI CONSTRUCTION
    # ──────────────────────────────────────────────────────────────────────────

    def _build_header(self):
        """Top accent bar + branded header section."""
        # Crimson accent strip at the very top
        accent_bar = ctk.CTkFrame(self, fg_color=CRIMSON, height=5, corner_radius=0)
        accent_bar.pack(fill="x", side="top")

        # Header area
        header_frame = ctk.CTkFrame(self, fg_color=BG_DEEP, corner_radius=0)
        header_frame.pack(fill="x", padx=0, pady=0)

        # App title
        self.title_label = ctk.CTkLabel(
            header_frame,
            text="RESOLVE-READY DOWNLOADER",
            font=ctk.CTkFont(family=FONT_FAMILY, size=22, weight="bold"),
            text_color=TEXT_PRIMARY
        )
        self.title_label.pack(pady=(22, 2))

        # Subtitle
        self.subtitle_label = ctk.CTkLabel(
            header_frame,
            text="Download \u00B7 Transcode \u00B7 Edit without barriers",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color=CRIMSON_GLOW
        )
        self.subtitle_label.pack(pady=(0, 16))

    def _build_input_section(self):
        """URL input and resolution selection card."""
        card = CardFrame(self, title="SOURCE")
        card.pack(fill="x", padx=24, pady=(0, 12))

        # Inner padding frame
        inner = ctk.CTkFrame(card, fg_color="transparent", corner_radius=0)
        inner.pack(fill="x", padx=14, pady=(0, 14))

        # URL entry row
        url_row = ctk.CTkFrame(inner, fg_color="transparent", corner_radius=0)
        url_row.pack(fill="x", pady=(0, 10))
        url_row.grid_columnconfigure(0, weight=1)

        self.url_entry = ctk.CTkEntry(
            url_row,
            placeholder_text="Paste link(s) \u2014 separate multiple with commas or spaces...",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13),
            fg_color=BG_INPUT,
            border_color=CRIMSON_DARK,
            border_width=1,
            corner_radius=8,
            height=38,
            text_color=TEXT_PRIMARY
        )
        self.url_entry.grid(row=0, column=0, sticky="ew")

        self.paste_btn = ctk.CTkButton(
            url_row, text="Paste", width=60, height=38,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            fg_color=BG_CARD_LIGHT, hover_color=BG_DEEP,
            text_color=CRIMSON, corner_radius=8,
            border_width=1, border_color=BORDER_SUBTLE,
            command=self.paste_from_clipboard
        )
        self.paste_btn.grid(row=0, column=1, padx=(8, 0))

        # Resolution dropdown
        res_row = ctk.CTkFrame(inner, fg_color="transparent", corner_radius=0)
        res_row.pack(fill="x")

        res_label = ctk.CTkLabel(
            res_row, text="Quality",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color=TEXT_SECONDARY
        )
        res_label.pack(side="left", padx=(2, 0))

        self.res_optionmenu = ctk.CTkOptionMenu(
            res_row,
            values=["1080p", "1440p (2K)", "2160p (4K)"],
            command=self._on_resolution_changed,
            fg_color=BG_INPUT,
            button_color=CRIMSON,
            button_hover_color=CRIMSON_DARK,
            text_color=TEXT_PRIMARY,
            dropdown_fg_color=BG_CARD_LIGHT,
            dropdown_hover_color=BG_DEEP,
            dropdown_text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            width=140, height=34,
            corner_radius=8
        )
        self.res_optionmenu.set(self._saved_resolution)
        self.res_optionmenu.pack(side="right", padx=(0, 2))

    def _build_output_section(self):
        """Output folder selection card."""
        card = CardFrame(self, title="DESTINATION")
        card.pack(fill="x", padx=24, pady=(0, 12))

        inner = ctk.CTkFrame(card, fg_color="transparent", corner_radius=0)
        inner.pack(fill="x", padx=14, pady=(0, 14))

        # Folder button + path display
        row = ctk.CTkFrame(inner, fg_color="transparent", corner_radius=0)
        row.pack(fill="x")
        row.grid_columnconfigure(1, weight=1)

        self.folder_btn = ctk.CTkButton(
            row, text="Browse", width=90, height=34,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            fg_color=BG_CARD_LIGHT, hover_color=BG_DEEP,
            text_color=CRIMSON, corner_radius=8,
            border_width=1, border_color=BORDER_SUBTLE,
            command=self.pick_folder
        )
        self.folder_btn.grid(row=0, column=0, padx=(2, 10), pady=(0, 4))

        # Truncated path display
        display_path = self._truncate_path(self.selected_output_dir, 45)
        self.active_path_label = ctk.CTkLabel(
            row, text=display_path,
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color=TEXT_DIM,
            anchor="w"
        )
        self.active_path_label.grid(row=0, column=1, padx=(0, 2), pady=(0, 4), sticky="w")

    def _build_actions(self):
        """Add to Queue + Cancel button row."""
        action_frame = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        action_frame.pack(fill="x", padx=24, pady=(2, 8))
        action_frame.grid_columnconfigure(0, weight=3)
        action_frame.grid_columnconfigure(1, weight=1)

        # Add to Queue — primary crimson button
        self.download_btn = ctk.CTkButton(
            action_frame,
            text="\u25B6  ADD TO QUEUE",
            font=ctk.CTkFont(family=FONT_FAMILY, size=14, weight="bold"),
            fg_color=CRIMSON, hover_color=CRIMSON_DARK,
            text_color="#FFFFFF", text_color_disabled="#5A2020",
            corner_radius=10,
            height=44, state="disabled",
            command=self.add_to_queue
        )
        self.download_btn.grid(row=0, column=0, padx=(0, 8), sticky="we")

        # Cancel — secondary dark button
        self.cancel_btn = ctk.CTkButton(
            action_frame,
            text="\u2715  CANCEL",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
            fg_color=BG_CARD_LIGHT, hover_color=STATUS_ERROR,
            text_color=TEXT_SECONDARY, text_color_disabled=TEXT_DIM,
            corner_radius=10,
            height=44, state="disabled",
            border_width=1, border_color=BORDER_SUBTLE,
            command=self.cancel_current
        )
        self.cancel_btn.grid(row=0, column=1, sticky="we")

    def _build_status_bar(self):
        """Status label + progress bar strip."""
        status_frame = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=12,
                                    border_width=1, border_color=BORDER_SUBTLE)
        status_frame.pack(fill="x", padx=24, pady=(0, 12))

        inner = ctk.CTkFrame(status_frame, fg_color="transparent", corner_radius=0)
        inner.pack(fill="x", padx=16, pady=12)

        # Status dot + label
        status_row = ctk.CTkFrame(inner, fg_color="transparent", corner_radius=0)
        status_row.pack(fill="x", pady=(0, 8))

        self.status_dot = StatusDot(status_row, color=CRIMSON, size=9)
        self.status_dot.pack(side="left", padx=(0, 8))

        self.status_label = ctk.CTkLabel(
            status_row, text="Initializing updater...",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            text_color=TEXT_PRIMARY, anchor="w"
        )
        self.status_label.pack(side="left", fill="x", expand=True)

        # Progress bar
        self.progress_bar = ctk.CTkProgressBar(
            inner, height=6, corner_radius=3,
            fg_color=BG_DEEP, progress_color=CRIMSON
        )
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x")

    def _build_queue_section(self):
        """Download queue display card."""
        # Queue header with title + clear button
        queue_header = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        queue_header.pack(fill="x", padx=24, pady=(2, 8))

        self.queue_label = ctk.CTkLabel(
            queue_header, text="QUEUE",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            text_color=CRIMSON
        )
        self.queue_label.pack(side="left")

        self.queue_count_label = ctk.CTkLabel(
            queue_header, text="0 items",
            font=ctk.CTkFont(family=FONT_FAMILY, size=10),
            text_color=TEXT_DIM
        )
        self.queue_count_label.pack(side="left", padx=(8, 0))

        self.clear_btn = ctk.CTkButton(
            queue_header, text="Clear", width=80, height=24,
            font=ctk.CTkFont(family=FONT_FAMILY, size=10),
            fg_color="transparent", hover_color=BG_CARD_LIGHT,
            text_color=TEXT_DIM, text_color_disabled="#333333",
            corner_radius=6,
            border_width=1, border_color=BORDER_SUBTLE,
            state="disabled",
            command=self.clear_completed
        )
        self.clear_btn.pack(side="right")

        # Error Log button — opens a popup showing the full error.log
        self.log_btn = ctk.CTkButton(
            queue_header, text="\u26A0  Error Log", width=100, height=24,
            font=ctk.CTkFont(family=FONT_FAMILY, size=10),
            fg_color="transparent", hover_color=BG_CARD_LIGHT,
            text_color=STATUS_ERROR,
            corner_radius=6,
            border_width=1, border_color=BORDER_SUBTLE,
            command=self._show_error_log
        )
        self.log_btn.pack(side="right", padx=(0, 8))

        # Scrollable queue frame
        self.queue_frame = ctk.CTkScrollableFrame(
            self, width=560, height=180,
            fg_color=BG_CARD, corner_radius=12,
            border_width=1, border_color=BORDER_SUBTLE,
            label_fg_color=BG_CARD
        )
        self.queue_frame.pack(padx=24, pady=(0, 16), fill="both", expand=True)

    # ──────────────────────────────────────────────────────────────────────────
    # HELPERS
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _truncate_path(path, max_len):
        """Truncate long paths with an ellipsis in the middle."""
        if len(path) <= max_len:
            return path
        half = max_len // 2 - 2
        return path[:half] + "..." + path[-half:]

    def _update_queue_count(self):
        """Refresh the 'N items' count label."""
        count = len(self.download_queue)
        self.queue_count_label.configure(text=f"{count} item{'s' if count != 1 else ''}")

    # ──────────────────────────────────────────────────────────────────────────
    # UPDATER COMPLETION
    # ──────────────────────────────────────────────────────────────────────────

    def _on_updater_finished(self, success=True, error_message=None):
        """Load the backend only after the updater has verified dependencies."""
        if not success:
            message = error_message or "yt-dlp could not be prepared."
            logger.log(f"Updater did not make the backend ready: {message}")
            self._run_on_ui(lambda: self._show_backend_error(message))
            return

        try:
            import downloader as backend
            self.backend = backend
            self._run_on_ui(self._enable_downloads)
        except Exception as exc:
            err_msg = str(exc)
            logger.log_exception("Failed to load backend after updater finished")
            self._run_on_ui(lambda: self._show_backend_error(
                f"Backend could not be loaded: {err_msg}"
            ))

    def _enable_downloads(self):
        self.download_btn.configure(state="normal")
        self.status_label.configure(text=f"Ready. v{APP_VERSION}", text_color=TEXT_PRIMARY)
        self.status_dot.set_color(STATUS_OK)

    def _show_backend_error(self, message):
        self.download_btn.configure(state="disabled")
        self.status_label.configure(text=message, text_color=STATUS_ERROR)
        self.status_dot.set_color(STATUS_ERROR)

    # ──────────────────────────────────────────────────────────────────────────
    # SETTINGS
    # ──────────────────────────────────────────────────────────────────────────

    def _on_resolution_changed(self, value):
        save_settings(self.selected_output_dir, value)

    # ──────────────────────────────────────────────────────────────────────────
    # CLIPBOARD
    # ──────────────────────────────────────────────────────────────────────────

    def paste_from_clipboard(self):
        """Paste clipboard contents into the URL entry field."""
        try:
            clip = self.clipboard_get()
            if clip:
                self.url_entry.delete(0, 'end')
                self.url_entry.insert(0, clip.strip())
        except Exception:
            self.update_status("Clipboard is empty or unavailable.", STATUS_WARN)

    # ──────────────────────────────────────────────────────────────────────────
    # FOLDER PICKER
    # ──────────────────────────────────────────────────────────────────────────

    def pick_folder(self):
        folder_selected = fd.askdirectory(initialdir=self.selected_output_dir)
        if folder_selected:
            self.selected_output_dir = folder_selected
            self.active_path_label.configure(text=self._truncate_path(folder_selected, 45))
            save_settings(folder_selected, self.res_optionmenu.get())

    # ──────────────────────────────────────────────────────────────────────────
    # THREAD-SAFE UI UPDATES
    # ──────────────────────────────────────────────────────────────────────────

    def _run_on_ui(self, callback):
        """Queue a callback for execution by Tk's main thread."""
        self._ui_events.put(callback)

    def _drain_ui_events(self):
        """Run worker callbacks from the Tk main thread only."""
        try:
            while True:
                callback = self._ui_events.get_nowait()
                try:
                    callback()
                except Exception:
                    logger.log_exception("UI event callback failed")
        except queue.Empty:
            pass
        if self.winfo_exists():
            self.after(50, self._drain_ui_events)

    def update_status(self, message, color=None):
        """Queue a thread-safe status update without calling Tk from workers."""
        def _update():
            self.status_label.configure(text=message)
            if color:
                self.status_label.configure(text_color=color)
                self.status_dot.set_color(color)
        self._run_on_ui(_update)

    def update_progress(self, value):
        """Queue a thread-safe progress-bar update."""
        self._run_on_ui(lambda: self.progress_bar.set(value))

    def _set_queue_item_status(self, item_id, status, color):
        """Queue a queue-row state update for the Tk main thread."""
        def _update():
            item = self._find_queue_item(item_id)
            if item and item.get('row'):
                with self._queue_lock:
                    item['status'] = status
                item['row'].set_status(status, color)
        self._run_on_ui(_update)

    def _find_queue_item(self, item_id):
        with self._queue_lock:
            for item in self.download_queue:
                if item['id'] == item_id:
                    return item
        return None

    # ──────────────────────────────────────────────────────────────────────────
    # CANCEL
    # ──────────────────────────────────────────────────────────────────────────

    def cancel_current(self):
        """Signals the in-progress download to abort."""
        with self._queue_lock:
            cancel_event = self.current_cancel_event
        if cancel_event:
            cancel_event.set()
            self.update_status("Cancelling current download...", STATUS_WARN)

    # ──────────────────────────────────────────────────────────────────────────
    # QUEUE MANAGEMENT
    # ──────────────────────────────────────────────────────────────────────────

    def _remove_queue_item_ui(self, item_id):
        """Remove a queue item's UI row from the scrollable frame."""
        item = self._find_queue_item(item_id)
        if item and item.get('row'):
            try:
                item['row'].destroy()
            except Exception:
                pass

    def remove_queue_item(self, item_id):
        """Removes an item from the queue, unless it is currently processing.

        Any item that is pending, done, error, or cancelled can be removed via
        the X button. Only the currently-active download ('processing') cannot
        be removed here — that must be cancelled first via the Cancel button.
        """
        item = self._find_queue_item(item_id)
        if not item:
            return
        if item.get('status') == 'processing':
            return  # Can't remove an in-progress download; cancel it first.
        # IMPORTANT: destroy the UI row BEFORE removing from the list,
        # because _remove_queue_item_ui looks up the item in
        # download_queue to get the row reference.
        with self._queue_lock:
            if item.get('status') == 'processing':
                return
            self._remove_queue_item_ui(item_id)
            if item in self.download_queue:
                self.download_queue.remove(item)
        self._update_queue_count()
        self.update_status("Removed from queue.", TEXT_SECONDARY)

    def clear_completed(self):
        """Remove all completed, error, and cancelled items from the queue UI and state."""
        with self._queue_lock:
            to_remove = [
                item for item in self.download_queue
                if item.get('status') in ('done', 'error', 'cancelled')
            ]
            for item in to_remove:
                self._remove_queue_item_ui(item['id'])
                if item in self.download_queue:
                    self.download_queue.remove(item)
            has_clearable = any(
                item.get('status') in ('done', 'error', 'cancelled')
                for item in self.download_queue
            )
        if not has_clearable:
            self.clear_btn.configure(state="disabled")
        self._update_queue_count()
        self.update_status("Cleared completed items." if to_remove else "Nothing to clear.", TEXT_SECONDARY)

    # ──────────────────────────────────────────────────────────────────────────
    # ERROR VIEWER POPUPS
    # ──────────────────────────────────────────────────────────────────────────

    def _show_error_details_for_item(self, item_id):
        """Shows a popup with the captured error message for a specific queue item."""
        item = self._find_queue_item(item_id)
        if not item:
            return

        url = item.get('url', 'Unknown')
        error_msg = item.get('last_error') or "No detailed error was captured for this item.\n\nCheck the Error Log for the full traceback."

        popup = ctk.CTkToplevel(self)
        popup.title("Error Details")
        popup.geometry("560x300")
        popup.resizable(False, False)
        popup.configure(fg_color=BG_DEEP)
        popup.attributes("-topmost", True)
        popup.grab_set()

        # Header
        header = ctk.CTkLabel(
            popup, text="\u26A0  Download Error",
            font=ctk.CTkFont(family=FONT_FAMILY, size=16, weight="bold"),
            text_color=STATUS_ERROR
        )
        header.pack(anchor="w", padx=20, pady=(16, 4))

        # URL label
        url_label = ctk.CTkLabel(
            popup, text=f"URL: {url}",
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color=TEXT_SECONDARY, anchor="w"
        )
        url_label.pack(anchor="w", padx=20, pady=(0, 10))

        # Error text box
        textbox = ctk.CTkTextbox(
            popup, font=ctk.CTkFont(family="Consolas", size=12),
            fg_color=BG_CARD, border_width=1, border_color=BORDER_SUBTLE,
            corner_radius=8, text_color=TEXT_PRIMARY,
            wrap="word"
        )
        textbox.pack(fill="both", expand=True, padx=20, pady=(0, 16))
        textbox.insert("1.0", error_msg)
        textbox.configure(state="disabled")

        # Close button
        close_btn = ctk.CTkButton(
            popup, text="Close", width=100, height=32,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            fg_color=CRIMSON, hover_color=CRIMSON_DARK,
            text_color="#FFFFFF", corner_radius=8,
            command=popup.destroy
        )
        close_btn.pack(pady=(0, 16))

    def _show_error_log(self):
        """Opens a popup showing the full contents of error.log with Refresh/Clear buttons."""
        popup = ctk.CTkToplevel(self)
        popup.title("Error Log")
        popup.geometry("620x460")
        popup.resizable(False, False)
        popup.configure(fg_color=BG_DEEP)
        popup.attributes("-topmost", True)
        popup.grab_set()

        # Header
        header = ctk.CTkLabel(
            popup, text="\u26A0  Error Log",
            font=ctk.CTkFont(family=FONT_FAMILY, size=16, weight="bold"),
            text_color=STATUS_ERROR
        )
        header.pack(anchor="w", padx=20, pady=(16, 4))

        sub_label = ctk.CTkLabel(
            popup, text=f"{logger.LOG_FILE}",
            font=ctk.CTkFont(family="Consolas", size=10),
            text_color=TEXT_DIM, anchor="w"
        )
        sub_label.pack(anchor="w", padx=20, pady=(0, 10))

        # Log text box
        textbox = ctk.CTkTextbox(
            popup, font=ctk.CTkFont(family="Consolas", size=11),
            fg_color=BG_CARD, border_width=1, border_color=BORDER_SUBTLE,
            corner_radius=8, text_color=TEXT_PRIMARY,
            wrap="none"
        )
        textbox.pack(fill="both", expand=True, padx=20, pady=(0, 12))

        def _refresh_log():
            textbox.configure(state="normal")
            textbox.delete("1.0", "end")
            content = logger.read_log()
            textbox.insert("1.0", content if content else "(log is empty)")
            textbox.configure(state="disabled")
            textbox.see("end")

        def _clear_log():
            logger.clear_log()
            _refresh_log()

        # Button row
        btn_frame = ctk.CTkFrame(popup, fg_color="transparent", corner_radius=0)
        btn_frame.pack(fill="x", padx=20, pady=(0, 16))

        refresh_btn = ctk.CTkButton(
            btn_frame, text="\u21BB  Refresh", width=100, height=32,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            fg_color=BG_CARD_LIGHT, hover_color=BG_DEEP,
            text_color=CRIMSON, corner_radius=8,
            border_width=1, border_color=BORDER_SUBTLE,
            command=_refresh_log
        )
        refresh_btn.pack(side="left", padx=(0, 8))

        clear_log_btn = ctk.CTkButton(
            btn_frame, text="Clear Log", width=100, height=32,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            fg_color=BG_CARD_LIGHT, hover_color=BG_DEEP,
            text_color=TEXT_SECONDARY, corner_radius=8,
            border_width=1, border_color=BORDER_SUBTLE,
            command=_clear_log
        )
        clear_log_btn.pack(side="left", padx=(0, 8))

        close_btn = ctk.CTkButton(
            btn_frame, text="Close", width=100, height=32,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            fg_color=CRIMSON, hover_color=CRIMSON_DARK,
            text_color="#FFFFFF", corner_radius=8,
            command=popup.destroy
        )
        close_btn.pack(side="right")

        # Load initial content
        _refresh_log()

    # ──────────────────────────────────────────────────────────────────────────
    # QUEUE PROCESSING
    # ──────────────────────────────────────────────────────────────────────────

    def process_queue(self):
        """Background thread target that processes the queue sequentially."""
        self._run_on_ui(lambda: self.cancel_btn.configure(
            state="normal", text_color="#FFFFFF"
        ))
        self.update_status("Processing queue...", CRIMSON_BRIGHT)

        while True:
            with self._queue_lock:
                current = next(
                    (item for item in self.download_queue
                     if item.get('status') == 'pending'),
                    None,
                )
                if current is None:
                    break
                current['status'] = 'processing'
                cancel_event = threading.Event()
                self.current_cancel_event = cancel_event

            item_id = current['id']
            url = current['url']
            output_dir = current['output_dir']
            resolution = current['resolution']
            self._set_queue_item_status(item_id, "processing", STATUS_WARN)

            # Capture only final/actionable errors for the queue row. Intermediate
            # yt-dlp retry diagnostics remain in error.log.
            def _capture_callback(message, color=None, _item=current):
                self.update_status(message, color)
                if (
                    color == STATUS_ERROR
                    or message.startswith((
                        "ERROR", "Encoding failed", "WARNING: Failed",
                    ))
                ):
                    with self._queue_lock:
                        _item['last_error'] = message

            success = False
            try:
                success = self.backend.download_youtube_video(
                    url=url,
                    output_dir=output_dir,
                    resolution=resolution,
                    progress_callback=_capture_callback,
                    progress_bar_callback=self.update_progress,
                    cancel_event=cancel_event,
                )
            except Exception as exc:
                err_msg = str(exc)
                self.update_status(f"Error processing {url}: {err_msg}", STATUS_ERROR)
                with self._queue_lock:
                    current['last_error'] = f"Exception: {err_msg}"
                logger.log_exception(f"process_queue error for {url}")

            with self._queue_lock:
                if cancel_event.is_set():
                    final_status, final_color = "cancelled", STATUS_CANCEL
                elif success:
                    final_status, final_color = "done", STATUS_OK
                else:
                    if not current.get('last_error'):
                        current['last_error'] = (
                            "Download failed with no specific error message captured.\n\n"
                            "Check the Error Log for the full traceback."
                        )
                    final_status, final_color = "error", STATUS_ERROR
                current['status'] = final_status
                self.current_cancel_event = None

            self._set_queue_item_status(item_id, final_status, final_color)
            self.update_progress(0)
            self._run_on_ui(self._maybe_enable_clear)

        with self._queue_lock:
            self.is_processing = False
            has_errors = any(
                item.get('status') == 'error' for item in self.download_queue
            )
        self._run_on_ui(lambda: self.cancel_btn.configure(
            state="disabled", text_color=TEXT_SECONDARY
        ))
        self.update_status(
            "Queue finished with errors." if has_errors else "Queue finished.",
            STATUS_ERROR if has_errors else STATUS_OK,
        )
        self.update_progress(0)

    def _maybe_enable_clear(self):
        with self._queue_lock:
            has_clearable = any(
                item.get('status') in ('done', 'error', 'cancelled')
                for item in self.download_queue
            )
        if has_clearable:
            self.clear_btn.configure(state="normal", text_color=CRIMSON)

    # ──────────────────────────────────────────────────────────────────────────
    # ADD TO QUEUE
    # ──────────────────────────────────────────────────────────────────────────

    def add_to_queue(self):
        raw_input = self.url_entry.get().strip()

        if not raw_input:
            self.update_status("Error: Please enter at least one valid URL.", STATUS_ERROR)
            return

        urls = self._split_urls(raw_input)

        if not urls:
            self.update_status("Error: No valid URLs found.", STATUS_ERROR)
            return

        resolution = self.res_optionmenu.get()
        output_dir = self.selected_output_dir

        added_count = 0
        needs_playlist_expansion = []

        for url in urls:
            url = url.strip()
            if not url:
                continue

            identity = self.backend.get_download_identity(url)
            with self._queue_lock:
                already_queued = any(
                    item.get('identity') == identity or item['url'] == url
                    for item in self.download_queue
                )
            if already_queued:
                self.update_status(f"Already in queue: {url}", STATUS_WARN)
                continue

            needs_playlist_expansion.append(url)
            added_count += 1

        if added_count == 0:
            return

        self.url_entry.delete(0, 'end')
        self.update_status(f"Added {added_count} item(s) to queue...", CRIMSON_BRIGHT)

        threading.Thread(
            target=self._expand_and_add,
            args=(needs_playlist_expansion, resolution, output_dir),
            daemon=True
        ).start()

    def _split_urls(self, raw):
        """Split a raw text blob into individual URL strings."""
        parts = re.split(r'[\n,\s]+', raw)
        return [p.strip() for p in parts if p.strip()]

    def _expand_and_add(self, urls, resolution, output_dir):
        """
        Runs in a background thread. For each URL, checks if it's a playlist
        and expands it into individual video URLs, then adds each to the queue.
        """
        all_urls = []
        for url in urls:
            try:
                entries = self.backend.extract_playlist_entries(url)
                if len(entries) > 1:
                    self.update_status(f"Found playlist with {len(entries)} videos", CRIMSON_BRIGHT)
                all_urls.extend(entries)
            except Exception as exc:
                self.update_status(
                    f"WARNING: Could not expand playlist; treating it as one URL ({exc})",
                    STATUS_WARN,
                )
                logger.log_exception(f"Playlist expansion failed for {url}")
                all_urls.append(url)

        for url in all_urls:
            url = url.strip()
            if not url:
                continue
            self._run_on_ui(
                lambda u=url: self._add_queue_item(u, resolution, output_dir)
            )

        self._run_on_ui(self._start_processing_if_idle)

    def _add_queue_item(self, url, resolution, output_dir):
        """Adds a new, not-yet-downloaded item to the queue state."""
        identity = self.backend.get_download_identity(url)
        with self._queue_lock:
            if any(
                item.get('identity') == identity or item['url'] == url
                for item in self.download_queue
            ):
                self.update_status(f"Already in queue: {url}", STATUS_WARN)
                return

        history_record = self.backend.get_download_history_record(url, output_dir)
        if history_record:
            title = history_record.get('title') or url
            self.update_status(f"Already downloaded: {title}", STATUS_WARN)
            return

        with self._queue_lock:
            self._queue_counter += 1
            item_id = f"item_{self._queue_counter}"

        row = QueueRow(
            self.queue_frame,
            url=url,
            item_id=item_id,
            on_remove=self.remove_queue_item,
            on_show_error=self._show_error_details_for_item
        )
        row.pack(fill="x", pady=3, padx=4)

        item = {
            'id': item_id,
            'url': url,
            'identity': identity,
            'resolution': resolution,
            'output_dir': output_dir,
            'status': 'pending',
            'row': row,
            'last_error': None,
        }
        with self._queue_lock:
            self.download_queue.append(item)
        self._update_queue_count()

    def _start_processing_if_idle(self):
        """Start the queue processor if nothing is currently running."""
        with self._queue_lock:
            has_pending = any(
                item.get('status') == 'pending'
                for item in self.download_queue
            )
            if not self.is_processing and has_pending:
                self.is_processing = True
                should_start = True
            else:
                should_start = False
        if should_start:
            threading.Thread(target=self.process_queue, daemon=True).start()


if __name__ == "__main__":
    app = YoutubeDownloaderApp()
    app.mainloop()
