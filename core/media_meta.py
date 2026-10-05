"""Extracts video thumbnails, timestamps, and GPS locations from bowling videos."""

import os
import re
import cv2
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

import config
import imageio_ffmpeg

THUMBNAILS_DIR = config.PROJECT_ROOT / "data" / "thumbnails"
THUMBNAILS_DIR.mkdir(parents=True, exist_ok=True)
CACHE_FILE = THUMBNAILS_DIR / "metadata_cache.json"

_METADATA_CACHE: Dict[str, Any] = {}
if CACHE_FILE.exists():
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            _METADATA_CACHE = json.load(f)
    except Exception:
        _METADATA_CACHE = {}


def _save_cache():
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(_METADATA_CACHE, f, indent=2)
    except Exception:
        pass


def parse_filename_datetime(filename: str) -> Optional[datetime]:
    """Attempts to parse recording timestamp from common phone video filename conventions."""
    # Pattern 1: 20260926_142544.mp4 or VID_20260904_180655...
    m = re.search(r'(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})', filename)
    if m:
        try:
            year, month, day, hour, minute, second = map(int, m.groups())
            return datetime(year, month, day, hour, minute, second)
        except ValueError:
            pass

    # Pattern 2: VID-20260706-WA0002
    m2 = re.search(r'(\d{4})(\d{2})(\d{2})', filename)
    if m2:
        try:
            year, month, day = map(int, m2.groups())
            return datetime(year, month, day, 12, 0, 0)
        except ValueError:
            pass

    return None


def extract_iso6709_location(text: str) -> Optional[Dict[str, Any]]:
    """Extracts ISO-6709 latitude/longitude from ffmpeg metadata and provides city/maps link."""
    # Example format: +01.3470+103.7810/ or location-eng : +01.3469+103.7809/
    match = re.search(r'location(?:-\w+)?\s*:\s*([+-]\d{2}(?:\.\d+)?)([+-]\d{3}(?:\.\d+)?)/?', text, re.IGNORECASE)
    if not match:
        match = re.search(r'([+-]\d{2}\.\d{4,})([+-]\d{3}\.\d{4,})', text)

    if match:
        try:
            lat = float(match.group(1))
            lon = float(match.group(2))
            
            # Identify region / city
            region = f"{lat:.3f}°, {lon:.3f}°"
            if 1.15 <= lat <= 1.48 and 103.60 <= lon <= 104.05:
                region = "Singapore"
            elif 3.0 <= lat <= 3.3 and 101.5 <= lon <= 101.8:
                region = "Kuala Lumpur, Malaysia"

            return {
                "latitude": lat,
                "longitude": lon,
                "formatted": f"{region} ({lat:.3f}°, {lon:.3f}°)",
                "maps_url": f"https://www.google.com/maps?q={lat},{lon}"
            }
        except Exception:
            pass
    return None


def get_video_metadata(video_path: Path, probe_ffmpeg: bool = False) -> Dict[str, Any]:
    """Gathers date, time, duration, resolution, size, and GPS location."""
    filename = video_path.name
    try:
        stat = video_path.stat()
        file_size_mb = round(stat.st_size / (1024 * 1024), 1)
        mtime = stat.st_mtime
        fsize = stat.st_size
    except Exception:
        file_size_mb = 0.0
        mtime = 0
        fsize = 0

    cache_key = f"{filename}_{mtime}_{fsize}"
    if cache_key in _METADATA_CACHE:
        return _METADATA_CACHE[cache_key]

    # 1. Instant Date & Time from filename or mtime
    dt = parse_filename_datetime(filename)
    if not dt and mtime > 0:
        dt = datetime.fromtimestamp(mtime)

    date_str = dt.strftime("%d %b %Y") if dt else "Unknown Date"
    time_str = dt.strftime("%I:%M %p") if dt else ""
    full_datetime = f"{date_str} at {time_str}" if time_str else date_str

    duration_s = 0.0
    resolution = None
    location_data = None

    if probe_ffmpeg:
        try:
            exe = imageio_ffmpeg.get_ffmpeg_exe()
            res = subprocess.run(
                [exe, "-nostdin", "-i", str(video_path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                text=True,
                timeout=2
            )
            raw_info = res.stderr

            # Duration
            dur_m = re.search(r'Duration:\s*(\d{2}):(\d{2}):(\d{2}\.\d+)', raw_info)
            if dur_m:
                hours, mins, secs = map(float, dur_m.groups())
                duration_s = round(hours * 3600 + mins * 60 + secs, 1)

            # Resolution
            res_m = re.search(r'Stream.*Video.*,\s*(\d{3,4})x(\d{3,4})', raw_info)
            if res_m:
                w, h = int(res_m.group(1)), int(res_m.group(2))
                resolution = f"{w}x{h}"

            # Location
            location_data = extract_iso6709_location(raw_info)

        except Exception:
            pass

    meta = {
        "filename": filename,
        "date": date_str,
        "time": time_str,
        "datetime": full_datetime,
        "duration_s": duration_s,
        "duration_str": f"{duration_s:.1f}s" if duration_s > 0 else "",
        "size_mb": file_size_mb,
        "resolution": resolution or "",
        "location": location_data,
    }

    if probe_ffmpeg or cache_key in _METADATA_CACHE:
        _METADATA_CACHE[cache_key] = meta
        _save_cache()

    return meta


def generate_video_thumbnail(video_path: Path) -> Optional[Path]:
    """Generates a small JPEG thumbnail and probes video metadata."""
    thumb_name = f"thumb_{video_path.stem}.jpg"
    thumb_path = THUMBNAILS_DIR / thumb_name

    # Also ensure full metadata (including GPS) is probed and cached
    get_video_metadata(video_path, probe_ffmpeg=True)

    if thumb_path.exists() and thumb_path.stat().st_size > 500:
        return thumb_path

    try:
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return None

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 60)
        # Capture frame at ~20% of video (bowler starting approach or setting up)
        target_frame = min(45, max(1, total_frames // 5))
        cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)

        ok, frame = cap.read()
        if not ok or frame is None:
            # Fallback to first frame
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = cap.read()

        cap.release()

        if ok and frame is not None:
            # Resize thumbnail (max width 320px)
            h, w = frame.shape[:2]
            target_w = 320
            target_h = int(h * (target_w / w))
            resized = cv2.resize(frame, (target_w, target_h), interpolation=cv2.INTER_AREA)

            cv2.imwrite(str(thumb_path), resized, [cv2.IMWRITE_JPEG_QUALITY, 80])
            return thumb_path

    except Exception as e:
        print(f"[Thumbnail] Error generating thumbnail for {video_path.name}: {e}")

    return None
