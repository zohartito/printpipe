from __future__ import annotations

from printpipe.web.final_readiness import (
    build_final_readiness_view,
    render_final_readiness_panel,
)


def test_build_final_readiness_view_flattens_section_actions() -> None:
    view = build_final_readiness_view(
        {
            "overall_status": "action_required",
            "action_count": 3,
            "proof_boundary": "A final plan is not evidence.",
            "next_action": {
                "section_id": "physical_validation",
                "section_label": "Physical validation",
                "action_id": "pla",
                "label": "PLA",
                "status": "missing",
                "detail": "no packet",
                "command": "printpipe physical-start --family pla",
                "command_kind": "start_command",
                "coupon_stl_path": (
                    "runs/pla/40_geometry/"
                    "physical_validation_coupon_40x15x3.stl"
                ),
                "handoff_markdown_path": (
                    "runs/pla/90_physical/"
                    "physical_print_handoff.md"
                ),
            },
            "sections": [
                {
                    "id": "physical_validation",
                    "label": "Physical validation",
                    "status": "action_required",
                    "action_count": 1,
                    "command": "printpipe physical-plan --runs-dir runs",
                    "actions": [
                        {
                            "family": "pla",
                            "status": "missing",
                            "reason": "no physical evidence packet found",
                            "start_command": "printpipe physical-start --family pla",
                            "record_command": "printpipe record-physical-evidence runs/pla",
                            "coupon_stl_path": (
                                "runs/pla/40_geometry/"
                                "physical_validation_coupon_40x15x3.stl"
                            ),
                            "handoff_markdown_path": (
                                "runs/pla/90_physical/"
                                "physical_print_handoff.md"
                            ),
                        }
                    ],
                },
                {
                    "id": "trusted_user_beta",
                    "label": "Trusted-user beta",
                    "status": "action_required",
                    "action_count": 2,
                    "actions": [
                        {"slot": 1, "status": "missing", "detail": "slot open"},
                        {"slot": 2, "status": "missing", "detail": "slot open"},
                    ],
                },
            ],
        },
        physical_status={
            "family_status": {
                "pla": {"status": "missing"},
                "petg": {"status": "missing"},
                "tpu": {"status": "missing"},
            }
        },
        feedback_status={
            "completed_trusted_user_count": 0,
            "required_trusted_user_count": 3,
            "not_run_trusted_users": ["Lee"],
        },
    )

    assert view["action_count"] == 3
    assert view["next_action"]["command"] == "printpipe physical-start --family pla"
    assert len(view["actions"]) == 3
    assert view["actions"][0]["command"] == "printpipe physical-start --family pla"
    assert view["actions"][0]["coupon_stl_path"].endswith(
        "physical_validation_coupon_40x15x3.stl"
    )
    assert view["actions"][0]["handoff_markdown_path"].endswith(
        "physical_print_handoff.md"
    )
    assert view["pillars"][0]["headline"].startswith("0/3 material families")
    assert "0/3 trusted users" in view["pillars"][1]["headline"]
    assert "not-run packet" in view["pillars"][1]["headline"]


def test_render_final_readiness_panel_includes_honest_boundaries() -> None:
    html = render_final_readiness_panel(
        {
            "overall_status": "action_required",
            "action_count": 1,
            "proof_boundary": "A final plan is not evidence.",
            "next_action": {
                "section_label": "Physical validation",
                "label": "PLA",
                "status": "missing",
                "detail": "no packet",
                "command": "printpipe open-folder runs/pla --target run",
                "record_command": "printpipe record-physical-evidence runs/pla",
                "coupon_stl_path": (
                    "runs/pla/40_geometry/"
                    "physical_validation_coupon_40x15x3.stl"
                ),
                "handoff_markdown_path": (
                    "runs/pla/90_physical/"
                    "physical_print_handoff.md"
                ),
            },
            "pillars": [
                {
                    "id": "physical_validation",
                    "label": "Physical validation",
                    "status": "action_required",
                    "headline": "0/3 material families have credible passed physical evidence",
                    "note": "Digital coupons are not physical proof.",
                    "action_count": 1,
                    "command": "printpipe physical-plan --runs-dir runs",
                }
            ],
            "actions": [
                {
                    "section_label": "Physical validation",
                    "label": "PLA physical validation",
                    "detail": "no physical evidence packet found",
                    "status": "missing",
                    "command": "printpipe record-physical-evidence runs/pla",
                    "coupon_stl_path": (
                        "runs/pla/40_geometry/"
                        "physical_validation_coupon_40x15x3.stl"
                    ),
                    "handoff_markdown_path": (
                        "runs/pla/90_physical/"
                        "physical_print_handoff.md"
                    ),
                }
            ],
        }
    )

    assert "Final readiness / Remaining actions" in html
    assert "A final plan is not evidence." in html
    assert "Digital coupons are not physical proof." in html
    assert "Next action:" in html
    assert "printpipe open-folder runs/pla --target run" in html
    assert "Record after print:" in html
    assert "printpipe record-physical-evidence runs/pla" in html
    assert "Next action artifact:" in html
    assert "Next action handoff:" in html
    assert "Coupon artifact:" in html
    assert "physical_validation_coupon_40x15x3.stl" in html
    assert "Handoff:" in html
    assert "physical_print_handoff.md" in html
    assert "PLA physical validation" in html
    assert "final-readiness-checklist" in html
    assert 'href="/final-next.json"' in html
