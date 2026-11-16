# 🎬 Trimaz — 1-Minute Reel Generator

> **Cut large videos into 1-minute reels, shorts & TikToks automatically by just uploading your video.**

Trimaz is a modern video processing software designed to take large videos (podcasts, lectures, gaming sessions, webinars, vlogs) and automatically slice them into bite-sized 1-minute reels, shorts, or clips ready for Instagram Reels, YouTube Shorts, and TikTok.

---

## ⚡ Key Features

- **Paste Video Link**: Just paste a link from **YouTube, Instagram Reels, TikTok, Twitter/X, Facebook**, or direct MP4 link! Trimaz fetches and cuts it automatically.
- **Upload & Slice**: Or drag and drop any local video file (MP4, MKV, MOV, AVI, WEBM, FLV, TS up to 10 GB).
- **Zero Disk Waste**: Uploaded or downloaded source videos are automatically deleted immediately after slicing is completed!
- **Default 1-Minute Reels**: Automatically splits the entire video into 60-second segments.
- **Customizable Duration**: Easily choose presets like 30s, 60s (1 min), 90s, or any custom seconds.
- **4 Cutting Modes**:
  - ⚡ **Original Aspect Ratio (Lossless Stream Copy)**: 100x real-time speed (~3-5s for an entire 1-hour video!), zero quality loss, preserves original audio.
  - 📱 **9:16 Vertical Reel (Blur Background)**: Converts landscape videos to 9:16 portrait with a stylish blurred background (ideal for TikTok & Reels).
  - 🔍 **9:16 Center Crop**: Crops directly to the center 9:16 frame.
  - ⬛ **9:16 Letterbox (Fit)**: Fits whole video inside 9:16 with clean borders.
- **Smart Speech Overlap**: Optional 1s-3s overlap between reels so sentences are not cut off abruptly.
- **Interactive In-Browser Player**: Watch and preview any generated reel right in the browser before downloading.
- **One-Click Download**:
  - Download individual reels.
  - **Download All (ZIP)**: Download all reels bundled in a single ZIP archive.
  - **Open Output Folder**: Instantly opens the folder in Windows File Explorer.
- **Self-Contained & Fast**: Comes pre-packaged with local FFmpeg engine and OpenCV metadata extractor.

---

## 🚀 How to Run

### Option 1: Double-Click Launcher (Recommended)
Simply double-click **`run.bat`** in this folder!
It will:
1. Start the Trimaz server.
2. Automatically launch your default web browser to `http://localhost:5000`.

### Option 2: PowerShell
```powershell
.\start.ps1
```

### Option 3: Manual Terminal Command
```bash
python app.py
```
Then open [http://localhost:5000](http://localhost:5000) in your browser.

---

## 💻 Command Line Interface (CLI)

Prefer working from the terminal? Use `cli.py` to cut videos directly without opening a browser:

```powershell
# Cut a video from a YouTube, Instagram, or TikTok link into 1-min reels:
python cli.py "https://www.youtube.com/watch?v=..." --duration 60

# Cut a local video file into 1-minute (60s) reels:
python cli.py "my_large_video.mp4"

# Cut into 60s reels with 2-second overlap
python cli.py "podcast.mp4" --duration 60 --overlap 2

# Cut into 9:16 vertical reels with blurred ambient background
python cli.py "gaming.mp4" --duration 60 --mode portrait_blur

# Specify custom output directory and prefix
python cli.py "lecture.mp4" --duration 60 --output "C:\MyReels" --prefix "Short"
```

### CLI Arguments:
| Flag | Description | Default |
|---|---|---|
| `video` | Path to the video file to cut | *(Required)* |
| `-d`, `--duration` | Segment duration in seconds | `60.0` (1 min) |
| `-m`, `--mode` | `fast`, `portrait_blur`, `portrait_crop`, `portrait_fit` | `fast` |
| `-o`, `--output` | Destination output directory | `outputs` |
| `--overlap` | Overlap in seconds between reels | `0.0` |
| `-p`, `--prefix` | Filename prefix | `Reel` |

---

## 📁 Project Structure

```text
video.ai/
├── app.py                # Flask Web Server & REST API
├── cutter.py             # Core Video Slicing Engine (OpenCV + FFmpeg)
├── cli.py                # Command Line Tool
├── run.bat               # Windows 1-Click Launcher
├── start.ps1             # PowerShell Launcher
├── bin/
│   └── ffmpeg.exe        # Self-contained FFmpeg binary
├── templates/
│   └── index.html        # Modern Dark-Mode Web App
├── static/
│   ├── css/style.css     # Responsive Styling & Glassmorphism UI
│   └── js/app.js         # Client-side state, upload progress, polling
├── uploads/              # Temporary storage for uploaded videos
└── outputs/              # Generated reel clips and ZIP archives
```

---

## 🌐 Free Cloud Deployment (Why Netlify Doesn't Work & How to Deploy to Render)

### Why Netlify Shows "Page Not Found":
- **Netlify only hosts static frontend files** (HTML/CSS/JS). It looks for an `index.html` file in the root directory.
- **Trimaz is a full Python backend application** with FFmpeg video processing and OpenCV. Netlify cannot run Python web servers or execute FFmpeg binaries.
- Netlify functions also have a strict 10-second timeout and 512MB memory limit, which terminates video slicing immediately.

### Deploy to Render for Free (Recommended):
Render provides free web service hosting with Docker and FFmpeg support:

1. Go to **[https://dashboard.render.com](https://dashboard.render.com)**.
2. Click **New +** → **Web Service**.
3. Connect your GitHub repository: **`AZHAN-01/Trimaz`**.
4. Select **Docker** as the runtime (Render will automatically detect our `Dockerfile`).
5. Choose the **Free** plan.
6. Click **Deploy Web Service**!
   Render will build the Docker container with FFmpeg, start the server, and give you a free live URL (e.g. `https://trimaz.onrender.com`)!
