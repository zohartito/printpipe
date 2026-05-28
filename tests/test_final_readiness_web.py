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
    assert view["actions"][0]["record_command"] == ""
    assert view["actions"][0]["coupon_stl_path"].endswith(
        "physical_validation_coupon_40x15x3.stl"
    )
    assert view["actions"][0]["handoff_markdown_path"].endswith(
        "physical_print_handoff.md"
    )
    assert view["pillars"][0]["headline"].startswith("0/3 material families")
    assert "0/3 trusted users" in view["pillars"][1]["headline"]
    assert "not-run packet" in view["pillars"][1]["headline"]


def test_build_final_readiness_view_keeps_row_record_after_print_command() -> None:
    view = build_final_readiness_view(
        {
            "overall_status": "action_required",
            "action_count": 1,
            "proof_boundary": "A final plan is not evidence.",
            "sections": [
                {
                    "id": "physical_validation",
                    "label": "Physical validation",
                    "status": "action_required",
                    "action_count": 1,
                    "actions": [
                        {
                            "family": "pla",
                            "status": "recorded_but_not_passed",
                            "detail": "print first, then record",
                            "command": "printpipe open-folder runs/pla --target run",
                            "record_command": "printpipe record-physical-evidence runs/pla",
                            "coupon_stl_path": "runs/pla/40_geometry/coupon.stl",
                            "bundle_path": "runs/pla/60_bundle/coupon.3mf",
                            "bundle_validation_path": "runs/pla/60_bundle/coupon_validation.json",
                            "slice_result_path": "runs/pla/70_slice/slice_result.json",
                        }
                    ],
                }
            ],
        }
    )

    assert view["actions"][0]["command"] == "printpipe open-folder runs/pla --target run"
    assert view["actions"][0]["record_command"] == (
        "printpipe record-physical-evidence runs/pla"
    )
    assert view["actions"][0]["bundle_path"] == "runs/pla/60_bundle/coupon.3mf"
    assert view["actions"][0]["bundle_validation_path"] == (
        "runs/pla/60_bundle/coupon_validation.json"
    )
    assert view["actions"][0]["slice_result_path"] == (
        "runs/pla/70_slice/slice_result.json"
    )


def test_build_final_readiness_view_keeps_trusted_user_supporting_paths_and_record_command() -> None:
    view = build_final_readiness_view(
        {
            "overall_status": "action_required",
            "action_count": 1,
            "proof_boundary": "A final plan is not evidence.",
            "sections": [
                {
                    "id": "trusted_user_beta",
                    "label": "Trusted-user beta",
                    "status": "action_required",
                    "action_count": 1,
                    "actions": [
                        {
                            "slot": 1,
                            "status": "action_required",
                            "detail": "review run, then record",
                            "start_command": "printpipe beta-feedback-start runs/demo",
                            "record_command": "printpipe record-beta-feedback runs/demo",
                            "handoff_markdown_path": (
                                "runs/demo/90_beta/"
                                "trusted_user_feedback_handoff_maya.md"
                            ),
                            "report_path": "runs/demo/80_reports/run_report.html",
                            "bundle_path": "runs/demo/60_bundle/demo.3mf",
                        }
                    ],
                }
            ],
        }
    )

    action = view["actions"][0]
    assert action["command"] == "printpipe beta-feedback-start runs/demo"
    assert action["record_command"] == "printpipe record-beta-feedback runs/demo"
    assert action["handoff_markdown_path"].endswith(
        "trusted_user_feedback_handoff_maya.md"
    )
    assert action["report_path"] == "runs/demo/80_reports/run_report.html"
    assert action["bundle_path"] == "runs/demo/60_bundle/demo.3mf"


