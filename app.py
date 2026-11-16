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

@app.route("/api/process", methods=["POST"])
def api_process():
    data = request.get_json() or {}
    file_id = data.get("file_id")
    
    if not file_id or file_id not in UPLOADED_FILES:
        return jsonify({"error": "Invalid or missing file_id"}), 400
    
    file_info = UPLOADED_FILES[file_id]
    input_path = file_info["path"]
    
    # Config parameters with 60 seconds (1 minute) default!
    segment_len = float(data.get("segment_len", 60.0))
    mode = data.get("mode", "fast")  # 'fast', 'portrait_blur', 'portrait_crop', 'portrait_fit'
    overlap = float(data.get("overlap", 0.0))
    prefix = data.get("prefix", "Reel").strip() or "Reel"
    
    task_id = str(uuid.uuid4())
    
    # Launch background thread
    worker = threading.Thread(
        target=cutter.process_video_task,
        args=(task_id, input_path, str(OUTPUT_DIR), segment_len, mode, overlap, prefix),
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
