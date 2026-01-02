# SunoSync V2

**Your World, Your Music. Seamlessly Synced.**

SunoSync V2 is the ultimate desktop manager for your Suno AI music generation. It combines a powerful bulk downloader, a feature-rich music library, and a built-in audio player into one seamless application.

![SunoSync Splash](resources/splash.png)

**Buy the exe or compile yourself below for free:**

- https://ko-fi.com/s/374c24251c - PayPal accepted here  [$3 or pay what you want]
- https://justinmurray99.gumroad.com/l/rrxty  [$3 or pay what you want]

**Discord Support and Community:** https://discord.gg/kZSc8sKUZR

## 🌟 Key Features

### 📥 Smart Downloader
*   **Bulk Downloading:** Download all your Suno songs in one click.
*   **Smart Sync:** Only downloads new songs, skipping what you already have.
*   **Format Choice:** Choose between **MP3** (smaller size) or **WAV** (lossless quality).
*   **Organization:** Automatically organizes downloads into folders by **Year-Month** (e.g., `2025-11`).
*   **Metadata Embedding:** Automatically embeds Title, Artist, and **Lyrics** directly into the audio file tags (MP3 and WAV).
*   **Lyrics Files:** Option to save lyrics as separate `.txt` files.
*   **Smart Resume:** Intelligently stops scanning after consecutive pages with no new songs.
*   **Workspace & Playlist Support:** Browse and download from your Suno workspaces and playlists.
*   **Advanced Filtering:** Filter by liked, trashed, stems, public/private, and more.
*   **Preload Mode:** Preview songs before downloading and uncheck unwanted tracks.

### 📚 Music Library
*   **Visual Browser:** Browse your entire collection in a clean, sortable list.
*   **Search:** Instantly filter songs by Title or Artist.
*   **Sorting:** Sort by Date, Duration, Size, Title, or Artist.
*   **Tag System:** Organize songs with Like 👍, Star ⭐, and Trash 🗑️ tags with filtering support.
*   **Context Menu:** Right-click to Play, View/Edit Lyrics, Open Folder, or Delete songs.
*   **Auto-Refresh:** Library automatically updates when new downloads finish.

### 🎵 Built-in Player
*   **Seamless Playback:** Play songs directly within the app without opening external players.
*   **Controls:** Play/Pause, Stop, Seek Bar, and Volume Control.
*   **Playback Modes:** Shuffle, Repeat All, and Repeat One modes.
*   **Tag Controls:** Quick-access Like, Star, and Trash buttons with automatic library synchronization.

### ✍️ Lyrics Editor
*   **View & Edit:** Right-click any song to view the embedded lyrics.
*   **Multiple Sources:** Reads lyrics from both embedded metadata and `.txt` files.
*   **Edit Mode:** Fix typos or add your own verses directly in the app.
*   **Dual Save:** Saves lyrics to both `.txt` file and audio file metadata.
*   **Verification:** Automatically verifies that your changes are saved to the file on disk.

### 🎨 Modern UI & Polish
*   **Dark Mode:** Sleek, modern dark interface that's easy on the eyes.
*   **Cross-Platform:** Works on Windows, macOS, and Linux (with full font/icon support).
*   **Customizable Notifications:** Option to disable Windows alert notification sounds.
*   **Window State:** Remembers your window size and position between sessions.
*   **Debug Tools:** Built-in debug log viewer for troubleshooting.

## 🚀 Getting Started

### Windows
1.  **Download:** Get the latest `SunoSyncV2.exe` or compile from source (see below).
2.  **Install VLC:** Ensure you have [VLC Media Player](https://www.videolan.org/) installed (required for audio playback).
3.  **Run:** Double-click `SunoSyncV2.exe`.
4.  **Get Token:**
    *   Click "Get Token" in the Downloader tab.
    *   Log in to Suno.com.
    *   Open Developer Tools (F12) -> Application -> Cookies.
    *   Copy the value of the `__client` cookie.
5.  **Download:** Paste your token and click **Start Download** or **Preload** to preview first.

### Linux (Ubuntu/Debian/Arch)
1.  **Install dependencies:**
    ```bash
    # Debian/Ubuntu
    sudo apt-get install python3-tk python3-pil python3-pip vlc
    
    # Arch Linux
    sudo pacman -S python-tk python-pillow python-pip vlc ttf-dejavu
    ```
2.  **Clone and setup:**
    ```bash
    git clone https://github.com/sunsetsacoustic/SunoSync.git
    cd SunoSync
    python -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```
3.  **Run:**
    ```bash
    python main.py
    ```
4.  **Get Token & Download:** Same as Windows steps 4-5.

## 🔒 Security & VirusTotal Transparency

We believe in 100% transparency. Because SunoSync is an indie tool built with Python (and not a digitally signed corporation app), a few generic antivirus filters may flag it as "unknown."

**The Reality:** ✅ 69/72 Security Vendors found NO issues (Clean) ⚠️ 3/72 flagged as "False Positive" (Generic/Heuristic)

These flags occur because the app is "unsigned" (common for indie devs). You can verify the file yourself below:

[➢ Click here to view the live VirusTotal Report](https://www.virustotal.com/gui/file/691ec3ad17ff18171b2499ed6c460db0fb1fb6015223eaa37c0cf06cdb92fc30?nocache=1)

## ☕ Support

Created by **@InternetThot**

If you love SunoSync, consider buying me a coffee to support future updates!
👉 [buymeacoffee.com/audioalchemy](https://buymeacoffee.com/audioalchemy)

---
*SunoSync is an unofficial tool and is not affiliated with Suno AI.*

## 🛠️ Building from Source

### Prerequisites
*   **Python 3.10+**
*   **Git**
*   **VLC Media Player** (Required for audio playback)

### Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/sunsetsacoustic/SunoSync.git
    cd SunoSync
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Run the application:**
    ```bash
    python main.py
    ```

### Compiling to Executable

To build the standalone `.exe` file:

1.  **Install PyInstaller:**
    ```bash
    pip install pyinstaller
    ```

2.  **Build using the spec file:**
    ```bash
    pyinstaller SunoApi.spec
    ```

3.  The executable will be in the `dist/` folder.