def test_build_final_readiness_view_keeps_release_commands_and_required_inputs() -> None:
    view = build_final_readiness_view(
        {
            "overall_status": "action_required",
            "action_count": 1,
            "proof_boundary": "A final plan is not evidence.",
            "sections": [
                {
                    "id": "release_distribution",
                    "label": "Release distribution",
                    "status": "action_required",
                    "action_count": 1,
                    "actions": [
                        {
                            "id": "macos_distribution",
                            "label": "macOS distribution",
                            "status": "action_required",
                            "detail": "sign and notarize",
                            "start_command": "printpipe release-start --release-dir dist/release",
                            "setup_command": "printpipe build-windows-standalone --output dist/release/PrintPipe-Windows-standalone.zip --json",
                            "command": "printpipe build-release --developer-id-identity '<id>'",
                            "followup_command": "printpipe release-status --strict",
                            "handoff_markdown_path": (
                                "dist/release_handoffs/"
                                "release_distribution_handoff.md"
                            ),
                            "required_inputs": [
                                "Developer ID Application certificate",
                                "notarytool keychain profile",
                            ],
                        }
                    ],
                }
            ],
        }
    )

    action = view["actions"][0]
    assert action["command"] == "printpipe release-start --release-dir dist/release"
    assert action["setup_command"] == (
        "printpipe build-windows-standalone --output "
        "dist/release/PrintPipe-Windows-standalone.zip --json"
    )
    assert action["run_command"] == (
        "printpipe build-release --developer-id-identity '<id>'"
    )
    assert action["followup_command"] == "printpipe release-status --strict"
    assert action["required_inputs"] == [
        "Developer ID Application certificate",
        "notarytool keychain profile",
    ]
    assert action["handoff_markdown_path"].endswith(
        "release_distribution_handoff.md"
    )


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
                    "command": "printpipe open-folder runs/pla --target run",
                    "record_command": "printpipe record-physical-evidence runs/pla",
                    "coupon_stl_path": (
                        "runs/pla/40_geometry/"
                        "physical_validation_coupon_40x15x3.stl"
                    ),
                    "bundle_path": "runs/pla/60_bundle/coupon.3mf",
                    "bundle_validation_path": "runs/pla/60_bundle/coupon_validation.json",
                    "slice_result_path": "runs/pla/70_slice/slice_result.json",
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
    assert "Bundle:" in html
    assert "runs/pla/60_bundle/coupon.3mf" in html
    assert "Bundle validation:" in html
    assert "runs/pla/60_bundle/coupon_validation.json" in html
    assert "Slice receipt:" in html
    assert "runs/pla/70_slice/slice_result.json" in html
    assert "Handoff:" in html
    assert "physical_print_handoff.md" in html
    assert "PLA physical validation" in html
    assert html.count("Record after print:") == 2
    assert "final-readiness-checklist" in html
    assert 'href="/final-next.json"' in html


def test_render_final_readiness_panel_links_run_artifact_paths() -> None:
    html = render_final_readiness_panel(
        {
            "overall_status": "action_required",
            "action_count": 1,
            "proof_boundary": "A final plan is not evidence.",
            "next_action": {
                "section_label": "Physical validation",
                "label": "PLA",
                "status": "recorded_but_not_passed",
                "detail": "print then record",
                "command": "printpipe open-folder runs/physical-pla-validation --target run",
                "coupon_stl_path": (
                    "/Users/zohartito/Desktop/printpipe/runs/"
                    "physical-pla-validation/40_geometry/coupon.stl"
                ),
                "handoff_markdown_path": (
                    "runs/physical-pla-validation/90_physical/"
                    "physical_print_handoff.md"
                ),
            },
            "pillars": [],
            "actions": [
                {
                    "section_label": "Trusted-user beta",
                    "label": "Trusted-user feedback (tester slot 1)",
                    "detail": "review then record",
                    "status": "action_required",
                    "report_path": (
                        "/Users/zohartito/Desktop/printpipe/runs/"
                        "run demo/80_reports/run_report.html"
                    ),
                    "bundle_path": "runs/run demo/60_bundle/demo file.3mf",
                    "handoff_markdown_path": (
                        "/Users/zohartito/Desktop/printpipe/dist/"
                        "release_handoffs/release_distribution_handoff.md"
                    ),
                }
            ],
        }
    )

    assert (
        'href="/runs/physical-pla-validation/artifacts/40_geometry/coupon.stl"'
        in html
    )
    assert (
        'href="/runs/physical-pla-validation/artifacts/90_physical/physical_print_handoff.md"'
        in html
    )
    assert 'href="/runs/run%20demo/artifacts/80_reports/run_report.html"' in html
    assert 'href="/runs/run%20demo/artifacts/60_bundle/demo%20file.3mf"' in html
    assert "/runs/release_handoffs" not in html
    assert "release_distribution_handoff.md" in html


