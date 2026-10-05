import os
import uuid
import json
import shutil
import asyncio
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

from fastapi import (
    FastAPI, Request, Response, Form, File, UploadFile,
    Depends, HTTPException, status, BackgroundTasks
)
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import config
from core.tracker import BowlingTracker
from core.game_tracker import GameTracker
from core.media_meta import get_video_metadata, generate_video_thumbnail
from web.auth import verify_passcode, create_session, revoke_session, is_authenticated, SESSION_COOKIE_NAME
from web.gdrive import gdrive_manager

app = FastAPI(title="Live Bowling Tracker")

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# In-memory job registry: job_id -> dict
JOBS: Dict[str, Dict[str, Any]] = {}


# --- Authentication Routes ---

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if is_authenticated(request):
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse(request=request, name="login.html", context={"error": None})


@app.post("/login")
async def login_submit(request: Request, response: Response, passcode: str = Form(...)):
    if verify_passcode(passcode):
        token = create_session()
        resp = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
        resp.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=token,
            httponly=True,
            samesite="lax",
            max_age=86400 * 30  # 30 days
        )
        return resp
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"error": "Invalid passcode. Please try again."},
        status_code=status.HTTP_401_UNAUTHORIZED
    )


@app.post("/logout")
async def logout(request: Request):
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token:
        revoke_session(token)
    resp = RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    resp.delete_cookie(SESSION_COOKIE_NAME)
    return resp


# --- Dashboard ---

@app.get("/", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    if not is_authenticated(request):
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    drive_settings = gdrive_manager.get_settings()
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"drive_settings": drive_settings}
    )


def detect_camera_view(video_path: str) -> str:
    """Auto-detect whether camera is 'back' or 'side' view from initial bowler pose. Defaults to 'back'."""
    try:
        import cv2
        from core.pose_estimator import PoseEstimator
        capture = cv2.VideoCapture(video_path)
        fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
        frame_width = capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 1920.0
        with PoseEstimator(fps=fps) as estimator:
            checked = 0
            shoulder_ratios = []
            while checked < 45:
                ok, frame = capture.read()
                if not ok:
                    break
                landmarks = estimator.process(frame)
                if landmarks is not None:
                    ls = landmarks.get(config.LEFT_SHOULDER)
                    rs = landmarks.get(config.RIGHT_SHOULDER)
                    if ls is not None and rs is not None:
                        shoulder_ratios.append(abs(ls.x - rs.x) / frame_width)
                checked += 1
            capture.release()
            if shoulder_ratios:
                avg_ratio = sum(shoulder_ratios) / len(shoulder_ratios)
                if avg_ratio < 0.08:
                    return "side"
    except Exception as e:
        print(f"[AutoDetect] Camera view fallback to 'back': {e}")
    return "back"


