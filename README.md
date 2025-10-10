# ResolveReady-Downloader: Your YouTube-to-Resolve Workflow Killer

If you've spent any time trying to get a high-quality YouTube video into DaVinci Resolve, you already know the pain. It’s usually a multi-step nightmare: download the file, realize Resolve *hates* the container/codec combination, fire up HandBrake, wait for the conversion, and then finally trash the original huge file.

Honestly, I got tired of it. So, I built this simple application to do all of that with a single link paste. It handles the download, the **NVENC-accelerated conversion**, and the cleanup automatically, leaving you with a clean, ready-to-edit MP4 file right in a dedicated folder. It’s so much smoother!

## ✨ Features That Make Editing Easier

*   **One-Paste Automation:** Takes a YouTube URL, downloads the best quality available (video and audio), and immediately starts the conversion.
*   **Truly Portable:** **All HandBrake files and the preset are bundled inside the EXE.** You only need one other dependency (FFmpeg) externally.
*   **Resolve-Optimized Conversion:** Uses a built-in HandBrake preset to ensure the output file is one that DaVinci Resolve will happily chew through without any fuss.
*   **Hardware Acceleration:** It leverages the speed of your NVIDIA card for lightning-fast encoding.
*   **Automatic Cleanup:** After a successful conversion, it responsibly deletes the original, massive downloaded file, saving you disk space.

***

### 🛑 CRITICAL WARNING: NVIDIA GPU REQUIRED

Before you download anything, let's be absolutely clear about one thing: **This tool is built for NVIDIA users.**

The custom HandBrake preset that's built-in is specifically configured to leverage **NVENC** (NVIDIA's hardware encoder) for maximum speed and file quality. I only own an NVIDIA card, so that's what I optimized for.

*   **If you have an NVIDIA GPU**, everything should work flawlessly.
*   **If you have an AMD or Intel GPU**, the conversion will fail unless you build your own executable with a modified preset. I can't provide those alternative presets, sorry!

***

## 🚀 Setup & Installation (Just Two Files!)

This workflow is now incredibly simple. You only need to place two items in the same folder.

1.  **Download:** Grab the latest `ResolveReady-Downloader.exe` from the [Releases page].
2.  **Get FFmpeg:** Download the `ffmpeg.exe` executable. You can usually find a static build from the official FFmpeg site or a trusted mirror.
3.  **Place Together:** Put **both files** in the exact same folder on your machine:

    *   `ResolveReady-Downloader.exe` (The main application, which contains HandBrakeCLI and the preset)
    *   `ffmpeg.exe` (Required by the downloader to merge the high-quality video and audio streams)

## 💡 How to Use It

1.  Double-click `ResolveReady-Downloader.exe` to run the application. A console window will pop up.
2.  The prompt will ask you for a link. Copy your full YouTube URL (e.g., `https://www.youtube.com/watch?v=...`) and paste it into the window.
3.  Hit `Enter`.
4.  The application will use `ffmpeg.exe` to finalize the high-quality download, and then immediately hand the file off to the built-in HandBrake, showing the progress bar updating in real time:
    ```
    Encoding: task 1 of 1, 84.03 % (10.97 fps, avg 15.00 fps, ETA 00h00m01s)
    ```
5.  When everything's done, the original downloaded file is deleted, and your new, clean, Resolve-friendly video is saved in a subfolder called **`Handbraked`** right next to the executable.
6.  Type `exit` or `quit` when you're done.

## ⚙️ Customizing the Built-in Preset

The NVENC preset is currently baked right into the executable, which is what makes the distribution so clean. If you want to change the encoding settings (maybe you want H.265 instead of H.264, or a different quality level), you will need to:

1.  Create your new `resolve_preset.json` file via HandBrake GUI.
2.  Update the source code with your new preset.
3.  **Re-build the executable** using PyInstaller (see the development instructions below) to bundle your new preset.

This keeps the end-user experience simple, but gives developers the flexibility they need.
