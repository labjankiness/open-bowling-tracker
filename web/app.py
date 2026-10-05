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
        with PoseEstimator(fps=fps) as estimator:
            checked = 0
            shoulder_widths = []
            while checked < 45:
                ok, frame = capture.read()
                if not ok:
                    break
                landmarks = estimator.process(frame)
                if landmarks is not None:
                    ls = landmarks.left_shoulder
                    rs = landmarks.right_shoulder
                    if ls is not None and rs is not None:
                        shoulder_widths.append(abs(ls[0] - rs[0]))
                checked += 1
            capture.release()
            if shoulder_widths:
                avg_width = sum(shoulder_widths) / len(shoulder_widths)
                if avg_width < 0.07:
                    return "side"
    except Exception as e:
        print(f"[AutoDetect] Camera view fallback to 'back': {e}")
    return "back"


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
                    "ball_velocity_px_s": m.ball_velocity_px_s,
                    "spine_tilt_deg": m.spine_tilt_deg,
                    "knee_flexion_deg": m.knee_flexion_deg
                }
                for m in tracker.history
            ]

            job["summary"] = {
                "peak_release_velocity_px_s": summary.peak_release_velocity_px_s,
                "spine_tilt_at_release_deg": summary.spine_tilt_at_release_deg,
                "knee_flexion_at_release_deg": summary.knee_flexion_at_release_deg,
                "hand_speed_at_release_px_s": summary.hand_speed_at_release_px_s,
            }
            job["history"] = history_data
            job["frame_count"] = tracker.frame_count

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

        job["annotated_video_url"] = f"/api/video/{output_filename}" if annotated_path.exists() else None
        job["progress"] = 85

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
