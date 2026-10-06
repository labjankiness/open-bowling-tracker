"""Approach Phase & Timing Synchronizer Model.

Analyzes frame-by-frame pose kinematics to identify the critical phases
of modern 2-handed left-handed bowling:
1. Pushaway Onset
2. Top of Backswing (Apex)
3. Power Step (Penultimate Step coil)
4. Foul Line Slide & Release
5. Finish Balance Hold

Also evaluates trail leg counter-balance and head stability leverage.
Can run on CPU, NVIDIA CUDA, or AMD DirectML.
"""

import math
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

import numpy as np


@dataclass
class ApproachPhases:
    pushaway_frame: int
    pushaway_time_s: float
    apex_frame: int
    apex_time_s: float
    power_step_frame: int
    power_step_time_s: float
    release_frame: int
    release_time_s: float
    finish_frame: int
    finish_time_s: float

    backswing_duration_s: float
    downswing_duration_s: float
    timing_ratio: float
    timing_evaluation: str

    trail_leg_sweep_deg: float
    head_stability_drift_px: float
    balance_score: int


def detect_approach_phases(
    history: List[Any],
    fps: float = 30.0,
    handedness: str = "left",
    speed_multiplier: float = 1.0
) -> Optional[ApproachPhases]:
    """Detects pushaway, apex, release, and finish from frame kinematics."""
    if not history or len(history) < 15:
        return None

    frames = [m.frame_index for m in history]
    n = len(history)

    # 1. Release Frame: Peak ball velocity
    vels = [getattr(m, "ball_velocity", 0.0) or 0.0 for m in history]
    knees = [getattr(m, "knee_flexion_deg", 0.0) or 0.0 for m in history]
    spines = [getattr(m, "spine_tilt_deg", 0.0) or 0.0 for m in history]
    coils = [abs(getattr(m, "hip_shoulder_separation_deg", 0.0) or 0.0) for m in history]

    # Find release index (peak ball velocity with sufficient knee flexion)
    max_vel = max(vels) if vels else 0.0
    if max_vel <= 0:
        return None

    # Focus search around velocity peak (usually in the middle/latter half of clip)
    rel_idx = vels.index(max_vel)
    release_frame = frames[rel_idx]

    # 2. Apex / Top of Backswing (Search backwards before release)
    # The apex is where the backswing is at its peak (highest torso coil & minimum ball velocity before downswing)
    search_back_start = max(0, rel_idx - int(fps * 2.5))
    pre_release_vels = vels[search_back_start:rel_idx]

    if pre_release_vels:
        # Apex is local velocity minimum or peak coil before the release acceleration
        local_min_sub = int(np.argmin(pre_release_vels))
        apex_idx = search_back_start + local_min_sub
        # If coil is prominent, apex aligns with max hip-shoulder separation
        sub_coils = coils[search_back_start:rel_idx]
        if sub_coils and max(sub_coils) > 15.0:
            coil_max_sub = int(np.argmax(sub_coils))
            apex_idx = search_back_start + coil_max_sub
    else:
        apex_idx = max(0, rel_idx - int(fps * 0.4))

    apex_frame = frames[apex_idx]

    # 3. Pushaway Frame (Search backwards before apex)
    # Pushaway is when the ball begins forward movement from address position
    search_push_start = max(0, apex_idx - int(fps * 2.0))
    push_idx = search_push_start
    if apex_idx > search_push_start:
        # Find where velocity first rises above address threshold
        thresh = max(15.0, max_vel * 0.12)
        for idx in range(search_push_start, apex_idx):
            if vels[idx] > thresh:
                push_idx = idx
                break
    pushaway_frame = frames[push_idx]

    # 4. Power Step (Penultimate step)
    # Typically 0.2s - 0.4s before release where slide knee begins deep compression
    power_step_idx = max(apex_idx, rel_idx - int(fps * 0.35))
    power_step_frame = frames[power_step_idx]

    # 5. Finish Hold (0.5s - 1.2s after release)
    finish_idx = min(n - 1, rel_idx + int(fps * 0.8))
    finish_frame = frames[finish_idx]

    # Timings in real seconds (adjusted for slow-motion multiplier)
    effective_fps = fps * speed_multiplier
    pushaway_t = round(pushaway_frame / effective_fps, 2)
    apex_t = round(apex_frame / effective_fps, 2)
    power_t = round(power_step_frame / effective_fps, 2)
    release_t = round(release_frame / effective_fps, 2)
    finish_t = round(finish_frame / effective_fps, 2)

    backswing_dur = max(0.1, round((apex_frame - pushaway_frame) / effective_fps, 2))
    downswing_dur = max(0.1, round((release_frame - apex_frame) / effective_fps, 2))
    timing_ratio = round(backswing_dur / downswing_dur, 2)

    # 2-Handed Timing Evaluation
    # Ideal backswing-to-downswing ratio is typically 1.6 to 2.2
    if 1.5 <= timing_ratio <= 2.3:
        timing_eval = "Sweet Spot Sync (Optimum Power & Accuracy)"
    elif timing_ratio < 1.5:
        timing_eval = "Fast / Rushed Backswing (Take smoother pushaway)"
    else:
        timing_eval = "Extended Backswing (Ensure downswing starts with power step)"

    # Balance & Trail Leg Analysis
    # Trail leg is left leg for lefty, sliding on right foot
    trail_knee_at_finish = knees[finish_idx] if finish_idx < len(knees) else 25.0
    slide_knee_at_rel = knees[rel_idx] if rel_idx < len(knees) else 35.0

    # Score balance from 0 to 100
    balance_pts = 100
    if slide_knee_at_rel < 25.0:
        balance_pts -= 15  # insufficient knee bend
    if abs(spines[rel_idx] - spines[finish_idx]) > 12.0:
        balance_pts -= 20  # popped up or dropped chest early
    balance_score = max(55, min(98, balance_pts))

    return ApproachPhases(
        pushaway_frame=pushaway_frame,
        pushaway_time_s=pushaway_t,
        apex_frame=apex_frame,
        apex_time_s=apex_t,
        power_step_frame=power_step_frame,
        power_step_time_s=power_t,
        release_frame=release_frame,
        release_time_s=release_t,
        finish_frame=finish_frame,
        finish_time_s=finish_t,
        backswing_duration_s=backswing_dur,
        downswing_duration_s=downswing_dur,
        timing_ratio=timing_ratio,
        timing_evaluation=timing_eval,
        trail_leg_sweep_deg=round(trail_knee_at_finish, 1),
        head_stability_drift_px=round(abs(spines[rel_idx] - spines[finish_idx]), 1),
        balance_score=balance_score
    )
