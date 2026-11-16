import os
import sys
import time
import math
import shutil
import zipfile
import subprocess
import threading
from pathlib import Path
import cv2

# Global task status store
TASKS = {}
TASKS_LOCK = threading.Lock()

def get_ffmpeg_path():
    """Detect the best available ffmpeg binary."""
    # 1. Local project bin
    local_bin = Path(__file__).parent / "bin" / "ffmpeg.exe"
    if local_bin.exists():
        return str(local_bin)
    
    # 2. Check PATH
    which_ffmpeg = shutil.which("ffmpeg")
    if which_ffmpeg:
        return which_ffmpeg
    
    # 3. Check BlueStacks installation
    bluestacks_path = Path("C:/Program Files/BlueStacks_nxt/ffmpeg.exe")
    if bluestacks_path.exists():
        return str(bluestacks_path)
    
    return "ffmpeg"

def format_timestamp(seconds: float) -> str:
    """Format seconds into HH:MM:SS string."""
    seconds = max(0, seconds)
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

def format_file_size(size_bytes: int) -> str:
    """Format bytes to human readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"

def get_video_metadata(filepath: str):
    """Extract metadata using OpenCV (fps, frame count, duration, resolution)."""
    cap = cv2.VideoCapture(filepath)
    if not cap.isOpened():
        raise ValueError(f"Could not open video file: {filepath}")
    
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    
    duration = 0.0
    if fps > 0 and frame_count > 0:
        duration = frame_count / fps
    else:
        # Fallback using cap position
        cap.set(cv2.CAP_PROP_POS_AVI_RATIO, 1)
        duration = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        
    cap.release()
    
    file_size = os.path.getsize(filepath)
    aspect_ratio = f"{width}:{height}"
    is_vertical = height > width
    
    return {
        "duration": round(duration, 2),
        "duration_formatted": format_timestamp(duration),
        "width": width,
        "height": height,
        "aspect_ratio": aspect_ratio,
        "is_vertical": is_vertical,
        "fps": round(fps, 2),
        "frame_count": int(frame_count),
        "file_size": file_size,
        "file_size_formatted": format_file_size(file_size)
    }

def generate_thumbnail(video_path: str, output_thumb_path: str, at_second: float = 1.0):
    """Generate a JPEG thumbnail using OpenCV at a given timestamp."""
    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return False
        
        cap.set(cv2.CAP_PROP_POS_MSEC, at_second * 1000.0)
        success, frame = cap.read()
        if not success:
            # Fallback to first frame
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            success, frame = cap.read()
        
        if success and frame is not None:
            # Resize thumbnail to max width 480px while maintaining aspect ratio
            h, w = frame.shape[:2]
            if w > 480:
                scale = 480.0 / w
                new_w, new_h = 480, int(h * scale)
                frame = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
            
            os.makedirs(os.path.dirname(output_thumb_path), exist_ok=True)
            cv2.imwrite(output_thumb_path, frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
            cap.release()
            return True
        cap.release()
    except Exception as e:
        print(f"Error generating thumbnail: {e}")
    return False

def calculate_segments(total_duration: float, segment_len: float = 60.0, overlap: float = 0.0):
    """
    Calculate start and end timestamps for each reel.
    Default segment_len is 60 seconds (1 minute).
    """
    segments = []
    if total_duration <= 0:
        return segments
    
    # If video is shorter than or equal to segment_len, produce 1 reel
    if total_duration <= segment_len:
        return [(0.0, total_duration)]
    
    current_start = 0.0
    step = max(1.0, segment_len - overlap)
    
    while current_start < total_duration:
        end = min(total_duration, current_start + segment_len)
        # Avoid tiny residual clips (< 4 seconds) at the end: merge into previous if very small
        remaining_after = total_duration - end
        if 0 < remaining_after < 4.0:
            end = total_duration
            
        segments.append((round(current_start, 2), round(end, 2)))
        
        if end >= total_duration:
            break
        current_start += step
        
    return segments

def cut_clip(ffmpeg_path: str, input_path: str, output_path: str, start: float, duration: float, mode: str = "fast"):
    """
    Cut a single clip using FFmpeg.
    mode:
      - 'fast': Lossless stream copy (-c copy). Instant, zero quality loss, keeps original audio.
      - 'portrait_blur': 9:16 vertical reel with blurred background.
      - 'portrait_crop': 9:16 vertical reel with center crop.
      - 'portrait_fit': 9:16 vertical reel with black letterboxing.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    if mode == "fast":
        # Ultra fast stream copy
        # Placing -ss before -i for fast seek, duration with -t
        cmd = [
            ffmpeg_path,
            "-y",
            "-ss", str(start),
            "-i", input_path,
            "-t", str(duration),
            "-c", "copy",
            "-avoid_negative_ts", "make_zero",
            "-map", "0",
            output_path
        ]
    elif mode == "portrait_blur":
        # 9:16 blurred background:
        # scale background to fill 1080x1920 with blur, scale foreground to fit, overlay
        filter_str = (
            "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=25:5[bg];"
            "[0:v]scale=1080:1920:force_original_aspect_ratio=decrease[fg];"
            "[bg][fg]overlay=(W-w)/2:(H-h)/2"
        )
        cmd = [
            ffmpeg_path,
            "-y",
            "-ss", str(start),
            "-i", input_path,
            "-t", str(duration),
            "-filter_complex", filter_str,
            "-vcodec", "h264_mf",
            "-c:a", "copy",
            output_path
        ]
    elif mode == "portrait_crop":
        # 9:16 center crop
        filter_str = "crop=ih*9/16:ih:(iw-ih*9/16)/2:0,scale=1080:1920"
        cmd = [
            ffmpeg_path,
            "-y",
            "-ss", str(start),
            "-i", input_path,
            "-t", str(duration),
            "-vf", filter_str,
            "-vcodec", "h264_mf",
            "-c:a", "copy",
            output_path
        ]
    elif mode == "portrait_fit":
        # 9:16 black padding / fit
        filter_str = "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black"
        cmd = [
            ffmpeg_path,
            "-y",
            "-ss", str(start),
            "-i", input_path,
            "-t", str(duration),
            "-vf", filter_str,
            "-vcodec", "h264_mf",
            "-c:a", "copy",
            output_path
        ]
    else:
        # Default to fast copy
        cmd = [
            ffmpeg_path,
            "-y",
            "-ss", str(start),
            "-i", input_path,
            "-t", str(duration),
            "-c", "copy",
            "-avoid_negative_ts", "make_zero",
            output_path
        ]
    
    # Run FFmpeg process
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        # If hardware encoder h264_mf failed (e.g. On certain machines), fallback to libopenh264 or fast copy
        if "h264_mf" in cmd:
            fallback_cmd = [arg if arg != "h264_mf" else "libopenh264" for arg in cmd]
            proc = subprocess.run(fallback_cmd, capture_output=True, text=True)
            if proc.returncode != 0:
                # If still fails, fallback to stream copy
                fallback_copy = [
                    ffmpeg_path, "-y", "-ss", str(start), "-i", input_path,
                    "-t", str(duration), "-c", "copy", "-avoid_negative_ts", "make_zero", output_path
                ]
                proc = subprocess.run(fallback_copy, capture_output=True, text=True)
                if proc.returncode != 0:
                    raise RuntimeError(f"FFmpeg cutting failed: {proc.stderr[:400]}")
        else:
            raise RuntimeError(f"FFmpeg error: {proc.stderr[:400]}")
    
    return True

