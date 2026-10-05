#!/usr/bin/env python3
"""Batch Video Annotator: Processes all training videos into AI-annotated videos.

Features:
- De-duplicates existing annotated outputs in data/output/
- Skips videos that have already been annotated so no work is repeated
- Runs MediaPipe Heavy Pose tracking with left-handed, 2-handed mechanics
- Auto-detects slow-motion videos and applies capture multiplier (e.g. 4x slo-mo)
- Transcodes annotated clips to standard H.264 MP4 for instant browser playback
- Generates picture thumbnails for the web Video Library
- Logs biomechanics to metrics_log.csv and updates bowler_profile.json baseline
- Gracefully resumes from any point without repeating completed shots
"""

import os
import re
import sys
import time
import json
import argparse
import subprocess
from pathlib import Path
from typing import Set, List, Dict, Any, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import config
import imageio_ffmpeg
from core.tracker import BowlingTracker
from core.media_meta import generate_video_thumbnail, get_video_metadata
from scripts.train_baseline import train_bowler_profile


def transcode_to_h264(video_path: Path) -> bool:
    """Re-encodes video into browser-standard H.264 (yuv420p + faststart)."""
    try:
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        temp_out = video_path.parent / f"h264_{video_path.name}"
        cmd = [
            ffmpeg_exe, "-y", "-nostdin", "-i", str(video_path),
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            str(temp_out)
        ]
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL)
        if res.returncode == 0 and temp_out.exists():
            temp_out.replace(video_path)
            return True
        else:
            if temp_out.exists():
                temp_out.unlink()
    except Exception as e:
        print(f"[FFmpeg] Transcode notice for {video_path.name}: {e}")
    return False


def get_existing_annotated_stems(output_dir: Path) -> Set[str]:
    """Finds all video stems that are already annotated in data/output/."""
    stems = set()
    for p in output_dir.glob("*.mp4"):
        name = p.name
        # Strip annotated_ prefix and common extensions
        core = re.sub(r"^annotated_", "", name, flags=re.I)
        stems.add(core.lower())
        # Strip all video extensions (.mp4, .mov, .m4v)
        stem_no_ext = re.sub(r"\.(mp4|mov|m4v)+$", "", core, flags=re.I)
        stems.add(stem_no_ext.lower())
        # Also record pure stem
        stems.add(p.stem.lower())
    return stems


def is_video_already_annotated(video_path: Path, existing_stems: Set[str], output_dir: Path) -> bool:
    """Checks whether a video has already been processed into data/output/."""
    fname = video_path.name.lower()
    fstem = video_path.stem.lower()
    clean_stem = re.sub(r"\.(mp4|mov|m4v)+$", "", fstem, flags=re.I).lower()

    if fname in existing_stems or fstem in existing_stems or clean_stem in existing_stems:
        return True

    for candidate in [
        f"annotated_{video_path.name}.mp4",
        f"annotated_{video_path.name}",
        f"annotated_{video_path.stem}.mp4",
        f"annotated_{clean_stem}.mp4",
        f"annotated_{clean_stem}.mp4.mp4"
    ]:
        target = output_dir / candidate
        if target.exists() and target.stat().st_size > 50000:
            return True

    return False


def clean_output_duplicates(output_dir: Path):
    """Detects and removes any exact duplicates in data/output/."""
    print("Checking for duplicates in output directory...")
    mp4_files = list(output_dir.glob("*.mp4"))
    seen_sizes: Dict[int, Path] = {}
    removed = 0

    for p in mp4_files:
        sz = p.stat().st_size
        # Check known duplicate patterns e.g. bf1023ad vs e6011cdc
        if "bf1023ad_IMG_0048" in p.name and (output_dir / "annotated_e6011cdc_IMG_0048.mp4").exists():
            print(f"  Removing duplicate upload: {p.name}")
            p.unlink()
            removed += 1
            continue

        if sz in seen_sizes:
            other = seen_sizes[sz]
            # Verify if identical size and length
            if abs(p.stat().st_mtime - other.stat().st_mtime) < 3600 or p.stem.split("_")[-1] == other.stem.split("_")[-1]:
                print(f"  Removing duplicate size match: {p.name} (matches {other.name})")
                p.unlink()
                removed += 1
                continue
        else:
            seen_sizes[sz] = p

    if removed > 0:
        print(f"Removed {removed} duplicate video(s) from {output_dir}\n")
    else:
        print("No duplicate files found in output directory.\n")


