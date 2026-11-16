import os
import sys
import uuid
import time
import shutil
import subprocess
import threading
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file, send_from_directory, Response

import cutter
import downloader

BASE_DIR = Path(__file__).parent.resolve()
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__, template_folder=str(BASE_DIR / "templates"), static_folder=str(BASE_DIR / "static"))

# Support up to 10 GB video uploads
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024 * 1024  
app.config['UPLOAD_FOLDER'] = str(UPLOAD_DIR)

# Store uploaded video metadata
UPLOADED_FILES = {}

def cleanup_stale_uploads():
    """Purge leftover upload files in UPLOAD_DIR on startup."""
    try:
        for item in UPLOAD_DIR.iterdir():
            if item.name == ".gitkeep":
                continue
            try:
                if item.is_file():
                    item.unlink()
            except Exception:
                pass
    except Exception:
        pass

def janitor_loop():
    """Background thread that deletes abandoned upload files older than 10 minutes."""
    while True:
        time.sleep(120)
        now = time.time()
        try:
            for item in UPLOAD_DIR.iterdir():
                if item.name == ".gitkeep":
                    continue
                try:
                    if item.is_file() and (now - item.stat().st_mtime > 600):
                        item.unlink()
                except Exception:
                    pass
        except Exception:
            pass

# Run startup cleanup & background janitor
cleanup_stale_uploads()
threading.Thread(target=janitor_loop, daemon=True).start()

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/system")
def api_system():
    ffmpeg_path = cutter.get_ffmpeg_path()
    return jsonify({
        "ffmpeg_path": ffmpeg_path,
        "ffmpeg_available": os.path.exists(ffmpeg_path) or shutil.which(ffmpeg_path) is not None,
        "upload_dir": str(UPLOAD_DIR),
        "output_dir": str(OUTPUT_DIR)
    })

# Download tasks store for link downloads
DOWNLOAD_TASKS = {}
DOWNLOAD_LOCK = threading.Lock()

@app.route("/api/probe-url", methods=["POST"])
def api_probe_url():
    """Inspect a video link without downloading to return qualities and estimated sizes."""
    data = request.get_json(silent=True) or {}
    url = data.get("url", "").strip()
    if not url or not downloader.is_valid_url(url):
        return jsonify({"error": "Please enter a valid video link"}), 400

    try:
        info = downloader.probe_video_info(url)
        return jsonify({"success": True, "info": info})
    except Exception as e:
        return jsonify({"error": f"Could not inspect video link: {str(e)}"}), 500

@app.route("/api/fetch-url", methods=["POST"])
def api_fetch_url():
    data = request.get_json(silent=True) or {}
    url = data.get("url", "").strip()
    format_spec = data.get("format_spec")
    if not url:
        return jsonify({"error": "Please enter a valid video link"}), 400
    
    if not downloader.is_valid_url(url):
        return jsonify({"error": "Invalid URL format. Please enter a valid web link."}), 400

    download_id = str(uuid.uuid4())[:12]
    with DOWNLOAD_LOCK:
        DOWNLOAD_TASKS[download_id] = {
            "status": "starting",
            "percent": 0,
            "message": "Connecting to video server...",
            "result": None,
            "error": None
        }

    def run_download():
        def progress(info):
            with DOWNLOAD_LOCK:
                if download_id in DOWNLOAD_TASKS:
                    DOWNLOAD_TASKS[download_id].update(info)

        try:
            result = downloader.download_video_from_url(url, str(UPLOAD_DIR), format_spec=format_spec, progress_callback=progress)
            file_id = result["file_id"]
            UPLOADED_FILES[file_id] = result
            with DOWNLOAD_LOCK:
                DOWNLOAD_TASKS[download_id] = {
                    "status": "completed",
                    "percent": 100,
                    "message": "Video downloaded successfully!",
                    "result": {
                        "success": True,
                        "file_id": file_id,
                        "filename": result["filename"],
                        "metadata": result["metadata"],
                        "thumb_url": result["thumb_url"]
                    }
                }
        except Exception as e:
            with DOWNLOAD_LOCK:
                DOWNLOAD_TASKS[download_id] = {
                    "status": "error",
                    "percent": 0,
                    "error": str(e),
                    "message": f"Failed to download video: {str(e)}"
                }

    threading.Thread(target=run_download, daemon=True).start()
    return jsonify({"success": True, "download_id": download_id})

@app.route("/api/fetch-status/<download_id>")
def api_fetch_status(download_id):
    with DOWNLOAD_LOCK:
        task = DOWNLOAD_TASKS.get(download_id)
        if not task:
            return jsonify({"error": "Download task not found"}), 404
        return jsonify(task)