def create_zip_archive(clip_paths: list, zip_destination: str):
    """Pack all generated reels into a single zip file."""
    os.makedirs(os.path.dirname(zip_destination), exist_ok=True)
    with zipfile.ZipFile(zip_destination, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for p in clip_paths:
            if os.path.exists(p):
                zipf.write(p, arcname=os.path.basename(p))
    return zip_destination

def process_video_task(task_id: str, input_path: str, output_dir: str, segment_len: float = 60.0, mode: str = "fast", overlap: float = 0.0, prefix: str = "Reel", cleanup_input: bool = True, temp_thumb_path: str = None):
    """
    Background worker thread function to slice video into 1-minute reels.
    Updates the global TASKS dictionary for real-time progress monitoring.
    Automatically deletes the uploaded input video and temp thumbnail when done.
    """
    ffmpeg_path = get_ffmpeg_path()
    
    with TASKS_LOCK:
        TASKS[task_id] = {
            "status": "analyzing",
            "progress": 5,
            "message": "Analyzing video metadata...",
            "current_clip": 0,
            "total_clips": 0,
            "clips": [],
            "zip_file": None,
            "error": None,
            "start_time": time.time(),
            "end_time": None
        }
    
    try:
        # 1. Analyze video
        metadata = get_video_metadata(input_path)
        total_duration = metadata["duration"]
        
        if total_duration <= 0:
            raise ValueError("Could not determine video duration. File may be corrupted.")
        
        # 2. Calculate segments
        segments = calculate_segments(total_duration, segment_len=segment_len, overlap=overlap)
        total_clips = len(segments)
        
        with TASKS_LOCK:
            TASKS[task_id].update({
                "status": "processing",
                "progress": 10,
                "message": f"Splitting video into {total_clips} reels ({int(segment_len)}s each)...",
                "total_clips": total_clips,
                "metadata": metadata
            })
            
        task_output_dir = Path(output_dir) / task_id
        os.makedirs(task_output_dir, exist_ok=True)
        
        generated_clips = []
        clip_paths = []
        
        for idx, (start_time, end_time) in enumerate(segments, start=1):
            clip_dur = end_time - start_time
            start_str = format_timestamp(start_time).replace(":", "-")
            end_str = format_timestamp(end_time).replace(":", "-")
            
            clip_filename = f"{prefix}_{idx:02d}_{start_str}_to_{end_str}.mp4"
            clip_path = str(task_output_dir / clip_filename)
            thumb_filename = f"{prefix}_{idx:02d}_thumb.jpg"
            thumb_path = str(task_output_dir / thumb_filename)
            
            with TASKS_LOCK:
                TASKS[task_id].update({
                    "current_clip": idx,
                    "message": f"Generating {prefix} {idx} of {total_clips} ({format_timestamp(start_time)} - {format_timestamp(end_time)})...",
                    "progress": int(10 + (idx - 1) / total_clips * 80)
                })
            
            # Cut clip
            cut_clip(ffmpeg_path, input_path, clip_path, start=start_time, duration=clip_dur, mode=mode)
            
            # Generate thumbnail for clip
            thumb_generated = generate_thumbnail(clip_path, thumb_path, at_second=min(1.0, clip_dur / 2))
            
            clip_size = os.path.getsize(clip_path) if os.path.exists(clip_path) else 0
            
            clip_info = {
                "index": idx,
                "filename": clip_filename,
                "start": start_time,
                "end": end_time,
                "start_formatted": format_timestamp(start_time),
                "end_formatted": format_timestamp(end_time),
                "duration": round(clip_dur, 1),
                "size": clip_size,
                "size_formatted": format_file_size(clip_size),
                "has_thumb": thumb_generated,
                "thumb_filename": thumb_filename
            }
            
            generated_clips.append(clip_info)
            clip_paths.append(clip_path)
            
            with TASKS_LOCK:
                TASKS[task_id]["clips"] = list(generated_clips)
                TASKS[task_id]["progress"] = int(10 + (idx / total_clips) * 80)
        
        # 3. Create ZIP archive
        with TASKS_LOCK:
            TASKS[task_id].update({
                "message": "Packaging all reels into ZIP archive...",
                "progress": 95
            })
            
        zip_filename = f"{prefix}_All_Reels_{task_id[:8]}.zip"
        zip_path = str(task_output_dir / zip_filename)
        create_zip_archive(clip_paths, zip_path)
        
        # 4. Finalize
        with TASKS_LOCK:
            TASKS[task_id].update({
                "status": "completed",
                "progress": 100,
                "message": f"Successfully created {total_clips} reels!",
                "clips": generated_clips,
                "zip_file": zip_filename,
                "end_time": time.time(),
                "elapsed": round(time.time() - TASKS[task_id]["start_time"], 1)
            })
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        with TASKS_LOCK:
            TASKS[task_id].update({
                "status": "error",
                "error": str(e),
                "message": f"Error: {str(e)}"
            })
    finally:
        # Automatically clean up the uploaded original video and preview thumbnail from disk
        if cleanup_input and input_path and os.path.exists(input_path):
            try:
                os.remove(input_path)
                print(f"[Cleanup] Deleted temporary uploaded video: {input_path}")
            except Exception as clean_err:
                print(f"[Cleanup] Failed to delete {input_path}: {clean_err}")
        if cleanup_input and temp_thumb_path and os.path.exists(temp_thumb_path):
            try:
                os.remove(temp_thumb_path)
            except Exception:
                pass
