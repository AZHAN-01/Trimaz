import os
import uuid
import re
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

def format_size_bytes(size_bytes: float) -> str:
    """Format bytes to human readable string (KB, MB, GB)."""
    if not size_bytes or size_bytes <= 0:
        return "Size estimate unavailable"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"

def probe_video_info(url: str):
    """
    Inspects video URL without downloading.
    Extracts title, duration, thumbnail, and all available video qualities with estimated sizes.
    """
    url = url.strip()
    if not is_valid_url(url):
        raise ValueError("Invalid URL format. Please provide a valid web link.")

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'noplaylist': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['ios', 'android', 'web']
            }
        }
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        
    title = info.get('title') or "Untitled Video"
    duration = info.get('duration') or 0
    thumbnail = info.get('thumbnail') or ""
    uploader = info.get('uploader') or info.get('channel') or "Web Video"
    
    # Format duration
    duration_formatted = cutter.format_timestamp(duration)
    
    # Analyze formats to get audio bitrate and video resolutions
    formats = info.get('formats') or []
    
    # Find best audio size / bitrate to combine with video-only streams
    best_audio_bytes = 0
    best_audio_rate = 128  # kbps default fallback
    for f in formats:
        if f.get('vcodec') == 'none' and f.get('acodec') != 'none':
            a_bytes = f.get('filesize') or f.get('filesize_approx') or 0
            if a_bytes > best_audio_bytes:
                best_audio_bytes = a_bytes
            abr = f.get('abr') or 0
            if abr > best_audio_rate:
                best_audio_rate = abr
                
    if best_audio_bytes == 0 and duration > 0:
        best_audio_bytes = int((best_audio_rate * 1000 / 8) * duration)

    # Standard target resolutions to offer
    target_heights = [1080, 720, 480, 360]
    height_labels = {
        1080: "1080p Full HD",
        720: "720p HD (Recommended)",
        480: "480p Standard",
        360: "360p Data Saver"
    }
    
    # Track available heights from streams
    found_heights = {}
    
    for f in formats:
        h = f.get('height')
        if not h:
            continue
        
        # Calculate file size for this stream
        stream_bytes = f.get('filesize') or f.get('filesize_approx') or 0
        if stream_bytes == 0 and duration > 0:
            tbr = f.get('tbr') or f.get('vbr') or 0
            if tbr > 0:
                stream_bytes = int((tbr * 1000 / 8) * duration)
        
        # If this is video-only, add estimated audio stream
        if f.get('acodec') == 'none' and stream_bytes > 0:
            total_bytes = stream_bytes + best_audio_bytes
        else:
            total_bytes = stream_bytes
            
        # Match to closest standard height
        for target in target_heights:
            if h >= target * 0.9 and h <= target * 1.15:
                if target not in found_heights or total_bytes > found_heights[target]['size_bytes']:
                    found_heights[target] = {
                        'height': target,
                        'size_bytes': total_bytes,
                        'actual_height': h
                    }
                break

    # If no standard heights were matched (e.g. Non-YouTube link, direct MP4 link)
    if not found_heights:
        direct_size = info.get('filesize') or info.get('filesize_approx') or 0
        found_heights[720] = {
            'height': 720,
            'size_bytes': direct_size,
            'actual_height': info.get('height') or 720
        }

    qualities = []
    # Build list of options sorted from highest to lowest quality
    for h in sorted(found_heights.keys(), reverse=True):
        entry = found_heights[h]
        size_b = entry['size_bytes']
        
        label = height_labels.get(h, f"{h}p")
        format_spec = f"bestvideo[height<={h}][ext=mp4]+bestaudio[ext=m4a]/best[height<={h}][ext=mp4]/best[height<={h}]/best"
        
        qualities.append({
            "quality_id": str(h),
            "height": h,
            "label": label,
            "size_bytes": size_b,
            "size_formatted": format_size_bytes(size_b),
            "format_spec": format_spec,
            "recommended": (h == 720) or (len(found_heights) == 1)
        })

    # If 720 is not present, mark the first one as recommended
    if qualities and not any(q.get('recommended') for q in qualities):
        qualities[0]['recommended'] = True

    return {
        "title": title,
        "duration": duration,
        "duration_formatted": duration_formatted,
        "thumbnail": thumbnail,
        "uploader": uploader,
        "url": url,
        "qualities": qualities
    }

def download_video_from_url(url: str, upload_dir: str, format_spec: str = None, progress_callback=None):
    """
    Download video from YouTube, Instagram, TikTok, Facebook, Twitter/X,
    Reddit, Vimeo, or direct video URL with the specified quality format.
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
                    'message': f"Downloading video: {round(percent, 1)}% ({round(speed/1024/1024, 1) if speed else 0} MB/s)"
                })
        elif d['status'] == 'finished':
            downloaded_filepath = d.get('filename')
            if progress_callback:
                progress_callback({
                    'status': 'finished',
                    'percent': 100,
                    'message': "Processing downloaded stream into cutter..."
                })

    chosen_format = format_spec or 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'

    ydl_opts = {
        'format': chosen_format,
        'outtmpl': out_template,
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'progress_hooks': [ydl_hook],
        'ffmpeg_location': ffmpeg_exe,
        'merge_output_format': 'mp4',
        'extractor_args': {
            'youtube': {
                'player_client': ['ios', 'android', 'web']
            }
        }
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            
            # Resolve actual downloaded filename
            if not downloaded_filepath or not os.path.exists(downloaded_filepath):
                matching = list(upload_path.glob(f"{file_id}_*"))
                if matching:
                    downloaded_filepath = str(matching[0])
                else:
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
        for f in upload_path.glob(f"{file_id}*"):
            try:
                f.unlink()
            except Exception:
                pass
        raise e
