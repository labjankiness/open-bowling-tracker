"""Tests for the comprehensive bowling ball catalog and ball detector."""

from core.ball_detector import BALL_DATABASE, get_all_balls, get_ball_info, calculate_ball_trajectory_modifier, detect_ball_from_image_crop
import numpy as np


def test_catalog_has_all_brands():
    balls = get_all_balls()
    assert len(balls) >= 1700

    brands = set(b.get("brand") for b in balls)
    for b in ["Hammer", "Storm", "Brunswick", "Motiv", "Ebonite", "Radical"]:
        assert b in brands, f"{b} should be in catalog"


def test_brands_have_current_and_retired_balls():
    balls = get_all_balls()
    for brand in ["Hammer", "Storm", "Brunswick", "Motiv", "Ebonite", "Radical"]:
        brand_balls = [b for b in balls if b.get("brand") == brand]
        statuses = set(b.get("status") for b in brand_balls)
        assert "Current" in statuses, f"{brand} should have Current balls"
        assert "Retired" in statuses, f"{brand} should have Retired balls"
        assert len(brand_balls) >= 100, f"{brand} should have at least 100 models"


def test_specific_ball_specs():
    # Storm Phaze II
    phaze2 = get_ball_info("storm_phaze_2")
    assert phaze2["name"] == "Storm Phaze II"
    assert phaze2["brand"] == "Storm"
    assert phaze2["rg"] == 2.48
    assert phaze2["diff"] == 0.051

    # Hammer Black Widow 2.0 Hybrid
    widow = get_ball_info("hammer_black_widow_2_0_hybrid")
    assert "Black Widow" in widow["name"]
    assert widow["brand"] == "Hammer"
    assert widow["rg"] == 2.50
    assert widow["diff"] == 0.058


def test_trajectory_modifier():
    # Asymmetric high flare ball
    mod_asym = calculate_ball_trajectory_modifier("hammer_black_widow_2_0_hybrid")
    assert mod_asym["flare_potential"] > 5.0
    assert mod_asym["hook_multiplier"] >= 1.0

    # Urethane ball (lower hook multiplier, early roll)
    mod_urethane = calculate_ball_trajectory_modifier("hammer_purple_pearl_urethane")
    assert mod_urethane["hook_multiplier"] < 1.0
    assert "Urethane" in mod_urethane["reaction_shape"] or "Early" in mod_urethane["reaction_shape"]


def test_color_detection_empty_fallback():
    # Empty crop fallback
    empty_crop = np.zeros((0, 0, 3), dtype=np.uint8)
    res = detect_ball_from_image_crop(empty_crop)
    assert res["confidence"] == 0.0
    assert "Standard Reactive" in res["name"]