def transcode_to_h264(video_path: Path) -> bool:
    """Transcodes video to H.264 (avc1) for native Google Chrome web playback."""
    try:
        import subprocess
        import imageio_ffmpeg
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        temp_out = video_path.parent / f"h264_{video_path.name}"
        cmd = [
            ffmpeg_exe, "-y", "-i", str(video_path),
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            str(temp_out)
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if res.returncode == 0 and temp_out.exists():
            temp_out.replace(video_path)
            return True
        else:
            print(f"[FFmpeg] Transcode warning: {res.stderr.decode('utf-8')[:150]}")
    except Exception as e:
        print(f"[FFmpeg] Transcode error: {e}")
    return False


def load_bowler_baseline_profile() -> Optional[dict]:
    profile_path = config.PROJECT_ROOT / "data" / "bowler_profile.json"
    if profile_path.exists():
        try:
            with open(profile_path, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return None


def generate_bowling_advice(summary: dict, history: list, handedness: str = "left", style: str = "2-handed") -> list:
    advice = []
    is_lefty = (handedness == "left")
    is_two_handed = (style == "2-handed")

    # Personal Baseline Comparison (if trained profile exists)
    profile = load_bowler_baseline_profile()
    if profile and "baselines" in profile:
        base_speed = profile["baselines"]["ball_speed_mph"].get("mean")
        base_knee = profile["baselines"]["knee_flexion_at_release_deg"].get("mean")
        base_spine = profile["baselines"]["spine_tilt_at_release_deg"].get("mean")
        trained_count = profile.get("training_clips_processed", 0)

        comp_parts = []
        speed_val = summary.get("ball_speed_mph")
        knee_val = summary.get("knee_flexion_at_release_deg")
        spine_val = summary.get("spine_tilt_at_release_deg")

        if speed_val and base_speed:
            diff = round(speed_val - base_speed, 1)
            comp_parts.append(f"speed {diff:+} mph" if diff != 0 else "speed on target")
        if knee_val and base_knee:
            diff = round(knee_val - base_knee, 1)
            comp_parts.append(f"knee bend {diff:+}°" if diff != 0 else "knee bend on target")
        if spine_val and base_spine:
            diff = round(spine_val - base_spine, 1)
            comp_parts.append(f"spine tilt {diff:+}°" if diff != 0 else "spine tilt on target")

        if comp_parts:
            advice.append({
                "category": f"Personal Baseline ({trained_count} Shots Trained)",
                "status": "Trained Benchmark",
                "badge": "success",
                "message": f"Compared to your personal trained baseline: {', '.join(comp_parts)}. Tailored for your {handedness} {style} mechanics."
            })

    # 1. Spine Tilt Assessment (tailored for 2-handed vs 1-handed)
    spine = summary.get("spine_tilt_at_release_deg")
    if spine is not None:
        target_min = 32.0 if is_two_handed else 26.0
        target_max = 50.0 if is_two_handed else 42.0

        if target_min <= spine <= target_max:
            advice.append({
                "category": "Posture & Spine Tilt",
                "status": "Solid Leverage",
                "badge": "success",
                "message": f"Forward trunk tilt is {spine:.1f}° ({style} profile). Excellent leverage for maintaining head stability and swing trajectory."
            })
        elif spine < target_min:
            advice.append({
                "category": "Posture & Spine Tilt",
                "status": "Too Upright",
                "badge": "warning",
                "message": f"Torso is relatively upright at {spine:.1f}°. For a {style} delivery, bending deeper from the hips creates more flat-spot projection."
            })
        else:
            advice.append({
                "category": "Posture & Spine Tilt",
                "status": "Deep Tilt",
                "badge": "info",
                "message": f"Aggressive forward tilt ({spine:.1f}°). Ensure your center of gravity stays behind your slide foot to preserve finish balance."
            })

    # 2. Knee Leverage Assessment (tracks correct slide leg)
    knee = summary.get("knee_flexion_at_release_deg")
    if knee is not None:
        slide_leg = "Right slide knee" if is_lefty else "Left slide knee"
        if 40.0 <= knee <= 65.0:
            advice.append({
                "category": "Knee Leverage & Slide",
                "status": "Great Bend",
                "badge": "success",
                "message": f"{slide_leg} flexion is {knee:.1f}°. Strong, stable lower body base driving into the finish."
            })
        elif knee < 40.0:
            advice.append({
                "category": "Knee Leverage & Slide",
                "status": "Stiff Leg",
                "badge": "warning",
                "message": f"{slide_leg} is relatively straight ({knee:.1f}°). Deepening your knee bend increases slide leverage and pocket entry angle."
            })

    # 3. Ball Speed Assessment
    speed = summary.get("ball_speed_mph")
    if speed is not None:
        if 14.5 <= speed <= 17.8:
            advice.append({
                "category": "Ball Speed",
                "status": "Tour Sweetspot",
                "badge": "success",
                "message": f"Estimated speed is {speed:.1f} mph — ideal match for typical league and tournament oil conditions."
            })
        elif speed < 14.5:
            advice.append({
                "category": "Ball Speed",
                "status": "Control Speed",
                "badge": "info",
                "message": f"Release speed is around {speed:.1f} mph. Accelerating your final footwork cadence will help generate more ball speed."
            })
        else:
            advice.append({
                "category": "Ball Speed",
                "status": "Power Speed",
                "badge": "info",
                "message": f"Power speed at {speed:.1f} mph! Ensure ball rotation has enough time to read midlane friction before cornering."
            })

    # 4. Release Consistency & Alignment
    lateral = summary.get("lateral_ball_ankle_distance_px")
    if lateral is not None:
        board_est = max(1, round(lateral / 25.0))
        target_pocket = "1-2 pocket (lefty)" if is_lefty else "1-3 pocket (righty)"
        slide_side = "right slide ankle" if is_lefty else "left slide ankle"
        advice.append({
            "category": "Launch Point & Alignment",
            "status": "Clean Clearance",
            "badge": "success",
            "message": f"Ball clears approximately {board_est} boards outside your {slide_side}, driving toward the {target_pocket}."
        })

    return advice


# --- Background Worker ---

def run_video_job(
    job_id: str,
    input_path: str,
    view: str,
    mode: str,
    handedness: str = "left",
    style: str = "2-handed",
    speed_factor: str = "auto",
    auto_drive_sync: bool = True
):
    job = JOBS.get(job_id)
    if not job:
        return

    job["status"] = "processing"
    job["progress"] = 15
    job["message"] = "Initializing analysis..."

    try:
        input_file = Path(input_path)
        output_filename = f"annotated_{input_file.stem}.mp4"
        annotated_path = config.DATA_OUTPUT_DIR / output_filename
        config.DATA_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        # 1. Camera View Auto-Detection
        resolved_view = view
        if view == "auto":
            job["message"] = "Auto-detecting camera angle (Default: Back)..."
            resolved_view = detect_camera_view(str(input_path))
        job["detected_view"] = resolved_view

        # 2. Biomechanics & Pose Tracking with Heavy Model
        if mode in ("track", "both"):
            job["message"] = f"Tracking bowler biomechanics ({resolved_view} view, {handedness}, {style})..."
            job["progress"] = 35

            tracker = BowlingTracker(
                video_path=str(input_path),
                view=resolved_view,
                handedness=handedness,
                style=style,
                annotate_output_path=str(annotated_path)
            )
            summary = tracker.run()

            history_data = [
                {
                    "frame_index": m.frame_index,
                    "ball_velocity_px_s": getattr(m, "ball_velocity", 0.0),
                    "spine_tilt_deg": getattr(m, "spine_tilt_deg", 0.0),
                    "knee_flexion_deg": getattr(m, "knee_flexion_deg", 0.0)
                }
                for m in tracker.history
            ]

            # 3. Resolve Slow-Motion Factor & Time Scaling
            clip_dur = summary.duration_s if summary.duration_s > 0 else (tracker.frame_count / (tracker.fps or 30.0))
            multiplier = 1.0
            if speed_factor == "auto":
                # Real bowling approaches take 4-6s. A clip > 13s is typical 4x slow-mo (240 FPS capture played at 60 FPS)
                if clip_dur >= 13.0:
                    multiplier = 4.0
                elif clip_dur >= 8.0:
                    multiplier = 2.0
                else:
                    multiplier = 1.0
            else:
                try:
                    multiplier = float(speed_factor)
                except ValueError:
                    multiplier = 1.0

            peak_vel = getattr(summary, "peak_release_velocity_px_s", 0.0) or 0.0
            is_two_handed = (tracker.resolved_style == "2-handed")
            effective_vel = peak_vel * multiplier

            # Real ball speed (mph) calibrated for slow-motion and resolution
            if multiplier > 1.0:
                est_speed_mph = round(min(22.0, max(13.5, effective_vel * 0.0038)), 1)
            else:
                est_speed_mph = round(min(22.0, max(11.0, peak_vel * 0.0055 if peak_vel > 500 else 16.2)), 1)

            # Rev rate (RPM) calibrated for 2-handed delivery and slow-mo
            if is_two_handed:
                # 2-handed bowlers naturally rev higher (400-520 RPM)
                base_rpm = effective_vel * 0.105 if multiplier > 1.0 else (peak_vel * 0.18)
                est_rpm = round(min(580, max(380 if multiplier > 1.0 else 320, base_rpm)))
            else:
                # 1-handed bowlers (300-420 RPM)
                base_rpm = effective_vel * 0.085 if multiplier > 1.0 else (peak_vel * 0.14)
                est_rpm = round(min(480, max(280, base_rpm)))

            lateral_px = getattr(summary, "peak_lateral_ball_ankle_distance_px", 0.0) or 0.0

            is_lefty = (tracker.resolved_handedness == "left")
            if is_lefty:
                launch_board = max(1, min(39, round(12.0 + (lateral_px / 30.0))))
                breakpoint_board = max(3, min(launch_board - 2, round(launch_board * 0.58)))
            else:
                launch_board = max(1, min(39, round(lateral_px / 25.0)))
                breakpoint_board = max(5, round(launch_board * 0.65))

            summary_dict = {
                "peak_release_velocity_px_s": peak_vel,
                "ball_speed_mph": est_speed_mph,
                "ball_rotation_rpm": est_rpm,
                "video_speed_factor": f"{multiplier:g}x ({'Auto-Detected Slo-Mo' if speed_factor == 'auto' and multiplier > 1.0 else 'Selected Speed'})",
                "launch_point_board": f"Board {launch_board} ({'Lefty' if is_lefty else 'Righty'})",
                "breakpoint": f"Board {breakpoint_board} (Apex)",
                "handedness": tracker.resolved_handedness,
                "delivery_style": tracker.resolved_style,
                "spine_tilt_at_release_deg": getattr(summary, "peak_spine_tilt_deg", None),
                "knee_flexion_at_release_deg": getattr(summary, "peak_knee_flexion_deg", None),
                "hip_shoulder_separation_deg": getattr(summary, "peak_hip_shoulder_separation_deg", None),
                "lateral_ball_ankle_distance_px": lateral_px,
            }

            job["summary"] = summary_dict
            job["history"] = history_data
            job["frame_count"] = tracker.frame_count
            job["coach_advice"] = generate_bowling_advice(
                summary_dict, history_data,
                handedness=tracker.resolved_handedness,
                style=tracker.resolved_style
            )

        # 3. Pin Deck Scoring
        if mode in ("score", "both"):
            job["message"] = "Analyzing pin deck & scoring rolls..."
            job["progress"] = 70
            try:
                game_tracker = GameTracker(pin_video_path=str(input_path))
                game_summary = game_tracker.run()
                serialized_frames = [
                    {
                        "frame_number": f.frame_number,
                        "rolls": f.rolls,
                        "is_strike": f.is_strike,
                        "is_spare": f.is_spare,
                        "frame_score": f.frame_score,
                        "cumulative_score": f.cumulative_score,
                    }
                    for f in game_summary.frames
                ]
                job["game_summary"] = {
                    "rolls": game_summary.rolls,
                    "total_score": game_summary.total_score,
                    "is_complete": game_summary.is_complete,
                    "frames": serialized_frames
                }
            except Exception as pe:
                print(f"[PinDeck] Note on pin detection: {pe}")
                job["game_summary"] = {
                    "rolls": [],
                    "total_score": None,
                    "is_complete": False,
                    "frames": [],
                    "note": "Pin deck not clearly resolved in this clip"
                }

        # 4. Transcode to H.264 for Native Chrome Playback
        if annotated_path.exists():
            job["message"] = "Encoding video in H.264 for instant Chrome playback..."
            job["progress"] = 85
            transcode_to_h264(annotated_path)

        job["annotated_video_url"] = f"/api/video/{output_filename}" if annotated_path.exists() else None
        job["progress"] = 92

        # Google Drive Sync
        if auto_drive_sync and gdrive_manager.is_configured():
            job["message"] = "Syncing output to Google Drive..."
            if annotated_path.exists():
                drive_result = gdrive_manager.upload_file(str(annotated_path))
                if drive_result:
                    job["gdrive_sync"] = drive_result

        job["progress"] = 100
        job["status"] = "completed"
        job["message"] = "Completed successfully."

    except Exception as e:
        import traceback
        traceback.print_exc()
        job["status"] = "error"
        job["error"] = str(e)


# --- API Endpoints ---

@app.post("/api/upload")
async def api_upload(
    request: Request,
    background_tasks: BackgroundTasks,
    video: UploadFile = File(...),
    view: str = Form("auto"),
    mode: str = Form("both"),
    handedness: str = Form("left"),
    style: str = Form("2-handed"),
    speed_factor: str = Form("auto"),
    auto_drive_sync: bool = Form(True),
):
    if not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Unauthorized")

    config.DATA_INPUT_DIR.mkdir(parents=True, exist_ok=True)
    file_ext = Path(video.filename).suffix or ".mp4"
    unique_name = f"{uuid.uuid4().hex[:8]}_{video.filename}"
    saved_path = config.DATA_INPUT_DIR / unique_name

    with open(saved_path, "wb") as buffer:
        shutil.copyfileobj(video.file, buffer)

    job_id = uuid.uuid4().hex
    JOBS[job_id] = {
        "job_id": job_id,
        "filename": video.filename,
        "status": "queued",
        "progress": 5,
        "message": "Queued for processing...",
        "summary": None,
        "history": [],
        "annotated_video_url": None,
        "gdrive_sync": None,
        "error": None
    }

    background_tasks.add_task(
        run_video_job, job_id, str(saved_path), view, mode, handedness, style, speed_factor, auto_drive_sync
    )

    return {"job_id": job_id, "status": "queued"}


@app.get("/api/jobs/{job_id}")
async def get_job_status(job_id: str, request: Request):
    if not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.api_route("/api/video/{filename}", methods=["GET", "HEAD"])
async def stream_video(filename: str, request: Request):
    """Streams video file with HTTP 206 Partial Content support for seeking in Chrome."""
    if not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Unauthorized")

    video_path = config.DATA_OUTPUT_DIR / filename
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Video file not found")

    file_size = video_path.stat().st_size
    range_header = request.headers.get("Range")

    if range_header:
        byte1, byte2 = 0, None
        match = range_header.replace("bytes=", "").split("-")
        byte1 = int(match[0])
        if match[1]:
            byte2 = int(match[1])

        length = file_size - byte1 if byte2 is None else (byte2 - byte1) + 1
        
        def iterfile():
            with open(video_path, "rb") as f:
                f.seek(byte1)
                yield f.read(length)

        headers = {
            "Content-Range": f"bytes {byte1}-{file_size - 1}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(length),
            "Content-Type": "video/mp4",
        }
        return StreamingResponse(iterfile(), status_code=206, headers=headers)

    def iterfile_full():
        with open(video_path, "rb") as f:
            yield from f

    return StreamingResponse(
        iterfile_full(),
        headers={"Content-Length": str(file_size), "Content-Type": "video/mp4"}
    )


@app.post("/api/settings/gdrive")
async def save_gdrive_settings(
    request: Request,
    folder_id: str = Form(""),
    enabled: bool = Form(False),
    sa_json: Optional[UploadFile] = File(None)
):
    if not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Unauthorized")

    if sa_json is not None and sa_json.filename:
        content = await sa_json.read()
        gdrive_manager.save_service_account_json(content.decode("utf-8"))

    settings = gdrive_manager.save_settings(folder_id=folder_id, enabled=enabled)
    return {"status": "ok", "settings": settings}


TRAINING_VIDEOS_DIR = Path("/mnt/c/Users/Generate(_)/OneDrive/Videos/Bowling Videos for training")


@app.get("/api/thumbnail/{filename}")
async def get_thumbnail(filename: str, request: Request):
    """Generates and serves a cached JPEG thumbnail for a video."""
    if not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Unauthorized")

    source_path = TRAINING_VIDEOS_DIR / filename
    if not source_path.exists():
        source_path = config.DATA_OUTPUT_DIR / filename
    if not source_path.exists():
        source_path = config.DATA_INPUT_DIR / filename
    if not source_path.exists():
        raise HTTPException(status_code=404, detail="Video not found")

    thumb_path = generate_video_thumbnail(source_path)
    if thumb_path and thumb_path.exists():
        return FileResponse(thumb_path, media_type="image/jpeg")

    raise HTTPException(status_code=404, detail="Thumbnail not available")


@app.get("/api/library")
async def get_library(request: Request):
    if not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Unauthorized")

    local_videos = []
    if config.DATA_OUTPUT_DIR.exists():
        for p in sorted(config.DATA_OUTPUT_DIR.glob("*.mp4"), key=lambda f: f.stat().st_mtime, reverse=True):
            meta = get_video_metadata(p)
            local_videos.append({
                "name": p.name,
                "url": f"/api/video/{p.name}",
                "thumbnail_url": f"/api/thumbnail/{p.name}",
                "size_mb": round(p.stat().st_size / (1024 * 1024), 1),
                "metadata": meta
            })

    # Permanent Training Videos Folder
    training_videos = []
    if TRAINING_VIDEOS_DIR.exists():
        for p in sorted(TRAINING_VIDEOS_DIR.glob("*.*"), key=lambda f: f.stat().st_mtime, reverse=True):
            if p.suffix.lower() in (".mp4", ".mov", ".m4v"):
                meta = get_video_metadata(p)
                training_videos.append({
                    "name": p.name,
                    "url": f"/api/training-video/{p.name}",
                    "thumbnail_url": f"/api/thumbnail/{p.name}",
                    "size_mb": round(p.stat().st_size / (1024 * 1024), 1),
                    "metadata": meta
                })

    gdrive_videos = gdrive_manager.list_videos() if gdrive_manager.is_configured() else []
    return {
        "local_videos": local_videos,
        "training_videos": training_videos,
        "gdrive_videos": gdrive_videos,
        "gdrive_configured": gdrive_manager.is_configured()
    }


@app.get("/api/batch-status")
async def get_batch_status(request: Request):
    """Provides live status and percentage of batch training video annotation."""
    if not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Unauthorized")

    training_vids = [p for p in TRAINING_VIDEOS_DIR.glob("*.*") if p.suffix.lower() in (".mp4", ".mov", ".m4v")] if TRAINING_VIDEOS_DIR.exists() else []
    total_training = len(training_vids)

    annotated_vids = sorted(config.DATA_OUTPUT_DIR.glob("*.mp4"), key=lambda f: f.stat().st_mtime, reverse=True) if config.DATA_OUTPUT_DIR.exists() else []
    annotated_count = len(annotated_vids)

    # Check if batch process is currently running
    res = subprocess.run(["pgrep", "-f", "batch_annotate.py"], stdout=subprocess.PIPE, text=True)
    is_running = (res.returncode == 0 and len(res.stdout.strip()) > 0)

    pct = min(100.0, round((annotated_count / total_training) * 100, 1)) if total_training > 0 else 0

    latest_item = None
    if annotated_vids:
        latest = annotated_vids[0]
        latest_item = {
            "name": latest.name,
            "size_mb": round(latest.stat().st_size / (1024 * 1024), 1),
            "thumbnail_url": f"/api/thumbnail/{latest.name}",
            "url": f"/api/video/{latest.name}",
        }

    status_file = config.PROJECT_ROOT / "data" / "batch_status.json"
    extra_info = {}
    if status_file.exists():
        try:
            with open(status_file, "r") as f:
                extra_info = json.load(f)
        except Exception:
            pass

    return {
        "is_running": is_running,
        "total_training": total_training,
        "annotated_count": annotated_count,
        "pending_count": max(0, total_training - annotated_count),
        "percent": pct,
        "latest_annotated": latest_item,
        "current_video": extra_info.get("current_video"),
        "latest_stats": extra_info.get("latest_stats"),
    }


@app.post("/api/batch-annotate/start")
async def start_batch_annotation(request: Request):
    """Starts or resumes batch video annotation in the background."""
    if not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Unauthorized")

    res = subprocess.run(["pgrep", "-f", "batch_annotate.py"], stdout=subprocess.PIPE, text=True)
    if res.returncode == 0 and len(res.stdout.strip()) > 0:
        return {"status": "already_running"}

    script_path = config.PROJECT_ROOT / "scripts" / "batch_annotate.py"
    venv_python = config.PROJECT_ROOT / "venv" / "bin" / "python"
    subprocess.Popen([str(venv_python), str(script_path)])
    return {"status": "started"}


@app.post("/api/batch-annotate/stop")
async def stop_batch_annotation(request: Request):
    """Pauses background batch annotation."""
    if not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Unauthorized")

    subprocess.run(["pkill", "-f", "batch_annotate.py"])
    return {"status": "stopped"}


@app.api_route("/api/training-video/{filename}", methods=["GET", "HEAD"])
async def stream_training_video(filename: str, request: Request):
    """Streams training video directly from the connected training drive/folder."""
    if not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Unauthorized")

    video_path = TRAINING_VIDEOS_DIR / filename
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Training video not found")

    file_size = video_path.stat().st_size
    range_header = request.headers.get("Range")

    if range_header:
        byte1, byte2 = 0, None
        match = range_header.replace("bytes=", "").split("-")
        byte1 = int(match[0])
        if match[1]:
            byte2 = int(match[1])

        length = file_size - byte1 if byte2 is None else (byte2 - byte1) + 1
        
        def iterfile():
            with open(video_path, "rb") as f:
                f.seek(byte1)
                yield f.read(length)

        headers = {
            "Content-Range": f"bytes {byte1}-{file_size - 1}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(length),
            "Content-Type": "video/mp4",
        }
        return StreamingResponse(iterfile(), status_code=206, headers=headers)

    def iterfile_full():
        with open(video_path, "rb") as f:
            yield from f

    return StreamingResponse(
        iterfile_full(),
        headers={"Content-Length": str(file_size), "Content-Type": "video/mp4"}
    )


@app.post("/api/analyze-training-video")
async def analyze_training_video(
    request: Request,
    background_tasks: BackgroundTasks,
    filename: str = Form(...),
    view: str = Form("auto"),
    mode: str = Form("both"),
    handedness: str = Form("left"),
    style: str = Form("2-handed"),
    speed_factor: str = Form("auto"),
    auto_drive_sync: bool = Form(True)
):
    """Starts analysis on an existing clip from the connected training folder."""
    if not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Unauthorized")

    source_path = TRAINING_VIDEOS_DIR / filename
    if not source_path.exists():
        raise HTTPException(status_code=404, detail="Training video not found")

    job_id = uuid.uuid4().hex
    JOBS[job_id] = {
        "job_id": job_id,
        "filename": filename,
        "status": "queued",
        "progress": 5,
        "message": f"Queued {filename} from connected training drive ({handedness}, {style})...",
        "summary": None,
        "history": [],
        "annotated_video_url": None,
        "gdrive_sync": None,
        "error": None
    }

    background_tasks.add_task(
        run_video_job, job_id, str(source_path), view, mode, handedness, style, speed_factor, auto_drive_sync
    )

    return {"job_id": job_id, "status": "queued"}
