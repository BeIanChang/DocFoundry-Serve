from pathlib import Path

from app.router.policy_router import PolicyRouter


def test_stage_aware_policy_resolution():
    cfg = Path(__file__).resolve().parents[1] / "config" / "policies.yaml"
    router = PolicyRouter(config_path=cfg, default_mode="stage_aware")

    decision = router.resolve("planning")
    assert decision.mode == "stage_aware"
    assert decision.name == "planning_fast"
    assert int(decision.generation.get("max_tokens") or 0) <= 128


def test_baseline_override_policy_resolution():
    cfg = Path(__file__).resolve().parents[1] / "config" / "policies.yaml"
    router = PolicyRouter(config_path=cfg, default_mode="stage_aware")

    decision = router.resolve("refinement", mode="baseline")
    assert decision.mode == "baseline"
    assert decision.name == "shared_balanced"
