import customtkinter as ctk
import tkinter.filedialog as fd
import threading
import os
import sys

# Import our backend logic
import downloader as backend

# App Setup and Theming
ctk.set_appearance_mode("Dark")  # Modes: "System" (standard), "Dark", "Light"
ctk.set_default_color_theme("blue")  # Themes: "blue" (standard), "green", "dark-blue"

class YoutubeDownloaderApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Resolve-Ready Downloader")
        self.geometry("600x480")
        self.resizable(False, False)

        # Default Output Path (Next to exe/script)
        if getattr(sys, 'frozen', False):
            self.selected_output_dir = os.path.dirname(sys.executable)
        else:
            self.selected_output_dir = os.path.dirname(os.path.abspath(__file__))

        # --- UI LAYOUT ---
        
        # Title
        self.title_label = ctk.CTkLabel(self, text="YouTube to Resolve Converter", font=ctk.CTkFont(size=20, weight="bold"))
        self.title_label.pack(pady=(20, 20))

        # Main Container
        self.frame = ctk.CTkFrame(self, width=540)
        self.frame.pack(padx=20, pady=10, fill="both", expand=True)

        # 1. URL Input
        self.url_label = ctk.CTkLabel(self.frame, text="YouTube URL:")
        self.url_label.grid(row=0, column=0, padx=15, pady=(15, 5), sticky="w")
        self.url_entry = ctk.CTkEntry(self.frame, width=400, placeholder_text="Paste your link here...")
        self.url_entry.grid(row=0, column=1, padx=15, pady=(15, 5), sticky="ew")

        # 2. Resolution Options
        self.res_label = ctk.CTkLabel(self.frame, text="Resolution:")
        self.res_label.grid(row=1, column=0, padx=15, pady=10, sticky="w")
        self.res_optionmenu = ctk.CTkOptionMenu(self.frame, values=["1080p", "1440p (2K)", "2160p (4K)"])
        self.res_optionmenu.grid(row=1, column=1, padx=15, pady=10, sticky="w")

        # 3. Transcripts Toggle
        self.transcript_switch_var = ctk.StringVar(value="on")
        self.transcript_switch = ctk.CTkSwitch(
            self.frame, text="Download English Transcripts", 
            variable=self.transcript_switch_var, onvalue="on", offvalue="off"
        )
        self.transcript_switch.grid(row=2, column=0, columnspan=2, padx=15, pady=10, sticky="w")

        # 4. Output Folder
        self.folder_label = ctk.CTkLabel(self.frame, text="Output Folder:")
        self.folder_label.grid(row=3, column=0, padx=15, pady=10, sticky="w")
        
        self.folder_btn = ctk.CTkButton(self.frame, text="Choose Path", command=self.pick_folder, width=120)
        self.folder_btn.grid(row=3, column=1, padx=15, pady=10, sticky="w")
        
        self.active_path_label = ctk.CTkLabel(self.frame, text=self.selected_output_dir, text_color="gray", font=ctk.CTkFont(size=11))
        self.active_path_label.grid(row=4, column=0, columnspan=2, padx=15, pady=(0, 15), sticky="w")

        # 5. Download Action
        self.download_btn = ctk.CTkButton(
            self.frame, text="START DOWNLOAD", fg_color="#2FA572", hover_color="#207651",
            font=ctk.CTkFont(weight="bold"), command=self.start_download
        )
        self.download_btn.grid(row=5, column=0, columnspan=2, padx=15, pady=15, sticky="we")

        # Status Display label at bottom
        self.status_label = ctk.CTkLabel(self, text="Ready.", text_color="#1F6AA5", font=ctk.CTkFont(weight="bold"))
        self.status_label.pack(pady=10)

    def pick_folder(self):
        folder_selected = fd.askdirectory(initialdir=self.selected_output_dir)
        if folder_selected:
            self.selected_output_dir = folder_selected
            self.active_path_label.configure(text=folder_selected)

    def update_status(self, message):
        """Thread-safe way to update the status label from backend."""
        self.after(0, lambda: self.status_label.configure(text=message))

    def _run_backend_task(self, url, output_dir, resolution, transcripts):
        """Background thread target."""
        try:
            backend.download_youtube_video(
                url=url,
                output_dir=output_dir,
                resolution=resolution,
                download_transcripts=transcripts,
                progress_callback=self.update_status
            )
        finally:
            self.after(0, lambda: self.download_btn.configure(state="normal", text="START DOWNLOAD"))
            # Leave the "All Tasks Completed" or Error message as is.

    def start_download(self):
        url = self.url_entry.get().strip()
        if not url:
            self.update_status("Error: Please enter a valid YouTube URL.")
            return

        resolution = self.res_optionmenu.get()
        transcripts = (self.transcript_switch_var.get() == "on")
        output_dir = self.selected_output_dir

        self.download_btn.configure(state="disabled", text="PROCESSING...")
        self.update_status("Starting background process...")

        # Run logic in a thread to keep GUI responsive
        threading.Thread(
            target=self._run_backend_task,
            args=(url, output_dir, resolution, transcripts),
            daemon=True
        ).start()

if __name__ == "__main__":
    app = YoutubeDownloaderApp()
    app.mainloop()
