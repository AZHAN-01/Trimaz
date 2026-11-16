import os
import uuid
import re
import urllib.request
from pathlib import Path
import yt_dlp
import cutter

def is_valid_url(url: str) -> bool:
    """Check if string is a valid HTTP/HTTPS URL."""
    url_pattern = re.compile(
        r'^(https?:\/\/)?'  # http:// or https://
        r'([a-zA-Z0-9_-]+\.)+[a-zA-Z]{2,}'  # domain
        r'(:\d+)?'  # optional port
        r'(\/.*)?$',  # optional path
        re.IGNORECASE
    )
    return bool(url_pattern.match(url.strip()))

def download_video_from_url(url: str, upload_dir: str, progress_callback=None):
    """
    Download video from YouTube, Instagram, TikTok, Facebook, Twitter/X,
    Reddit, Vimeo, or direct video URL.
    Returns metadata dict compatible with Trimaz's upload workflow.
    """
    url = url.strip()
    if not is_valid_url(url):
        raise ValueError("Invalid URL format. Please provide a valid web link.")
    
    file_id = str(uuid.uuid4())[:12]
    upload_path = Path(upload_dir)
    upload_path.mkdir(parents=True, exist_ok=True)
    
    ffmpeg_exe = cutter.get_ffmpeg_path()
    
    out_template = str(upload_path / f"{file_id}_%(title).60s.%(ext)s")
    
    downloaded_filepath = None
    
    def ydl_hook(d):
        nonlocal downloaded_filepath
        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            downloaded = d.get('downloaded_bytes') or 0
            speed = d.get('speed') or 0
            eta = d.get('eta') or 0
            percent = (downloaded / total * 100) if total > 0 else 0
            
            if progress_callback:
                progress_callback({
                    'status': 'downloading',
                    'percent': round(percent, 1),
                    'downloaded': downloaded,
                    'total': total,
                    'speed': speed,
                    'eta': eta,
                    'message': f"Downloading: {round(percent, 1)}% ({round(speed/1024/1024, 1) if speed else 0} MB/s)"
                })
        elif d['status'] == 'finished':
            downloaded_filepath = d.get('filename')
            if progress_callback:
                progress_callback({
                    'status': 'finished',
                    'percent': 100,
                    'message': "Processing downloaded video..."
                })

    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': out_template,
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'progress_hooks': [ydl_hook],
        'ffmpeg_location': ffmpeg_exe,
        'merge_output_format': 'mp4',
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            
            # Resolve actual downloaded filename
            if not downloaded_filepath or not os.path.exists(downloaded_filepath):
                # Check directory for matching prefix
                matching = list(upload_path.glob(f"{file_id}_*"))
                if matching:
                    downloaded_filepath = str(matching[0])
                else:
                    # Try ydl.prepare_filename
                    expected = ydl.prepare_filename(info)
                    if os.path.exists(expected):
                        downloaded_filepath = expected
                    else:
                        base = Path(expected).stem
                        matches = list(upload_path.glob(f"{base}*"))
                        if matches:
                            downloaded_filepath = str(matches[0])
                        else:
                            raise FileNotFoundError("Could not find downloaded file.")

        # Ensure it has .mp4 extension or compatible
        downloaded_path = Path(downloaded_filepath)
        filename = downloaded_path.name
        
        # Extract video metadata using OpenCV
        metadata = cutter.get_video_metadata(str(downloaded_path))
        
        # Generate video preview thumbnail
        preview_thumb_name = f"preview_{file_id}.jpg"
        preview_thumb_path = upload_path / preview_thumb_name
        cutter.generate_thumbnail(str(downloaded_path), str(preview_thumb_path), at_second=min(2.0, metadata["duration"] / 2))
        
        return {
            "file_id": file_id,
            "filename": filename,
            "path": str(downloaded_path),
            "thumb_path": str(preview_thumb_path),
            "thumb_name": preview_thumb_name,
            "metadata": metadata,
            "thumb_url": f"/api/upload-thumb/{preview_thumb_name}"
        }

    except Exception as e:
        # Cleanup any partially downloaded files
        for f in upload_path.glob(f"{file_id}*"):
            try:
                f.unlink()
            except Exception:
                pass
        raise e
