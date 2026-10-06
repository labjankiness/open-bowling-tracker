"""Bowling Ball Spec Database and Automatic/Manual Ball Detector.

Provides:
1. BALL_DATABASE: Known popular bowling balls with coverstock, core type, RG, Diff, and dominant color signatures.
2. detect_bowling_ball_from_crop: HSV color matching to predict which bowling ball was used.
3. calculate_ball_trajectory_modifier: Adjusts hook potential and entry angle predictions based on the chosen ball.
"""

from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import cv2


# Common, high-performance & popular bowling balls across Storm, Roto Grip, Hammer, Motiv, Brunswick, etc.
BALL_DATABASE: Dict[str, Dict[str, Any]] = {
    "storm_phaze_2": {
        "id": "storm_phaze_2",
        "name": "Storm Phaze II",
        "brand": "Storm",
        "coverstock": "TX-16 Solid Reactive",
        "core": "Velocity Core (Symmetrical)",
        "finish": "3000-grit Abralon",
        "rg": 2.48,
        "diff": 0.051,
        "hook_potential": "High Benchmark",
        "typical_colors": ["red", "blue", "purple"],
        "color_hsv_ranges": [
            # Red/Crimson and Royal Blue / Purple
            {"name": "red", "lower": (0, 70, 50), "upper": (10, 255, 255)},
            {"name": "purple_blue", "lower": (110, 60, 50), "upper": (145, 255, 255)},
        ]
    },
    "storm_hy_road": {
        "id": "storm_hy_road",
        "name": "Storm Hy-Road",
        "brand": "Storm",
        "coverstock": "R2S Hybrid Reactive",
        "core": "Inverted Fe² Technology (Symmetrical)",
        "finish": "1500-grit Polished",
        "rg": 2.57,
        "diff": 0.046,
        "hook_potential": "Medium Smooth",
        "typical_colors": ["black", "blue"],
        "color_hsv_ranges": [
            {"name": "dark_blue", "lower": (100, 80, 40), "upper": (130, 255, 200)},
        ]
    },
    "hammer_black_widow_2_0_hybrid": {
        "id": "hammer_black_widow_2_0_hybrid",
        "name": "Hammer Black Widow 2.0 Hybrid",
        "brand": "Hammer",
        "coverstock": "HK22 - Aggression Hybrid",
        "core": "Gas Mask (Asymmetrical)",
        "finish": "1500-grit Compound",
        "rg": 2.50,
        "diff": 0.058,
        "hook_potential": "Strong Angular Backend",
        "typical_colors": ["red", "black"],
        "color_hsv_ranges": [
            {"name": "bright_red", "lower": (0, 100, 70), "upper": (12, 255, 255)},
            {"name": "high_red", "lower": (165, 100, 70), "upper": (180, 255, 255)},
        ]
    },
    "hammer_purple_pearl_urethane": {
        "id": "hammer_purple_pearl_urethane",
        "name": "Hammer Purple Pearl Urethane",
        "brand": "Hammer",
        "coverstock": "Urethane Pearl",
        "core": "LED (Symmetrical)",
        "finish": "500 / 1000 / 2000 Siaair",
        "rg": 2.65,
        "diff": 0.015,
        "hook_potential": "Control Early Arc (Tour Standard)",
        "typical_colors": ["purple"],
        "color_hsv_ranges": [
            {"name": "purple", "lower": (125, 60, 50), "upper": (155, 255, 255)},
        ]
    },
    "roto_grip_gem": {
        "id": "roto_grip_gem",
        "name": "Roto Grip Exotic GEM / GEM",
        "brand": "Roto Grip",
        "coverstock": "MicroTrax Solid / Pearl",
        "core": "Defiant LRG (Asymmetrical Heavy Oil)",
        "finish": "2000-grit Abralon",
        "rg": 2.47,
        "diff": 0.053,
        "hook_potential": "Maximum Heavy Oil Traction",
        "typical_colors": ["teal", "green", "pink"],
        "color_hsv_ranges": [
            {"name": "teal_cyan", "lower": (80, 70, 50), "upper": (105, 255, 255)},
            {"name": "magenta_pink", "lower": (145, 80, 80), "upper": (170, 255, 255)},
        ]
    },
    "motiv_venom_shock": {
        "id": "motiv_venom_shock",
        "name": "Motiv Venom Shock",
        "brand": "Motiv",
        "coverstock": "Turmoil MFS Solid Reactive",
        "core": "Gear (Symmetrical)",
        "finish": "4000-grit LSS",
        "rg": 2.48,
        "diff": 0.034,
        "hook_potential": "Continuous Smooth Benchmark",
        "typical_colors": ["purple", "orange"],
        "color_hsv_ranges": [
            {"name": "purple", "lower": (130, 60, 50), "upper": (155, 255, 230)},
            {"name": "orange", "lower": (10, 100, 100), "upper": (25, 255, 255)},
        ]
    },
    "brunswick_tzone_spare": {
        "id": "brunswick_tzone_spare",
        "name": "Brunswick TZone / Plastic Spare Ball",
        "brand": "Brunswick / Columbia 300",
        "coverstock": "Polyester / Plastic",
        "core": "Bullet (Symmetrical low-flare)",
        "finish": "High Gloss Polish",
        "rg": 2.71,
        "diff": 0.005,
        "hook_potential": "Straight Spare (Minimal Hook)",
        "typical_colors": ["multi", "white", "blue"],
        "color_hsv_ranges": [
            {"name": "bright_cyan", "lower": (85, 40, 120), "upper": (105, 200, 255)},
        ]
    },
    "custom_generic_reactive": {
        "id": "custom_generic_reactive",
        "name": "Standard Reactive Resin Ball",
        "brand": "Standard",
        "coverstock": "Reactive Resin",
        "core": "Symmetrical",
        "finish": "Factory Standard",
        "rg": 2.52,
        "diff": 0.045,
        "hook_potential": "Balanced Medium-High",
        "typical_colors": ["all"],
        "color_hsv_ranges": []
    }
}


