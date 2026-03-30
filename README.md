# YouTube Resolve-Ready Downloader

A sleek, intuitive desktop application designed for video editors. It allows you to effortlessly download YouTube videos in up to 4K resolution alongside their English transcripts, and automatically transcodes them into a high-performance, editing-friendly format optimized for DaVinci Resolve.

Built with Python, `yt-dlp`, and HandBrakeCLI, wrapped in a beautiful modern GUI using **CustomTkinter**.

## ✨ Features
- **Clean and Modern Interface:** Fully dark-mode responsive UI that stays smooth and snappy by performing heavy downloads and transcoding in the background.
- **Selectable Resolutions:** Easily pick between 1080p, 1440p (2K), and 2160p (4K) source qualities.
- **Automatic Transcripts:** A convenient toggle to download available hand-crafted or auto-generated English `.srt`/`.vtt` subtitle packages right next to your videos.
- **Resolve-Ready Conversion:** Automatically runs downloaded footage through HandBrake to conform it to a professional standard (via a custom `resolve_preset.json`), bypassing compatibility errors and VFR (variable framerate) desyncs inside DaVinci Resolve.
- **Custom Destinations:** Full freedom to pick exactly where both your subtitles and fully processed `.mp4` video files are saved.

## 📁 Architecture
- `gui_app.py`: The frontend graphical application. Run this script to launch the interface.
- `downloader.py`: The core backend logic handling `yt-dlp` interaction and HandBrake command-line dispatching.
- `resolve_preset.json`: A custom HandBrake encoding preset tailored for Resolve workloads. 
- `HandBrakeCLI.exe` & `ffmpeg.exe`: External command-line utilities used for high-tier demuxing, merging, and hardware-accelerated transcoding.

## 🚀 Getting Started

### Using the Portable Application (Recommended)
If you generated or downloaded the standalone application folder, all dependencies are fully packaged inside!
1. Navigate to your `dist/ResolveReadyDownloader` folder.
2. Double click `ResolveReadyDownloader.exe`.

### Running from Source
If modifying the codebase or running directly using Python:
1. Ensure you have Python 3.10+ installed.
2. Clone or download this project folder.
3. Install the required dependencies:
   ```bash
   pip install yt-dlp customtkinter
   ```
4. Verify you have `HandBrakeCLI.exe` and `ffmpeg.exe` in the root folder alongside `resolve_preset.json`.
5. Launch the application:
   ```bash
   python gui_app.py
   ```

## 🛠️ Building an Executable
If you would like to rebuild the project into a portable `.exe` application directory using PyInstaller, run the following command in the project root:

```powershell
pyinstaller --noconfirm --onedir --windowed --add-data "HandBrakeCLI.exe;." --add-data "resolve_preset.json;." --add-data "ffmpeg.exe;." --collect-all customtkinter --name "ResolveReadyDownloader" "gui_app.py"
```
Your compiled application will spit out safely into the generated `dist/` directory.
