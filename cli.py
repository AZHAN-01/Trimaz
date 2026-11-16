"""
Trimaz - Command Line Tool
Cut large videos into 1-minute reels directly from your terminal.

Usage:
    python cli.py <input_video_path> [options]

Examples:
    python cli.py my_podcast.mp4
    python cli.py webinar.mkv --duration 60 --mode fast --overlap 2
    python cli.py lecture.mp4 --duration 60 --mode portrait_blur --prefix Reel
"""

import os
import sys
import argparse
import time
from pathlib import Path
import cutter
import downloader

def main():
    parser = argparse.ArgumentParser(
        description="Cut large videos into 1-minute reels, shorts, or TikTok clips.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("video", help="Path to the video file to cut")
    parser.add_argument("-d", "--duration", type=float, default=60.0, help="Reel duration in seconds (default: 60.0s / 1 min)")
    parser.add_argument("-m", "--mode", choices=["fast", "portrait_blur", "portrait_crop", "portrait_fit"], default="fast",
                        help="Cutting style:\n"
                             "  fast: Stream copy (lossless, instant 100x speed)\n"
                             "  portrait_blur: 9:16 vertical reel with blurred background\n"
                             "  portrait_crop: 9:16 vertical center crop\n"
                             "  portrait_fit: 9:16 letterbox with black bars")
    parser.add_argument("-o", "--output", default="outputs", help="Output directory (default: ./outputs)")
    parser.add_argument("--overlap", type=float, default=0.0, help="Overlap in seconds between reels (default: 0)")
    parser.add_argument("-p", "--prefix", default="Reel", help="Filename prefix (default: Reel)")

    args = parser.parse_args()
    raw_video = args.video.strip()
    is_url = raw_video.startswith("http://") or raw_video.startswith("https://")
    cleanup_after = False

    if is_url:
        print(f"🔗 Detected Video URL: {raw_video}")
        print("⬇️  Fetching video stream...")
        try:
            res = downloader.download_video_from_url(raw_video, "uploads")
            video_path = Path(res["path"]).resolve()
            cleanup_after = True
            print(f"✅ Downloaded: {video_path.name}")
        except Exception as e:
            print(f"❌ Failed to download from URL: {e}")
            sys.exit(1)
    else:
        video_path = Path(raw_video).resolve()
        if not video_path.exists():
            print(f"❌ Error: Video file not found: {video_path}")
            sys.exit(1)

    print("=" * 60)
    print(f"🎬 Trimaz - 1-Minute Reel Generator")
    print("=" * 60)
    print(f"📁 Video:    {video_path.name}")
    print(f"⏱️  Duration: {args.duration}s per reel")
    print(f"⚙️  Mode:     {args.mode}")
    print(f"📂 Output:   {args.output}")
    print("-" * 60)

    try:
        meta = cutter.get_video_metadata(str(video_path))
        print(f"📊 Video Info: {meta['duration_formatted']} | {meta['width']}x{meta['height']} | {meta['fps']} fps | {meta['file_size_formatted']}")
    except Exception as e:
        print(f"⚠️ Warning: Could not read metadata: {e}")

    task_id = f"cli_{int(time.time())}"
    
    print("\n🚀 Processing video...")
    
    # Process (auto-cleanup if downloaded from link, preserve if local file)
    cutter.process_video_task(
        task_id=task_id,
        input_path=str(video_path),
        output_dir=args.output,
        segment_len=args.duration,
        mode=args.mode,
        overlap=args.overlap,
        prefix=args.prefix,
        cleanup_input=cleanup_after
    )

    task = cutter.TASKS.get(task_id, {})
    if task.get("status") == "completed":
        clips = task.get("clips", [])
        print(f"\n✅ SUCCESS! Generated {len(clips)} reels in {task.get('elapsed', 0)} seconds:")
        for c in clips:
            print(f"   ▶ {c['filename']} [{c['duration']}s | {c['size_formatted']}]")
        print(f"\n📦 All reels packed in ZIP: {task.get('zip_file')}")
        print(f"📁 Output folder: {os.path.abspath(os.path.join(args.output, task_id))}")
    else:
        print(f"\n❌ Error: {task.get('error') or task.get('message')}")
        sys.exit(1)

if __name__ == "__main__":
    main()
