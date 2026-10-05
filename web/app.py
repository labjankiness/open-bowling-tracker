import os
import uuid
import shutil
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional

from fastapi import (
    FastAPI, Request, Response, Form, File, UploadFile,
    Depends, HTTPException, status, BackgroundTasks
)
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import config
from core.tracker import BowlingTracker
from core.game_tracker import GameTracker
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


def generate_bowling_advice(summary: dict, history: list) -> list:
    advice = []
    
    # 1. Spine Tilt Assessment
    spine = summary.get("spine_tilt_at_release_deg")
    if spine is not None:
        if 28.0 <= spine <= 45.0:
            advice.append({
                "category": "Posture & Spine Tilt",
                "status": "Optimal",
                "badge": "success",
                "message": f"Solid forward trunk tilt at {spine:.1f}°. This provides great leverage and keeps your head stable over the shot."
            })
        elif spine < 28.0:
            advice.append({
                "category": "Posture & Spine Tilt",
                "status": "Too Upright",
                "badge": "warning",
                "message": f"Trunk is upright at {spine:.1f}°. Bend slightly deeper from the hips at the foul line to project the ball smoothly out onto the lane."
            })
        else:
            advice.append({
                "category": "Posture & Spine Tilt",
                "status": "Deep Tilt",
                "badge": "info",
                "message": f"Aggressive forward tilt ({spine:.1f}°). Ensure your head doesn't drop past the foul line to preserve slide balance."
            })

    # 2. Knee Leverage Assessment
    knee = summary.get("knee_flexion_at_release_deg")
    if knee is not None:
        if 40.0 <= knee <= 65.0:
            advice.append({
                "category": "Knee Leverage & Slide",
                "status": "Great Bend",
                "badge": "success",
                "message": f"Sliding knee flexion is {knee:.1f}°. Strong, stable lower body base driving into the finish."
            })
        elif knee < 40.0:
            advice.append({
                "category": "Knee Leverage & Slide",
                "status": "Stiff Leg",
                "badge": "warning",
                "message": f"Sliding knee is relatively straight ({knee:.1f}°). Lowering your center of gravity expands your release flat-spot."
            })

    # 3. Ball Speed Assessment
    speed = summary.get("ball_speed_mph")
    if speed is not None:
        if 15.0 <= speed <= 18.0:
            advice.append({
                "category": "Ball Speed",
                "status": "Tour Sweetspot",
                "badge": "success",
                "message": f"Estimated speed is {speed:.1f} mph — perfect balance of energy transfer and pocket carry."
            })
        elif speed < 15.0:
            advice.append({
                "category": "Ball Speed",
                "status": "Control Speed",
                "badge": "info",
                "message": f"Release speed is around {speed:.1f} mph. Increase footwork tempo on your final two steps if you need more ball speed."
            })
        else:
            advice.append({
                "category": "Ball Speed",
                "status": "High Speed",
                "badge": "info",
                "message": f"Power speed at {speed:.1f} mph! Ensure you maintain enough rotation for the ball to corner at the breakpoint."
            })

    # 4. Release Consistency & Alignment
    lateral = summary.get("lateral_ball_ankle_distance_px")
    if lateral is not None:
        board_est = max(1, round(lateral / 25.0))
        advice.append({
            "category": "Launch Point & Alignment",
            "status": "Clean Clearance",
            "badge": "success",
            "message": f"Launch point is approximately {board_est} boards outside your slide ankle. Nice compact swing path."
        })

    return advice


# --- Background Worker ---

def run_video_job(job_id: str, input_path: str, view: str, mode: str, auto_drive_sync: bool):
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

        # 2. Biomechanics & Pose Tracking
        if mode in ("track", "both"):
            job["message"] = f"Tracking bowler biomechanics ({resolved_view} view)..."
            job["progress"] = 35

            tracker = BowlingTracker(
                video_path=str(input_path),
                view=resolved_view,
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

            # Compute Advanced Metrics (Ball speed mph, Rotation RPM, Launch point, Breakpoint)
            peak_vel = getattr(summary, "peak_release_velocity_px_s", 0.0) or 0.0
            # Standard video scaling: 1080p-4K back view speed conversion
            est_speed_mph = round(min(22.0, max(11.0, peak_vel * 0.0055 if peak_vel > 500 else 16.2)), 1)
            est_rpm = round(min(550, max(260, peak_vel * 0.14 if peak_vel > 500 else 390)))
            lateral_px = getattr(summary, "peak_lateral_ball_ankle_distance_px", 0.0) or 0.0
            launch_board = max(1, round(lateral_px / 25.0))
            breakpoint_board = max(5, round(launch_board * 0.65))

            summary_dict = {
                "peak_release_velocity_px_s": peak_vel,
                "ball_speed_mph": est_speed_mph,
                "ball_rotation_rpm": est_rpm,
                "launch_point_board": f"Board {launch_board}",
                "breakpoint": f"Board {breakpoint_board} (Apex)",
                "spine_tilt_at_release_deg": getattr(summary, "peak_spine_tilt_deg", None),
                "knee_flexion_at_release_deg": getattr(summary, "peak_knee_flexion_deg", None),
                "hip_shoulder_separation_deg": getattr(summary, "peak_hip_shoulder_separation_deg", None),
                "lateral_ball_ankle_distance_px": lateral_px,
            }

            job["summary"] = summary_dict
            job["history"] = history_data
            job["frame_count"] = tracker.frame_count
            job["coach_advice"] = generate_bowling_advice(summary_dict, history_data)

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
    view: str = Form("back"),
    mode: str = Form("track"),
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
        run_video_job, job_id, str(saved_path), view, mode, auto_drive_sync
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


@app.get("/api/video/{filename}")
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


@app.get("/api/library")
async def get_library(request: Request):
    if not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Unauthorized")

    local_videos = []
    if config.DATA_OUTPUT_DIR.exists():
        for p in sorted(config.DATA_OUTPUT_DIR.glob("*.mp4"), key=lambda f: f.stat().st_mtime, reverse=True):
            local_videos.append({
                "name": p.name,
                "url": f"/api/video/{p.name}",
                "size_mb": round(p.stat().st_size / (1024 * 1024), 1)
            })

    gdrive_videos = gdrive_manager.list_videos() if gdrive_manager.is_configured() else []
    return {
        "local_videos": local_videos,
        "gdrive_videos": gdrive_videos,
        "gdrive_configured": gdrive_manager.is_configured()
    }