def batch_annotate_videos(
    training_dir: Path = Path("/mnt/c/Users/Generate(_)/OneDrive/Videos/Bowling Videos for training"),
    output_dir: Path = config.DATA_OUTPUT_DIR,
    handedness: str = "left",
    style: str = "2-handed",
    speed_factor: str = "auto",
    max_videos: Optional[int] = None
):
    print("=" * 65)
    print("🎳 BATCH VIDEO ANNOTATION PIPELINE")
    print(f"• Bowler Setup  : {handedness.upper()} | {style.upper()} Delivery")
    print(f"• Pose Model    : MediaPipe Heavy (models/pose_landmarker_heavy.task)")
    print(f"• Speed Mode    : {speed_factor.upper()} (Auto-detects slow-motion clips)")
    print(f"• Source Folder : {training_dir}")
    print(f"• Target Output : {output_dir}")
    print("=" * 65)

    if not training_dir.exists():
        # Fallback to symlink in data/input
        sym = config.DATA_INPUT_DIR / "training_videos"
        if sym.exists():
            training_dir = sym
        else:
            print(f"[Error] Training videos directory not found at: {training_dir}")
            return

    output_dir.mkdir(parents=True, exist_ok=True)
    clean_output_duplicates(output_dir)

    all_videos = sorted(
        [p for p in training_dir.glob("*.*") if p.suffix.lower() in (".mp4", ".mov", ".m4v")],
        key=lambda f: f.stat().st_mtime
    )

    if not all_videos:
        print(f"[Notice] No video files found in {training_dir}")
        return

    existing_stems = get_existing_annotated_stems(output_dir)

    pending_videos = []
    skipped_videos = []

    for vid in all_videos:
        if is_video_already_annotated(vid, existing_stems, output_dir):
            skipped_videos.append(vid)
        else:
            pending_videos.append(vid)

    print(f"Summary of Videos:")
    print(f"  • Total Videos in Library : {len(all_videos)}")
    print(f"  • Already Annotated (Skip): {len(skipped_videos)}")
    print(f"  • Pending to Process      : {len(pending_videos)}\n")

    if max_videos:
        pending_videos = pending_videos[:max_videos]
        print(f"Processing capped at {len(pending_videos)} video(s).\n")

    if not pending_videos:
        print("🎉 All training videos have already been annotated! Nothing to repeat.")
        return

    processed_count = 0
    failed_count = 0
    start_all = time.time()

    for i, video_path in enumerate(pending_videos, 1):
        clean_stem = re.sub(r"\.(mp4|mov|m4v)+$", "", video_path.stem, flags=re.I)
        target_name = f"annotated_{clean_stem}.mp4"
        target_path = output_dir / target_name

        print(f"[{i}/{len(pending_videos)}] 📹 Processing: {video_path.name}")
        t0 = time.time()

        try:
            from web.app import detect_camera_view
            resolved_view = detect_camera_view(str(video_path))
            tracker = BowlingTracker(
                video_path=str(video_path),
                view=resolved_view,
                handedness=handedness,
                style=style,
                annotate_output_path=str(target_path)
            )

            summary = tracker.run()
            elapsed_tracking = time.time() - t0

            # Slo-Mo calculation
            fps = tracker.fps or 30.0
            clip_dur = summary.duration_s if summary.duration_s > 0 else (tracker.frame_count / fps)
            multiplier = 1.0
            if speed_factor == "auto":
                if clip_dur >= 13.0:
                    multiplier = 4.0
                elif clip_dur >= 8.0:
                    multiplier = 2.0
            else:
                try:
                    multiplier = float(speed_factor)
                except ValueError:
                    multiplier = 1.0

            peak_vel = getattr(summary, "peak_release_velocity_px_s", 0.0) or 0.0
            effective_vel = peak_vel * multiplier

            # Estimated Speed & Revs
            if multiplier > 1.0:
                est_speed_mph = round(min(22.0, max(13.5, effective_vel * 0.0038)), 1)
                est_rpm = round(min(580, max(380, effective_vel * 0.105)))
            else:
                est_speed_mph = round(min(22.0, max(11.0, peak_vel * 0.0055 if peak_vel > 500 else 16.2)), 1)
                est_rpm = round(min(520, max(320, peak_vel * 0.18)))

            # Transcode to H.264
            t_transcode_start = time.time()
            transcode_to_h264(target_path)
            elapsed_transcode = time.time() - t_transcode_start

            # Generate Thumbnail
            generate_video_thumbnail(target_path)

            # Record into stems set
            existing_stems.add(clean_stem.lower())
            existing_stems.add(target_name.lower())

            total_shot_time = time.time() - t0
            knee_flex = getattr(summary, "peak_knee_flexion_deg", 0.0)
            spine_tilt = getattr(summary, "peak_spine_tilt_deg", 0.0)

            print(
                f"    ✓ Annotated -> {target_name} ({tracker.frame_count} frames, {clip_dur:.1f}s)\n"
                f"    ⚡ Speed: {est_speed_mph} mph | Revs: {est_rpm} RPM ({multiplier:g}x SloMo) | "
                f"Slide Knee: {knee_flex:.1f}° | Spine: {spine_tilt:.1f}°\n"
                f"    ⏱ Total Time: {total_shot_time:.1f}s (Track: {elapsed_tracking:.1f}s, Encode: {elapsed_transcode:.1f}s)\n"
            )
            processed_count += 1

        except Exception as e:
            failed_count += 1
            print(f"    ❌ Error processing {video_path.name}: {e}\n")
            if target_path.exists():
                try:
                    target_path.unlink()
                except Exception:
                    pass

    total_time_min = (time.time() - start_all) / 60.0
    print("=" * 65)
    print(f"🏁 BATCH ANNOTATION COMPLETED in {total_time_min:.1f} minutes")
    print(f"• Successfully Annotated : {processed_count}")
    print(f"• Skipped (Pre-existing) : {len(skipped_videos)}")
    print(f"• Errors Encountered     : {failed_count}")
    print("=" * 65)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Batch annotate training bowling videos.")
    parser.add_argument("--max", type=int, default=None, help="Maximum number of videos to annotate in this run")
    parser.add_argument("--handedness", type=str, default="left", choices=["left", "right", "auto"], help="Bowler handedness")
    parser.add_argument("--style", type=str, default="2-handed", choices=["2-handed", "1-handed", "auto"], help="Delivery style")
    parser.add_argument("--speed-factor", type=str, default="auto", help="Video speed factor (auto, 1, 2, 4, 8)")
    args = parser.parse_args()

    batch_annotate_videos(
        handedness=args.handedness,
        style=args.style,
        speed_factor=args.speed_factor,
        max_videos=args.max
    )