@app.route("/api/upload", methods=["POST"])
def api_upload():
    if "video" not in request.files:
        return jsonify({"error": "No video file provided"}), 400
    
    file = request.files["video"]
    if file.filename == "":
        return jsonify({"error": "Empty filename"}), 400
    
    # Generate clean unique ID
    file_id = str(uuid.uuid4())[:12]
    original_name = file.filename
    clean_name = f"{file_id}_{Path(original_name).name}"
    save_path = UPLOAD_DIR / clean_name
    
    file.save(str(save_path))
    
    try:
        metadata = cutter.get_video_metadata(str(save_path))
        
        # Generate video preview thumbnail
        preview_thumb_name = f"preview_{file_id}.jpg"
        preview_thumb_path = UPLOAD_DIR / preview_thumb_name
        cutter.generate_thumbnail(str(save_path), str(preview_thumb_path), at_second=min(2.0, metadata["duration"] / 2))
        
        UPLOADED_FILES[file_id] = {
            "file_id": file_id,
            "filename": original_name,
            "path": str(save_path),
            "thumb_path": str(preview_thumb_path),
            "thumb_name": preview_thumb_name,
            "metadata": metadata
        }
        
        return jsonify({
            "success": True,
            "file_id": file_id,
            "filename": original_name,
            "metadata": metadata,
            "thumb_url": f"/api/upload-thumb/{preview_thumb_name}"
        })
    except Exception as e:
        if save_path.exists():
            save_path.unlink()
        return jsonify({"error": f"Failed to analyze video: {str(e)}"}), 500

@app.route("/api/upload-thumb/<filename>")
def api_upload_thumb(filename):
    return send_from_directory(str(UPLOAD_DIR), filename)

@app.route("/api/discard", methods=["POST"])
def api_discard():
    """Immediately remove uploaded raw video and preview thumbnail."""
    data = request.get_json(silent=True) or {}
    file_id = data.get("file_id")
    if file_id and file_id in UPLOADED_FILES:
        info = UPLOADED_FILES.pop(file_id, {})
        for key in ["path", "thumb_path"]:
            p = Path(info.get(key, ""))
            if p.exists():
                try:
                    p.unlink()
                except Exception:
                    pass
    return jsonify({"success": True})

@app.route("/api/process", methods=["POST"])
def api_process():
    data = request.get_json() or {}
    file_id = data.get("file_id")
    
    if not file_id or file_id not in UPLOADED_FILES:
        return jsonify({"error": "Invalid or missing file_id"}), 400
    
    file_info = UPLOADED_FILES.pop(file_id)
    input_path = file_info["path"]
    thumb_path = file_info.get("thumb_path")
    
    # Config parameters with 60 seconds (1 minute) default!
    segment_len = float(data.get("segment_len", 60.0))
    mode = data.get("mode", "fast")  # 'fast', 'portrait_blur', 'portrait_crop', 'portrait_fit'
    overlap = float(data.get("overlap", 0.0))
    prefix = data.get("prefix", "Reel").strip() or "Reel"
    
    task_id = str(uuid.uuid4())
    
    # Launch background thread with cleanup_input=True
    worker = threading.Thread(
        target=cutter.process_video_task,
        args=(task_id, input_path, str(OUTPUT_DIR), segment_len, mode, overlap, prefix, True, thumb_path),
        daemon=True
    )
    worker.start()
    
    return jsonify({
        "success": True,
        "task_id": task_id,
        "message": "Processing started"
    })

@app.route("/api/status/<task_id>")
def api_status(task_id):
    with cutter.TASKS_LOCK:
        task = cutter.TASKS.get(task_id)
        if not task:
            return jsonify({"error": "Task not found"}), 404
        return jsonify(task)

@app.route("/api/thumb/<task_id>/<filename>")
def api_thumb(task_id, filename):
    folder = OUTPUT_DIR / task_id
    return send_from_directory(str(folder), filename)

@app.route("/api/stream/<task_id>/<filename>")
def api_stream(task_id, filename):
    file_path = OUTPUT_DIR / task_id / filename
    if not file_path.exists():
        return "File not found", 404
    return send_file(str(file_path), mimetype="video/mp4")

@app.route("/api/download/<task_id>/<filename>")
def api_download(task_id, filename):
    file_path = OUTPUT_DIR / task_id / filename
    if not file_path.exists():
        return "File not found", 404
    return send_file(str(file_path), as_attachment=True, download_name=filename)

@app.route("/api/download-all/<task_id>")
def api_download_all(task_id):
    with cutter.TASKS_LOCK:
        task = cutter.TASKS.get(task_id)
        if not task or not task.get("zip_file"):
            return jsonify({"error": "ZIP not ready"}), 400
        zip_name = task["zip_file"]
        
    zip_path = OUTPUT_DIR / task_id / zip_name
    if not zip_path.exists():
        return jsonify({"error": "ZIP file not found on disk"}), 404
    
    return send_file(str(zip_path), as_attachment=True, download_name=zip_name)

@app.route("/api/open-folder", methods=["POST"])
def api_open_folder():
    data = request.get_json() or {}
    task_id = data.get("task_id")
    target_dir = OUTPUT_DIR / task_id if task_id else OUTPUT_DIR
    
    if not target_dir.exists():
        target_dir = OUTPUT_DIR
    
    try:
        if sys.platform == "win32":
            os.startfile(str(target_dir))
        else:
            subprocess.Popen(["xdg-open", str(target_dir)])
        return jsonify({"success": True, "path": str(target_dir)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    print(f"==================================================")
    print(f"🎬 Trimaz Server Starting on http://127.0.0.1:5000")
    print(f"==================================================")
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