def get_ball_info(ball_id: Optional[str]) -> Dict[str, Any]:
    """Retrieve full ball specifications by ball_id or fallback to generic."""
    if not ball_id or ball_id not in BALL_DATABASE:
        return BALL_DATABASE["custom_generic_reactive"]
    return BALL_DATABASE[ball_id]


def detect_ball_from_image_crop(ball_crop_bgr: np.ndarray) -> Dict[str, Any]:
    """Analyzes a cropped region containing the bowling ball to predict the model.

    Uses HSV color space histograms and known ball color profile matching.
    Returns matched ball_id, ball name, confidence score (0-1), and detected color signature.
    """
    if ball_crop_bgr is None or ball_crop_bgr.size == 0 or ball_crop_bgr.shape[0] < 5 or ball_crop_bgr.shape[1] < 5:
        return {
            "ball_id": "custom_generic_reactive",
            "name": "Standard Reactive Resin Ball",
            "confidence": 0.0,
            "detected_color": "unknown",
            "details": BALL_DATABASE["custom_generic_reactive"]
        }

    # Preprocess: Gaussian blur to smooth surface reflections and lane oil sheen
    blurred = cv2.GaussianBlur(ball_crop_bgr, (7, 7), 0)
    hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)

    best_match_id = "custom_generic_reactive"
    best_score = 0.0
    detected_color = "neutral"

    # Evaluate each ball's distinctive color HSV masks
    total_pixels = float(hsv.shape[0] * hsv.shape[1])

    for ball_id, ball in BALL_DATABASE.items():
        ranges = ball.get("color_hsv_ranges", [])
        if not ranges:
            continue

        match_pixel_count = 0
        current_matched_color = None

        for color_range in ranges:
            lower = np.array(color_range["lower"], dtype=np.uint8)
            upper = np.array(color_range["upper"], dtype=np.uint8)
            mask = cv2.inRange(hsv, lower, upper)
            count = int(cv2.countNonZero(mask))
            if count > 0:
                match_pixel_count += count
                current_matched_color = color_range["name"]

        ratio = match_pixel_count / total_pixels
        if ratio > best_score and ratio >= 0.12:  # at least 12% dominant color coverage
            best_score = ratio
            best_match_id = ball_id
            if current_matched_color:
                detected_color = current_matched_color

    confidence = round(min(0.95, best_score * 1.6), 2)
    matched_ball = BALL_DATABASE.get(best_match_id, BALL_DATABASE["custom_generic_reactive"])

    return {
        "ball_id": best_match_id,
        "name": matched_ball["name"],
        "confidence": confidence,
        "detected_color": detected_color,
        "details": matched_ball
    }


def calculate_ball_trajectory_modifier(ball_id: Optional[str]) -> Dict[str, Any]:
    """Calculates flare, hook multiplier, and skid factor based on ball specs."""
    ball = get_ball_info(ball_id)
    rg = ball.get("rg", 2.52)
    diff = ball.get("diff", 0.045)
    cover = ball.get("coverstock", "").lower()

    # Lower RG revs up earlier; higher RG skids longer
    skid_factor = round(1.0 + (rg - 2.50) * 1.5, 2)

    # Higher Diff flares more and creates stronger backend change of direction
    flare_potential = round(diff * 100.0, 1)

    # Urethane vs Reactive vs Plastic hook modifier
    if "urethane" in cover:
        hook_multiplier = 0.82
        reaction_shape = "Smooth Arching / Early Roll"
    elif "plastic" in cover or "polyester" in cover:
        hook_multiplier = 0.25
        reaction_shape = "Direct Straight (Spare)"
    elif "asymmetrical" in ball.get("core", "").lower() or diff >= 0.052:
        hook_multiplier = 1.18
        reaction_shape = "Sharp Angular Backend"
    else:
        hook_multiplier = 1.0
        reaction_shape = "Balanced Benchmark Hook"

    return {
        "ball_id": ball.get("id"),
        "ball_name": ball.get("name"),
        "rg": rg,
        "diff": diff,
        "skid_factor": skid_factor,
        "flare_potential": flare_potential,
        "hook_multiplier": hook_multiplier,
        "reaction_shape": reaction_shape,
        "coverstock": ball.get("coverstock"),
        "core": ball.get("core")
    }