def test_render_final_readiness_panel_next_action_shows_release_commands() -> None:
    html = render_final_readiness_panel(
        {
            "overall_status": "action_required",
            "action_count": 1,
            "proof_boundary": "A final plan is not evidence.",
            "next_action": {
                "section_id": "release_distribution",
                "section_label": "Release distribution",
                "label": "macOS distribution",
                "status": "action_required",
                "detail": "sign and notarize",
                "command": "printpipe release-start --release-dir dist/release",
                "setup_command": "printpipe build-windows-standalone --output dist/release/PrintPipe-Windows-standalone.zip --json",
                "run_command": "printpipe build-release --developer-id-identity '<id>'",
                "followup_command": "printpipe release-status --strict",
                "required_inputs": [
                    "Developer ID Application certificate",
                    "notarytool keychain profile",
                ],
                "handoff_markdown_path": (
                    "dist/release_handoffs/"
                    "release_distribution_handoff.md"
                ),
            },
            "pillars": [],
            "actions": [],
        }
    )

    assert "Next action:" in html
    assert "Next action required inputs:" in html
    assert "Developer ID Application certificate" in html
    assert "Setup prerequisite:" in html
    assert "printpipe build-windows-standalone --output" in html
    assert "Run after prerequisites:" in html
    assert "printpipe build-release --developer-id-identity" in html
    assert "Follow-up check:" in html
    assert "printpipe release-status --strict" in html
    assert "Next action handoff:" in html
    assert "release_distribution_handoff.md" in html


def test_render_final_readiness_panel_labels_trusted_user_record_command_after_review() -> None:
    html = render_final_readiness_panel(
        {
            "overall_status": "action_required",
            "action_count": 1,
            "proof_boundary": "A final plan is not evidence.",
            "pillars": [],
            "actions": [
                {
                    "section_id": "trusted_user_beta",
                    "section_label": "Trusted-user beta",
                    "label": "Trusted-user feedback (tester slot 1)",
                    "detail": "review run, then record",
                    "status": "action_required",
                    "command": "printpipe beta-feedback-start runs/demo",
                    "record_command": "printpipe record-beta-feedback runs/demo",
                    "handoff_markdown_path": (
                        "runs/demo/90_beta/"
                        "trusted_user_feedback_handoff_maya.md"
                    ),
                    "report_path": "runs/demo/80_reports/run_report.html",
                    "bundle_path": "runs/demo/60_bundle/demo.3mf",
                }
            ],
        }
    )

    assert "Report:" in html
    assert "runs/demo/80_reports/run_report.html" in html
    assert "Bundle:" in html
    assert "runs/demo/60_bundle/demo.3mf" in html
    assert "Handoff:" in html
    assert "trusted_user_feedback_handoff_maya.md" in html
    assert "Record after review:" in html
    assert "printpipe record-beta-feedback runs/demo" in html
    assert "Record after print:" not in html


def test_render_final_readiness_panel_shows_release_commands_and_required_inputs() -> None:
    html = render_final_readiness_panel(
        {
            "overall_status": "action_required",
            "action_count": 1,
            "proof_boundary": "A final plan is not evidence.",
            "pillars": [],
            "actions": [
                {
                    "section_id": "release_distribution",
                    "section_label": "Release distribution",
                    "label": "macOS distribution",
                    "detail": "sign and notarize",
                    "status": "action_required",
                    "command": "printpipe release-start --release-dir dist/release",
                    "setup_command": "printpipe build-windows-standalone --output dist/release/PrintPipe-Windows-standalone.zip --json",
                    "run_command": "printpipe build-release --developer-id-identity '<id>'",
                    "followup_command": "printpipe release-status --strict",
                    "handoff_markdown_path": (
                        "dist/release_handoffs/"
                        "release_distribution_handoff.md"
                    ),
                    "required_inputs": [
                        "Developer ID Application certificate",
                        "notarytool keychain profile",
                    ],
                }
            ],
        }
    )

    assert "Required inputs:" in html
    assert "Developer ID Application certificate" in html
    assert "notarytool keychain profile" in html
    assert "Setup prerequisite:" in html
    assert "printpipe build-windows-standalone --output" in html
    assert "Run after prerequisites:" in html
    assert "printpipe build-release --developer-id-identity" in html
    assert "Follow-up check:" in html
    assert "printpipe release-status --strict" in html
    assert "Handoff:" in html
    assert "release_distribution_handoff.md" in html
