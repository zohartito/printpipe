from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote

from printpipe.beta.physical import (
    PhysicalArtifact,
    build_physical_print_evidence,
    write_physical_evidence_files,
)
from printpipe.beta.physical_start import start_physical_validation
from printpipe.beta.feedback import (
    build_trusted_user_feedback,
    start_trusted_user_feedback,
    write_trusted_user_feedback_files,
)
from printpipe.config import CONFIG_PATH_ENV
from printpipe.contracts import Artifact, ArtifactKind, StageReceipt, StageStatus
from printpipe.reports import build_run_report_dict, write_run_report
from printpipe.reports.html import write_html_report
from printpipe.runs.editing import load_edit_recipe
from printpipe.runs.paths import create_run
from printpipe.web import PrintPipeWebApp, create_app
from printpipe.web import run_detail
from printpipe.web import server as web_server


def _multipart_form_body(
    *,
    fields: dict[str, str],
    file_field: str,
    filename: str,
    content_type: str,
    file_content: bytes,
) -> tuple[bytes, str]:
    boundary = "printpipe-test-boundary"
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.extend(
            [
                f"--{boundary}\r\n".encode("ascii"),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("ascii"),
                value.encode("utf-8"),
                b"\r\n",
            ]
        )
    chunks.extend(
        [
            f"--{boundary}\r\n".encode("ascii"),
            (
                f'Content-Disposition: form-data; name="{file_field}"; '
                f'filename="{filename}"\r\n'
            ).encode("ascii"),
            f"Content-Type: {content_type}\r\n\r\n".encode("ascii"),
            file_content,
            b"\r\n",
            f"--{boundary}--\r\n".encode("ascii"),
        ]
    )
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def _multipart_fields_body(fields: dict[str, str]) -> tuple[bytes, str]:
    boundary = "printpipe-test-boundary"
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.extend(
            [
                f"--{boundary}\r\n".encode("ascii"),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("ascii"),
                value.encode("utf-8"),
                b"\r\n",
            ]
        )
    chunks.append(f"--{boundary}--\r\n".encode("ascii"))
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def _write_trusted_feedback(
    run_root: Path,
    *,
    tester: str,
    outcome: str = "passed",
) -> None:
    run_root.mkdir(parents=True)
    report = run_root / "80_reports" / "run_report.html"
    report.parent.mkdir(parents=True)
    report.write_text("<h1>run report</h1>\n", encoding="utf-8")
    feedback = build_trusted_user_feedback(
        run_id=run_root.name,
        tester=tester,
        tester_type="trusted_user",
        input_type="existing_stl",
        material="Bambu PLA Basic",
        printer="Bambu Lab P2S",
        outcome=outcome,
        summary=f"{tester} completed a beta run.",
        issues=(),
        would_print="no",
        recommendation="needs_review",
        artifacts=(),
    )
    write_trusted_user_feedback_files(run_root=run_root, feedback=feedback)


def test_home_response_renders_status_and_static_page_links(tmp_path: Path):
    report = tmp_path / "run_report.html"
    report.write_text("<!doctype html><h1>Run Report</h1>\n", encoding="utf-8")

    app = create_app(static_roots=(tmp_path,))

    response = app.handle("/")

    assert response.status == 200
    assert response.header("Content-Type") == "text/html; charset=utf-8"
    assert "<!doctype html>" in response.text
    assert "PrintPipe" in response.text
    assert 'href="/static/run_report.html"' in response.text


def test_home_response_renders_launch_controls_recent_runs_and_artifacts(tmp_path: Path):
    source = tmp_path / "reference.png"
    source.write_bytes(b"fake image")
    runs_dir = tmp_path / "runs"
    layout = create_run(source, runs_dir, run_id="run-ui-001")
    bundle = layout.bundle_dir / "ready.3mf"
    bundle.write_bytes(b"bundle")
    stages = (
        StageReceipt(
            stage="slice",
            status=StageStatus.SUCCEEDED,
            message="Slice passed.",
            artifacts=(
                Artifact(
                    kind=ArtifactKind.THREEMF,
                    path=bundle,
                    label="Bambu bundle",
                ),
            ),
            metrics={"mass_g": 12.3},
        ),
    )
    report_dict = build_run_report_dict(
        layout,
        stages=stages,
        warnings=("review first layer",),
    )
    write_run_report(layout, stages=stages, warnings=("review first layer",))
    write_html_report(layout, report_dict)
    app = create_app(runs_dir=runs_dir)

    response = app.handle("/")

    assert response.status == 200
    assert "New Run" in response.text
    assert 'type="file"' in response.text
    assert 'name="prompt"' in response.text
    assert "Bambu Lab P2S" in response.text
    assert "SUNLU TPU 90A Slipper" in response.text
    assert "Prompt image provider" in response.text
    assert "Target length (mm)" in response.text
    assert "run-ui-001" in response.text
    assert "succeeded" in response.text
    assert "Open report" in response.text
    assert 'href="/static/run-ui-001/80_reports/run_report.html"' in response.text
    assert 'href="/runs/run-ui-001"' in response.text
    assert "Open workbench" in response.text
    assert 'href="/runs/run-ui-001/artifacts/60_bundle/ready.3mf"' in response.text
    assert 'href="/readiness.json"' in response.text
    assert 'href="/release-status.json"' in response.text
    assert 'href="/physical-plan.json"' in response.text
    assert 'href="/beta-feedback-status.json"' in response.text
    assert 'href="/beta-plan.json"' in response.text
    assert 'href="/doctor.json"' in response.text


def test_home_recent_run_card_surfaces_print_verdict_before_bundle_download(tmp_path: Path):
    source = tmp_path / "reference.png"
    source.write_bytes(b"fake image")
    runs_dir = tmp_path / "runs"
    layout = create_run(source, runs_dir, run_id="run-review-before-print")
    bundle = layout.bundle_dir / "ready.3mf"
    bundle.write_bytes(b"bundle")
    stages = (
        StageReceipt(
            stage="slice",
            status=StageStatus.SUCCEEDED,
            message="Slice passed with warnings.",
            artifacts=(
                Artifact(
                    kind=ArtifactKind.THREEMF,
                    path=bundle,
                    label="Bambu bundle",
                ),
            ),
            metrics={
                "fits": True,
                "watertight": True,
                "non_manifold_edges": 0,
                "boundary_edges": 0,
                "slice_success": True,
                "support_risk": "low",
            },
        ),
    )
    report_dict = build_run_report_dict(
        layout,
        stages=stages,
        warnings=("review first layer",),
    )
    write_run_report(layout, stages=stages, warnings=("review first layer",))
    write_html_report(layout, report_dict)
    app = create_app(runs_dir=runs_dir)

    response = app.handle("/")

    assert response.status == 200
    assert '<section class="run-print-verdict run-print-verdict-review">' in response.text
    assert "Review before print" in response.text
    assert "Warnings remain, but no blocking validation checks failed." in response.text
    assert response.text.find("Review before print") < response.text.find("Downloads")
    assert (
        response.text.find("Review before print")
        < response.text.find('download="ready.3mf"')
    )


def test_home_response_renders_physical_beta_gate_status(tmp_path: Path):
    runs_dir = tmp_path / "runs"
    pla_run = runs_dir / "run-pla-pass"
    pla_run.mkdir(parents=True)
    photo = pla_run / "coupon.jpg"
    photo.write_bytes(b"photo")
    write_physical_evidence_files(
        run_root=pla_run,
        evidence=build_physical_print_evidence(
            run_id="run-pla-pass",
            material="Bambu PLA Basic",
            printer="Bambu Lab P2S",
            object_label="validation coupon",
            print_type="coupon",
            print_status="passed",
            operator="Zohar",
            first_layer="clean first layer",
            adhesion="held through print",
            artifacts=(PhysicalArtifact(label="Coupon photo", path=photo, kind="photo"),),
        ),
        copy_artifacts=True,
    )
    tpu_run = runs_dir / "run-tpu-failed"
    tpu_run.mkdir(parents=True)
    tpu_photo = tpu_run / "coupon.jpg"
    tpu_photo.write_bytes(b"photo")
    write_physical_evidence_files(
        run_root=tpu_run,
        evidence=build_physical_print_evidence(
            run_id="run-tpu-failed",
            material="SUNLU TPU 90A",
            printer="Bambu Lab P2S",
            object_label="validation coupon",
            print_type="coupon",
            print_status="failed",
            operator="Zohar",
            filament_drying="50 C for 6 h",
            layer_bonding="split at layer 12",
            flex_recovery="not tested because print failed",
            artifacts=(PhysicalArtifact(label="Coupon photo", path=tpu_photo, kind="photo"),),
        ),
        copy_artifacts=True,
    )
    app = create_app(runs_dir=runs_dir)

    response = app.handle("/")

    assert response.status == 200
    assert "Physical beta gate" in response.text
    assert "missing_passed_evidence" in response.text
    assert "PLA" in response.text
    assert "PETG" in response.text
    assert "TPU" in response.text
    assert "passed" in response.text
    assert "missing" in response.text
    assert "recorded_but_not_passed" in response.text
    assert "printpipe physical-status --runs-dir" in response.text


def test_physical_status_json_endpoint_returns_beta_gate_status(tmp_path: Path):
    runs_dir = tmp_path / "runs"
    pla_run = runs_dir / "run-pla-pass"
    pla_run.mkdir(parents=True)
    photo = pla_run / "coupon.jpg"
    photo.write_bytes(b"photo")
    write_physical_evidence_files(
        run_root=pla_run,
        evidence=build_physical_print_evidence(
            run_id="run-pla-pass",
            material="Bambu PLA Basic",
            printer="Bambu Lab P2S",
            object_label="validation coupon",
            print_type="coupon",
            print_status="passed",
            operator="Zohar",
            first_layer="clean first layer",
            adhesion="held through print",
            artifacts=(PhysicalArtifact(label="Coupon photo", path=photo, kind="photo"),),
        ),
        copy_artifacts=True,
    )
    app = create_app(runs_dir=runs_dir)

    response = app.handle("/physical-status.json")

    payload = json.loads(response.text)
    assert response.status == 200
    assert response.header("Content-Type") == "application/json; charset=utf-8"
    assert payload["overall_status"] == "missing_passed_evidence"
    assert payload["family_status"]["pla"]["status"] == "passed"
    assert payload["family_status"]["petg"]["status"] == "missing"
    assert payload["family_status"]["tpu"]["status"] == "missing"


def test_physical_plan_json_endpoint_returns_action_plan(tmp_path: Path):
    app = create_app(runs_dir=tmp_path / "runs")

    response = app.handle("/physical-plan.json")

    payload = json.loads(response.text)
    assert response.status == 200
    assert response.header("Content-Type") == "application/json; charset=utf-8"
    assert payload["overall_status"] == "action_required"
    assert payload["action_count"] == 3
    assert payload["actions"][0]["family"] == "pla"
    assert "record-physical-evidence" in payload["actions"][0]["record_command"]
    assert "Digital artifacts" in payload["proof_boundary"]


def test_home_response_renders_physical_action_plan(tmp_path: Path):
    app = create_app(runs_dir=tmp_path / "runs")

    response = app.handle("/")

    assert response.status == 200
    assert "Physical action plan" in response.text
    assert "3 action required" in response.text
    assert "Digital artifacts, generated coupons, and slice receipts do not count" in response.text
    assert "PLA" in response.text
    assert "PETG" in response.text
    assert "TPU" in response.text
    assert "mkdir -p" in response.text
    assert "printpipe physical-start" in response.text
    assert "printpipe record-physical-evidence" in response.text
    assert "printpipe physical-plan --runs-dir runs" in response.text


def test_home_response_renders_physical_start_form(tmp_path: Path):
    app = create_app(runs_dir=tmp_path / "runs")

    response = app.handle("/")

    assert response.status == 200
    assert 'action="/physical/start"' in response.text
    assert 'name="family" value="pla"' in response.text
    assert 'name="operator" value="Zohar"' in response.text


def test_post_physical_start_creates_starter_packet_and_redirects(tmp_path: Path):
    runs_dir = tmp_path / "runs"
    app = create_app(runs_dir=runs_dir)

    response = app.handle(
        "/physical/start",
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        body=b"family=pla&operator=Zohar",
    )

    run_root = runs_dir / "physical-pla-validation"
    evidence_path = run_root / "90_physical" / "physical_evidence.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert response.status == 303
    assert response.header("Location") == "/#physical-action-plan"
    assert evidence["print_status"] == "not_printed"
    assert evidence["operator"] == "Zohar"
    assert (run_root / "40_geometry" / "physical_validation_coupon_40x15x3.stl").exists()
    assert (run_root / "60_bundle" / "physical_validation_coupon_40x15x3.3mf").exists()


def test_home_response_renders_started_physical_action_context_and_files(
    tmp_path: Path,
) -> None:
    runs_dir = tmp_path / "runs"
    result = start_physical_validation(
        runs_dir,
        family="pla",
        operator="Zohar",
    )
    run_root = runs_dir / "physical-pla-validation"
    app = create_app(runs_dir=runs_dir)

    response = app.handle("/")

    assert response.status == 200
    assert "Physical action plan" in response.text
    assert (
        "Physical context: Material: Bambu PLA Basic; "
        "Object: PLA validation coupon; Print type: coupon; "
        f"Run: {run_root.resolve()}"
    ) in response.text
    assert f"Coupon artifact: {result['coupon_stl_path']}" in response.text
    assert f"Coupon sidecar: {result['coupon_json_path']}" in response.text
    assert f"Bundle: {result['bundle_path']}" in response.text
    assert f"Bundle validation: {result['bundle_validation_path']}" in response.text
    assert f"Handoff: {result['handoff_markdown_path']}" in response.text
    assert "printpipe physical-slice --family pla" in response.text
    assert (
        f"printpipe open-folder &quot;{run_root.resolve()}&quot; --target run"
        in response.text
    )
    assert "Record after print:" in response.text


def test_home_response_renders_physical_record_form_after_starter_packet(
    tmp_path: Path,
) -> None:
    runs_dir = tmp_path / "runs"
    start_physical_validation(
        runs_dir,
        family="pla",
        operator="Zohar",
    )
    app = create_app(runs_dir=runs_dir)

    response = app.handle("/")

    assert response.status == 200
    assert 'action="/physical/record"' in response.text
    assert 'enctype="multipart/form-data"' in response.text
    assert 'name="family" value="pla"' in response.text
    assert 'name="print_status"' in response.text
    assert 'name="first_layer"' in response.text
    assert 'name="adhesion"' in response.text
    assert 'name="photo"' in response.text


def test_post_physical_record_writes_passed_evidence_and_copies_photo(
    tmp_path: Path,
) -> None:
    runs_dir = tmp_path / "runs"
    start_physical_validation(
        runs_dir,
        family="pla",
        operator="Zohar",
    )
    app = create_app(runs_dir=runs_dir)
    body, content_type = _multipart_form_body(
        fields={
            "family": "pla",
            "print_status": "passed",
            "operator": "Zohar",
            "first_layer": "clean first layer",
            "adhesion": "held through print",
        },
        file_field="photo",
        filename="first-layer.jpg",
        content_type="image/jpeg",
        file_content=b"jpeg-ish",
    )

    response = app.handle(
        "/physical/record",
        method="POST",
        headers={"Content-Type": content_type},
        body=body,
    )

    run_root = runs_dir / "physical-pla-validation"
    evidence_path = run_root / "90_physical" / "physical_evidence.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    artifact_path = run_root / evidence["artifacts"][0]["path"]
    status = json.loads(app.handle("/physical-status.json").text)
    assert response.status == 303
    assert response.header("Location") == "/#physical-action-plan"
    assert evidence["print_status"] == "passed"
    assert evidence["operator"] == "Zohar"
    assert evidence["first_layer"] == "clean first layer"
    assert evidence["adhesion"] == "held through print"
    assert evidence["artifacts"][0]["kind"] == "photo"
    assert artifact_path.read_bytes() == b"jpeg-ish"
    assert status["family_status"]["pla"]["status"] == "passed"


def test_post_physical_record_requires_photo(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    start_physical_validation(
        runs_dir,
        family="pla",
        operator="Zohar",
    )
    app = create_app(runs_dir=runs_dir)
    body, content_type = _multipart_fields_body(
        {
            "family": "pla",
            "print_status": "passed",
            "operator": "Zohar",
            "first_layer": "clean first layer",
            "adhesion": "held through print",
        }
    )

    response = app.handle(
        "/physical/record",
        method="POST",
        headers={"Content-Type": content_type},
        body=body,
    )

    evidence = json.loads(
        (
            runs_dir
            / "physical-pla-validation"
            / "90_physical"
            / "physical_evidence.json"
        ).read_text(encoding="utf-8")
    )
    assert response.status == 400
    assert "Physical evidence photo is required." in response.text
    assert evidence["print_status"] == "not_printed"


def test_beta_plan_json_endpoint_returns_action_plan(tmp_path: Path):
    app = create_app(runs_dir=tmp_path / "runs")

    response = app.handle("/beta-plan.json")

    payload = json.loads(response.text)
    actions = {action["id"]: action for action in payload["actions"]}
    assert response.status == 200
    assert response.header("Content-Type") == "application/json; charset=utf-8"
    assert payload["overall_status"] == "action_required"
    assert payload["evidence"]["failure_report_count"] == 0
    assert actions["run_beta_dogfood"]["status"] == "action_required"
    assert actions["physical_validation"]["command"].startswith(
        "printpipe physical-plan --runs-dir"
    )


def test_release_plan_json_endpoint_returns_distribution_plan(monkeypatch, tmp_path: Path):
    def fake_release_plan(*, release_dir, runs_dir, regression_manifest_path=None):
        assert release_dir == tmp_path / "release"
        assert runs_dir == tmp_path / "runs"
        assert regression_manifest_path is None
        return {
            "schema_version": 1,
            "overall_status": "action_required",
            "action_count": 1,
            "proof_boundary": "A release plan is not signed distribution evidence.",
            "actions": [
                {
                    "id": "macos_distribution",
                    "label": "macOS distribution",
                    "status": "action_required",
                    "command": "printpipe build-release --developer-id-identity ...",
                    "followup_command": "",
                }
            ],
        }

    monkeypatch.setattr(
        "printpipe.web.server.build_release_distribution_plan",
        fake_release_plan,
    )
    app = create_app(
        release_dir=tmp_path / "release",
        runs_dir=tmp_path / "runs",
    )

    response = app.handle("/release-plan.json")

    payload = json.loads(response.text)
    assert response.status == 200
    assert response.header("Content-Type") == "application/json; charset=utf-8"
    assert payload["overall_status"] == "action_required"
    assert payload["actions"][0]["id"] == "macos_distribution"


def test_home_response_renders_release_distribution_plan(monkeypatch, tmp_path: Path):
    def fake_release_plan(*, release_dir, runs_dir, regression_manifest_path=None):
        return {
            "schema_version": 1,
            "overall_status": "action_required",
            "action_count": 2,
            "proof_boundary": "A release plan is not signed distribution evidence.",
            "actions": [
                {
                    "id": "macos_distribution",
                    "label": "macOS distribution",
                    "status": "action_required",
                    "detail": "Developer ID signing and notarization are missing.",
                    "required_inputs": [
                        "Developer ID Application certificate",
                        "notarytool keychain profile",
                    ],
                    "start_command": "printpipe release-start --release-dir dist/release --runs-dir runs",
                    "handoff_markdown_path": str(tmp_path / "release_handoffs" / "release_distribution_handoff.md"),
                    "command": "printpipe build-release --developer-id-identity ...",
                    "followup_command": "",
                },
                {
                    "id": "windows_distribution",
                    "label": "Windows distribution",
                    "status": "action_required",
                    "detail": "Signed Windows installer is missing.",
                    "required_inputs": [
                        "Windows standalone ZIP",
                        "signtool",
                        "Code-signing certificate",
                    ],
                    "setup_command": "printpipe build-windows-standalone --output dist/release/PrintPipe-Windows-standalone.zip --json",
                    "start_command": "printpipe release-start --release-dir dist/release --runs-dir runs",
                    "handoff_markdown_path": str(tmp_path / "release_handoffs" / "release_distribution_handoff.md"),
                    "command": "printpipe build-windows-installer ...",
                    "followup_command": "printpipe build-release --windows-installer-exe ...",
                },
            ],
        }

    monkeypatch.setattr(
        "printpipe.web.server.build_release_distribution_plan",
        fake_release_plan,
    )
    app = create_app(
        release_dir=tmp_path / "release",
        runs_dir=tmp_path / "runs",
    )

    response = app.handle("/")

    assert response.status == 200
    assert "Release distribution plan" in response.text
    assert "2 action required" in response.text
    assert "A release plan is not signed distribution evidence." in response.text
    assert "macOS distribution" in response.text
    assert "Windows distribution" in response.text
    assert "printpipe release-start --release-dir dist/release --runs-dir runs" in response.text
    assert "release_distribution_handoff.md" in response.text
    assert (
        "Required inputs: Developer ID Application certificate, "
        "notarytool keychain profile"
    ) in response.text
    assert (
        "Required inputs: Windows standalone ZIP, signtool, "
        "Code-signing certificate"
    ) in response.text
    assert "Setup prerequisite:" in response.text
    assert "printpipe build-windows-standalone" in response.text
    assert "Release handoff:" in response.text
    assert "Build/check:" in response.text
    assert "printpipe build-release --developer-id-identity" in response.text
    assert "printpipe build-windows-installer" in response.text
    assert "Follow-up check:" in response.text
    assert 'href="/release-plan.json"' in response.text


def test_home_response_renders_release_start_form(monkeypatch, tmp_path: Path):
    def fake_release_plan(*, release_dir, runs_dir, regression_manifest_path=None):
        return {
            "schema_version": 1,
            "overall_status": "action_required",
            "action_count": 1,
            "proof_boundary": "A release plan is not signed distribution evidence.",
            "actions": [
                {
                    "id": "macos_distribution",
                    "label": "macOS distribution",
                    "status": "action_required",
                    "start_command": "printpipe release-start --release-dir dist/release --runs-dir runs",
                    "command": "printpipe build-release --developer-id-identity ...",
                },
            ],
        }

    monkeypatch.setattr(
        "printpipe.web.server.build_release_distribution_plan",
        fake_release_plan,
    )
    app = create_app(
        release_dir=tmp_path / "release",
        runs_dir=tmp_path / "runs",
    )

    response = app.handle("/")

    assert response.status == 200
    assert 'id="release-distribution-plan"' in response.text
    assert 'action="/release/start"' in response.text
    assert "Create release handoff" in response.text


def test_post_release_start_writes_handoff_and_redirects(tmp_path: Path):
    release_dir = tmp_path / "release"
    runs_dir = tmp_path / "runs"
    app = create_app(release_dir=release_dir, runs_dir=runs_dir)

    response = app.handle(
        "/release/start",
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        body=b"",
    )

    handoff = release_dir.parent / "release_handoffs" / "release_distribution_handoff.md"
    text = handoff.read_text(encoding="utf-8")
    assert response.status == 303
    assert response.header("Location") == "/#release-distribution-plan"
    assert "Release Distribution Handoff" in text
    assert "A release plan is not signed distribution evidence" in text
    assert not (release_dir / "release_manifest.json").exists()


def test_final_plan_json_endpoint_returns_ordered_endgame_plan(monkeypatch, tmp_path: Path):
    def fake_final_plan(*, release_dir, runs_dir, regression_manifest_path=None):
        assert release_dir == tmp_path / "release"
        assert runs_dir == tmp_path / "runs"
        assert regression_manifest_path is None
        return {
            "schema_version": 1,
            "overall_status": "action_required",
            "action_count": 7,
            "proof_boundary": "A final plan is not evidence.",
            "sections": [
                {"id": "physical_validation", "label": "Physical validation", "action_count": 3},
                {"id": "trusted_user_beta", "label": "Trusted-user beta", "action_count": 1},
                {"id": "release_distribution", "label": "Release distribution", "action_count": 3},
            ],
        }

    monkeypatch.setattr("printpipe.web.server.build_final_action_plan", fake_final_plan)
    app = create_app(
        release_dir=tmp_path / "release",
        runs_dir=tmp_path / "runs",
    )

    response = app.handle("/final-plan.json")

    payload = json.loads(response.text)
    assert response.status == 200
    assert response.header("Content-Type") == "application/json; charset=utf-8"
    assert payload["overall_status"] == "action_required"
    assert payload["sections"][0]["id"] == "physical_validation"
    assert payload["action_count"] == 7


def test_final_next_json_endpoint_returns_focused_next_action(monkeypatch, tmp_path: Path):
    def fake_final_plan(*, release_dir, runs_dir, regression_manifest_path=None):
        assert release_dir == tmp_path / "release"
        assert runs_dir == tmp_path / "runs"
        assert regression_manifest_path == tmp_path / "regressions.json"
        return {
            "schema_version": 1,
            "overall_status": "action_required",
            "action_count": 7,
            "proof_boundary": "A final plan is not evidence.",
            "next_action": {
                "section_label": "Physical validation",
                "action_id": "pla",
                "label": "PLA",
                "command": "printpipe record-physical-evidence runs/pla",
                "coupon_stl_path": "runs/pla/40_geometry/coupon.stl",
            },
            "sections": [{"id": "physical_validation"}],
        }

    monkeypatch.setattr("printpipe.web.server.build_final_action_plan", fake_final_plan)
    app = create_app(
        release_dir=tmp_path / "release",
        runs_dir=tmp_path / "runs",
    )

    response = app.handle(
        f"/final-next.json?regression_manifest={tmp_path / 'regressions.json'}"
    )

    payload = json.loads(response.text)
    assert response.status == 200
    assert response.header("Content-Type") == "application/json; charset=utf-8"
    assert payload["overall_status"] == "action_required"
    assert payload["action_count"] == 7
    assert payload["next_action"]["action_id"] == "pla"
    assert payload["next_command"] == "printpipe record-physical-evidence runs/pla"
    assert "sections" not in payload


def test_home_response_renders_final_action_plan(monkeypatch, tmp_path: Path):
    def fake_final_plan(*, release_dir, runs_dir, regression_manifest_path=None):
        return {
            "schema_version": 1,
            "overall_status": "action_required",
            "action_count": 7,
            "proof_boundary": "A final plan is not evidence.",
            "sections": [
                {
                    "id": "physical_validation",
                    "label": "Physical validation",
                    "status": "action_required",
                    "action_count": 3,
                    "detail": "Print and record PLA, PETG, and TPU coupons.",
                    "command": "printpipe physical-plan --runs-dir runs",
                },
                {
                    "id": "trusted_user_beta",
                    "label": "Trusted-user beta",
                    "status": "action_required",
                    "action_count": 1,
                    "detail": "Record missing trusted-user feedback.",
                    "command": "printpipe beta-feedback-plan --runs-dir runs",
                },
                {
                    "id": "release_distribution",
                    "label": "Release distribution",
                    "status": "action_required",
                    "action_count": 3,
                    "detail": "Sign and notarize release artifacts.",
                    "command": "printpipe release-plan --release-dir dist/release --runs-dir runs",
                },
            ],
        }

    monkeypatch.setattr("printpipe.web.server.build_final_action_plan", fake_final_plan)
    app = create_app(
        release_dir=tmp_path / "release",
        runs_dir=tmp_path / "runs",
    )

    response = app.handle("/")

    assert response.status == 200
    assert "Final readiness / Remaining actions" in response.text
    assert "<strong>7</strong> remaining action(s)" in response.text
    assert "A final plan is not evidence." in response.text
    assert "Physical validation" in response.text
    assert "Trusted-user beta" in response.text
    assert "Release distribution" in response.text
    assert "final-readiness-checklist" in response.text
    assert "Digital coupons, meshes, and slice receipts are not physical proof." in response.text
    assert "not-run or incomplete feedback packets" in response.text
    assert "printpipe physical-plan --runs-dir runs" in response.text
    assert "printpipe beta-feedback-plan --runs-dir runs" in response.text
    assert 'href="/final-plan.json"' in response.text
    assert 'href="/final-next.json"' in response.text
    assert 'href="/physical-plan.json"' in response.text


def test_beta_feedback_status_json_endpoint_returns_trusted_user_status(
    tmp_path: Path,
):
    runs_dir = tmp_path / "runs"
    _write_trusted_feedback(runs_dir / "run-maya", tester="Maya")
    _write_trusted_feedback(runs_dir / "run-sam", tester="Sam", outcome="failed")

    app = create_app(runs_dir=runs_dir)

    response = app.handle("/beta-feedback-status.json")

    payload = json.loads(response.text)
    assert response.status == 200
    assert response.header("Content-Type") == "application/json; charset=utf-8"
    assert payload["overall_status"] == "insufficient_feedback"
    assert payload["unique_trusted_user_count"] == 2
    assert payload["missing_trusted_user_count"] == 1
    assert payload["outcome_counts"]["failed"] == 1


def test_beta_feedback_plan_json_endpoint_returns_action_plan(tmp_path: Path):
    runs_dir = tmp_path / "runs"
    _write_trusted_feedback(runs_dir / "run-maya", tester="Maya")
    app = create_app(runs_dir=runs_dir)

    response = app.handle("/beta-feedback-plan.json")

    payload = json.loads(response.text)
    assert response.status == 200
    assert response.header("Content-Type") == "application/json; charset=utf-8"
    assert payload["overall_status"] == "action_required"
    assert payload["trusted_user_count"] == 1
    assert payload["action_count"] == 2
    assert "record-beta-feedback" in payload["actions"][0]["record_command"]
    assert "not trusted-user evidence" in payload["proof_boundary"]


def test_home_response_renders_trusted_user_feedback_action_plan(tmp_path: Path):
    app = create_app(runs_dir=tmp_path / "runs")

    response = app.handle("/")

    assert response.status == 200
    assert "Trusted-user action plan" in response.text
    assert "3 action required" in response.text
    assert "A generated feedback plan is not trusted-user evidence" in response.text
    assert "Tester slot 1" in response.text
    assert "printpipe record-beta-feedback" in response.text
    assert "printpipe beta-feedback-plan --runs-dir runs" in response.text
    assert 'href="/beta-feedback-plan.json"' in response.text


def test_home_response_renders_trusted_user_action_context_and_files(
    tmp_path: Path,
) -> None:
    runs_dir = tmp_path / "runs"
    run_root = runs_dir / "run-trusted-ui-context"
    report = run_root / "80_reports" / "run_report.html"
    bundle = run_root / "60_bundle" / "part.3mf"
    report.parent.mkdir(parents=True)
    bundle.parent.mkdir(parents=True)
    report.write_text("<html>report</html>", encoding="utf-8")
    bundle.write_text("bundle", encoding="utf-8")
    result = start_trusted_user_feedback(
        run_root,
        tester="Maya",
        input_type="existing_stl",
        material="SUNLU TPU 90A",
        printer="Bambu Lab P2S",
    )
    app = create_app(runs_dir=runs_dir)

    response = app.handle("/")

    assert response.status == 200
    assert "Trusted-user action plan" in response.text
    assert (
        "Review context: Material: SUNLU TPU 90A; Printer: Bambu Lab P2S; "
        "Input: existing_stl; Tester: Maya; "
        f"Run: {run_root.resolve()}"
    ) in response.text
    assert f"Handoff: {result['handoff_markdown_path']}" in response.text
    assert f"Run report: {report.resolve()}" in response.text
    assert f"Bundle: {bundle.resolve()}" in response.text


def test_home_response_renders_trusted_user_record_form_after_handoff(
    tmp_path: Path,
) -> None:
    runs_dir = tmp_path / "runs"
    run_root = runs_dir / "run-trusted-ui-record"
    report = run_root / "80_reports" / "run_report.html"
    report.parent.mkdir(parents=True)
    report.write_text("<html>report</html>", encoding="utf-8")
    start_trusted_user_feedback(
        run_root,
        tester="Maya",
        input_type="existing_stl",
        material="SUNLU TPU 90A",
        printer="Bambu Lab P2S",
    )
    app = create_app(runs_dir=runs_dir)

    response = app.handle("/")

    assert response.status == 200
    assert 'action="/beta-feedback/record"' in response.text
    assert 'enctype="multipart/form-data"' in response.text
    assert 'name="slot" value="1"' in response.text
    assert 'name="outcome"' in response.text
    assert 'name="summary"' in response.text
    assert 'name="would_print"' in response.text
    assert 'name="recommendation"' in response.text
    assert 'name="artifact"' in response.text


def test_post_beta_feedback_record_writes_packet_and_copies_artifact(
    tmp_path: Path,
) -> None:
    runs_dir = tmp_path / "runs"
    run_root = runs_dir / "run-trusted-ui-post"
    report = run_root / "80_reports" / "run_report.html"
    report.parent.mkdir(parents=True)
    report.write_text("<html>report</html>", encoding="utf-8")
    start_trusted_user_feedback(
        run_root,
        tester="Maya",
        input_type="existing_stl",
        material="SUNLU TPU 90A",
        printer="Bambu Lab P2S",
    )
    app = create_app(runs_dir=runs_dir)
    body, content_type = _multipart_form_body(
        fields={
            "slot": "1",
            "outcome": "passed",
            "summary": "Maya reviewed the run and would print it.",
            "would_print": "yes",
            "recommendation": "ready for a small test group",
            "issue": "No blocking issue.",
        },
        file_field="artifact",
        filename="review.png",
        content_type="image/png",
        file_content=b"png-ish",
    )

    response = app.handle(
        "/beta-feedback/record",
        method="POST",
        headers={"Content-Type": content_type},
        body=body,
    )

    feedback_path = run_root / "90_beta" / "trusted_user_feedback.json"
    feedback = json.loads(feedback_path.read_text(encoding="utf-8"))
    artifact_path = run_root / feedback["artifacts"][0]["path"]
    status = json.loads(app.handle("/beta-feedback-status.json").text)
    assert response.status == 303
    assert response.header("Location") == "/#trusted-user-action-plan"
    assert feedback["tester"] == "Maya"
    assert feedback["outcome"] == "passed"
    assert feedback["summary"] == "Maya reviewed the run and would print it."
    assert feedback["would_print"] == "yes"
    assert feedback["recommendation"] == "ready for a small test group"
    assert feedback["artifacts"][0]["kind"] == "artifact"
    assert artifact_path.read_bytes() == b"png-ish"
    assert status["unique_trusted_user_count"] == 1
    assert status["trusted_users"] == ["Maya"]


def test_post_beta_feedback_record_requires_summary(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    run_root = runs_dir / "run-trusted-ui-missing-summary"
    report = run_root / "80_reports" / "run_report.html"
    report.parent.mkdir(parents=True)
    report.write_text("<html>report</html>", encoding="utf-8")
    start_trusted_user_feedback(
        run_root,
        tester="Maya",
        input_type="existing_stl",
        material="SUNLU TPU 90A",
        printer="Bambu Lab P2S",
    )
    app = create_app(runs_dir=runs_dir)
    body, content_type = _multipart_fields_body(
        {
            "slot": "1",
            "outcome": "passed",
            "summary": "",
            "would_print": "yes",
            "recommendation": "ready",
        }
    )

    response = app.handle(
        "/beta-feedback/record",
        method="POST",
        headers={"Content-Type": content_type},
        body=body,
    )

    assert response.status == 400
    assert "Trusted-user feedback summary is required." in response.text
    assert not (run_root / "90_beta" / "trusted_user_feedback.json").exists()


def test_home_response_renders_trusted_user_feedback_gate(tmp_path: Path):
    runs_dir = tmp_path / "runs"
    _write_trusted_feedback(runs_dir / "run-maya", tester="Maya")
    _write_trusted_feedback(runs_dir / "run-sam", tester="Sam", outcome="failed")
    _write_trusted_feedback(runs_dir / "run-lee", tester="Lee", outcome="partial")
    app = create_app(runs_dir=runs_dir)

    response = app.handle("/")

    assert response.status == 200
    assert "Trusted-user feedback" in response.text
    assert "passed" in response.text
    assert "3 / 3 trusted users" in response.text
    assert "Feedback packets: 3" in response.text
    assert "Maya" in response.text
    assert "Sam" in response.text
    assert "Lee" in response.text
    assert "printpipe beta-feedback-status --runs-dir runs --strict" in response.text
    assert 'href="/beta-feedback-status.json"' in response.text


def test_home_response_renders_not_run_trusted_users_without_counting_them(
    tmp_path: Path,
):
    runs_dir = tmp_path / "runs"
    _write_trusted_feedback(runs_dir / "run-maya", tester="Maya")
    _write_trusted_feedback(runs_dir / "run-lee-not-run", tester="Lee", outcome="not_run")
    app = create_app(runs_dir=runs_dir)

    response = app.handle("/")

    assert response.status == 200
    assert "Trusted-user feedback" in response.text
    assert "1 / 3 trusted users" in response.text
    assert "Not-run testers" in response.text
    assert "Lee" in response.text
    assert "Not-run packets are audit records, not completed beta feedback." in response.text


def test_home_trusted_feedback_outcomes_are_missing_when_no_outcomes_recorded(
    tmp_path: Path,
):
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    app = create_app(runs_dir=runs_dir)

    response = app.handle("/")

    assert response.status == 200
    assert "Trusted-user feedback" in response.text
    assert (
        '<article class="physical-family physical-family-missing">\n'
        "          <span>Outcomes</span>\n"
        "          <strong>missing</strong>"
    ) in response.text
    assert "No completed tester outcomes recorded." in response.text


def test_beta_plan_json_endpoint_accepts_regression_manifest_query(
    monkeypatch,
    tmp_path: Path,
):
    manifest_path = tmp_path / "regression_manifest.json"

    def fake_beta_plan(runs_dir, *, regression_manifest_path=None):
        assert runs_dir == tmp_path / "runs"
        assert regression_manifest_path == manifest_path
        return {
            "schema_version": 1,
            "overall_status": "action_required",
            "action_required_count": 1,
            "proof_boundary": "proof boundary",
            "actions": [
                {
                    "id": "run_regressions",
                    "label": "Replay captured regressions",
                    "status": "action_required",
                    "detail": "1 regression case drifted.",
                    "command": "printpipe run-regressions manifest --strict",
                }
            ],
        }

    monkeypatch.setattr("printpipe.web.server.build_beta_action_plan", fake_beta_plan)
    app = create_app(runs_dir=tmp_path / "runs")

    response = app.handle(f"/beta-plan.json?regression_manifest={manifest_path}")

    payload = json.loads(response.text)
    assert response.status == 200
    assert payload["actions"][0]["id"] == "run_regressions"


def test_home_response_renders_beta_action_plan(tmp_path: Path):
    app = create_app(runs_dir=tmp_path / "runs")

    response = app.handle("/")

    assert response.status == 200
    assert "Beta action plan" in response.text
    assert "4 action required" in response.text
    assert "A generated beta plan is not trusted-user evidence" in response.text
    assert "Dogfood canonical object matrix" in response.text
    assert "Physical material validation" in response.text
    assert "Capture failed beta runs" in response.text
    assert "Replay captured regressions" in response.text
    assert "Trusted-user beta" in response.text
    assert "Update material/orientation/repair rules" in response.text
    assert "printpipe beta-plan --runs-dir runs" in response.text


def test_home_response_renders_combined_readiness_summary(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        "printpipe.web.server.build_beta_readiness_report",
        lambda runs_dir: {
            "schema_version": 1,
            "overall_status": "action_required",
            "action_required_count": 2,
            "gates": [
                {
                    "id": "physical_validation",
                    "label": "Physical validation",
                    "status": "action_required",
                    "detail": "Missing passed physical evidence for: PLA, PETG, TPU.",
                    "action": "Print and record passed coupons.",
                },
                {
                    "id": "dependencies",
                    "label": "Dependencies",
                    "status": "ready",
                    "detail": "Required dependencies are available.",
                    "action": "No action needed.",
                },
                {
                    "id": "signing",
                    "label": "Release signing",
                    "status": "action_required",
                    "detail": "Missing signing requirements: Developer ID Application.",
                    "action": "Install signing tools/certificates.",
                },
            ],
        },
    )
    app = create_app(runs_dir=tmp_path / "runs")

    response = app.handle("/")

    assert response.status == 200
    assert "Readiness gates" in response.text
    assert "action_required" in response.text
    assert "2 action required" in response.text
    assert "Physical validation" in response.text
    assert "Release signing" in response.text
    assert "Missing signing requirements: Developer ID Application." in response.text
    assert "Print and record passed coupons." in response.text


def test_media_meshgen_smoke_status_json_endpoint(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        "printpipe.web.server.build_media_meshgen_smoke_status",
        lambda runs_dir: {
            "schema_version": 1,
            "runs_dir": str(runs_dir),
            "overall_status": "passed",
            "smoke_receipt_count": 1,
            "successful_smoke_count": 1,
            "failed_smoke_count": 0,
            "latest_successful_smoke": {
                "run_id": "smoke-ok",
                "provider_id": "media_command",
                "output_path": "20_meshgen/media_command.stl",
            },
            "message": "1 successful media meshgen smoke receipt(s) found.",
            "action": "No action needed.",
        },
    )
    app = create_app(runs_dir=tmp_path / "runs")

    response = app.handle("/media-meshgen-smoke-status.json")

    payload = json.loads(response.text)
    assert response.status == 200
    assert payload["overall_status"] == "passed"
    assert payload["latest_successful_smoke"]["run_id"] == "smoke-ok"


def test_home_response_renders_media_meshgen_smoke_status(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        "printpipe.web.server.build_media_meshgen_smoke_status",
        lambda runs_dir: {
            "schema_version": 1,
            "runs_dir": str(runs_dir),
            "overall_status": "missing",
            "smoke_receipt_count": 0,
            "successful_smoke_count": 0,
            "failed_smoke_count": 0,
            "latest_successful_smoke": None,
            "message": "No successful media meshgen smoke receipt found.",
            "action": "Run printpipe media-meshgen-smoke reference.png --runs-dir runs",
        },
    )
    app = create_app(runs_dir=tmp_path / "runs")

    response = app.handle("/")

    assert response.status == 200
    assert "Media meshgen smoke" in response.text
    assert "overall: missing" in response.text
    assert "No successful media meshgen smoke receipt found." in response.text
    assert "media-meshgen-smoke-status.json" in response.text


def test_home_response_renders_media_meshgen_setup_forms(tmp_path: Path):
    app = create_app(runs_dir=tmp_path / "runs", workspace_dir=tmp_path)

    response = app.handle("/")

    assert response.status == 200
    assert 'id="media-meshgen-setup"' in response.text
    assert 'action="/media-meshgen/template"' in response.text
    assert 'action="/media-meshgen/configure"' in response.text
    assert 'action="/media-meshgen/smoke"' in response.text
    assert 'name="preset"' in response.text
    assert 'name="command"' in response.text
    assert 'name="reference"' in response.text
    assert 'name="output_format"' in response.text
    assert 'value="comfyui-api"' in response.text
    assert 'value="glb"' in response.text
    assert "This does not prove semantic reconstruction" in response.text


def test_post_media_meshgen_template_writes_adapter_and_redirects(tmp_path: Path):
    app = create_app(runs_dir=tmp_path / "runs", workspace_dir=tmp_path)

    response = app.handle(
        "/media-meshgen/template",
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        body=b"",
    )

    adapter = tmp_path / "scripts" / "media_meshgen_adapter.py"
    assert response.status == 303
    assert response.header("Location") == "/#media-meshgen-setup"
    assert adapter.exists()
    assert "PrintPipe media meshgen adapter template" in adapter.read_text(encoding="utf-8")
    assert adapter.stat().st_mode & 0o111


def test_post_media_meshgen_template_writes_selected_preset_and_redirects(tmp_path: Path):
    app = create_app(runs_dir=tmp_path / "runs", workspace_dir=tmp_path)

    response = app.handle(
        "/media-meshgen/template",
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        body=b"preset=comfyui-api",
    )

    adapter = tmp_path / "scripts" / "media_meshgen_adapter.py"
    assert response.status == 303
    assert response.header("Location") == "/#media-meshgen-setup"
    text = adapter.read_text(encoding="utf-8")
    assert "ComfyUI API media meshgen adapter preset" in text
    assert "PRINTPIPE_COMFYUI_WORKFLOW" in text


def test_post_media_meshgen_configure_writes_project_config_and_redirects(
    tmp_path: Path,
):
    app = create_app(runs_dir=tmp_path / "runs", workspace_dir=tmp_path)

    response = app.handle(
        "/media-meshgen/configure",
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        body=b"command=python+scripts%2Fmedia_meshgen_adapter.py",
    )

    config = json.loads((tmp_path / ".printpipe" / "config.json").read_text())
    assert response.status == 303
    assert response.header("Location") == "/#media-meshgen-setup"
    assert config["media_meshgen_command"] == "python scripts/media_meshgen_adapter.py"


def test_post_media_meshgen_smoke_runs_configured_adapter_and_redirects(
    tmp_path: Path,
):
    source_mesh = (
        Path(__file__).parent
        / "fixtures"
        / "objects"
        / "existing_stl_pipeline"
        / "tiny_tetrahedron.stl"
    )
    fake_adapter = tmp_path / "fake_media_adapter.py"
    fake_adapter.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "import argparse",
                "parser = argparse.ArgumentParser()",
                "parser.add_argument('--output', required=True)",
                "parser.add_argument('--output-format', required=True)",
                "args, _ = parser.parse_known_args()",
                f"Path(args.output).write_text(Path({str(source_mesh)!r}).read_text(encoding='ascii'), encoding='ascii')",
                "",
            ]
        ),
        encoding="utf-8",
    )
    runs_dir = tmp_path / "runs"
    command = f"python {fake_adapter}"
    (tmp_path / ".printpipe").mkdir()
    (tmp_path / ".printpipe" / "config.json").write_text(
        json.dumps({"media_meshgen_command": command}),
        encoding="utf-8",
    )
    app = create_app(runs_dir=runs_dir, workspace_dir=tmp_path)
    body, content_type = _multipart_form_body(
        fields={"prompt": "printable hook", "output_format": "glb"},
        file_field="reference",
        filename="reference.png",
        content_type="image/png",
        file_content=b"fake image",
    )

    response = app.handle(
        "/media-meshgen/smoke",
        method="POST",
        headers={"Content-Type": content_type},
        body=body,
    )

    smoke_paths = list(runs_dir.glob("*/20_meshgen/smoke.json"))
    payload = json.loads(smoke_paths[0].read_text(encoding="utf-8"))
    assert response.status == 303
    assert response.header("Location") == "/#media-meshgen-setup"
    assert payload["status"] == "succeeded"
    assert payload["command"] == command
    assert payload["output_path"].endswith(".glb")
    assert (smoke_paths[0].parents[1] / payload["output_path"]).exists()


def test_post_media_meshgen_smoke_requires_reference(tmp_path: Path):
    app = create_app(runs_dir=tmp_path / "runs", workspace_dir=tmp_path)
    body, content_type = _multipart_fields_body({"prompt": "printable hook"})

    response = app.handle(
        "/media-meshgen/smoke",
        method="POST",
        headers={"Content-Type": content_type},
        body=body,
    )

    assert response.status == 400
    assert "Media meshgen reference upload is required." in response.text


def test_home_response_renders_release_status_summary(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        "printpipe.web.server.build_release_status_report",
        lambda *, release_dir, runs_dir: {
            "schema_version": 1,
            "overall_status": "action_required",
            "action_required_count": 2,
            "gates": [
                {
                    "id": "release_bundle",
                    "label": "Release bundle",
                    "status": "ready",
                    "detail": "Release manifest and 4 artifact(s) verify.",
                    "action": "No action needed.",
                },
                {
                    "id": "macos_distribution",
                    "label": "macOS distribution",
                    "status": "action_required",
                    "detail": "macOS release artifact is not Developer ID signed and notarized.",
                    "action": "Install Developer ID identities.",
                },
                {
                    "id": "windows_distribution",
                    "label": "Windows distribution",
                    "status": "action_required",
                    "detail": "No signed Windows installer artifact is recorded in the manifest.",
                    "action": "Build and include a signed PrintPipeSetup.exe.",
                },
            ],
            "next_actions": [
                "Install Developer ID identities.",
                "Build and include a signed PrintPipeSetup.exe.",
            ],
        },
    )
    app = create_app(runs_dir=tmp_path / "runs", release_dir=tmp_path / "release")

    response = app.handle("/")

    assert response.status == 200
    assert "Release status" in response.text
    assert "2 action required" in response.text
    assert "Release bundle" in response.text
    assert "macOS distribution" in response.text
    assert "Windows distribution" in response.text
    assert "macOS release artifact is not Developer ID signed and notarized." in response.text
    assert "Build and include a signed PrintPipeSetup.exe." in response.text


def test_release_status_json_endpoint_returns_combined_release_report(
    monkeypatch,
    tmp_path: Path,
):
    monkeypatch.setattr(
        "printpipe.web.server.build_release_status_report",
        lambda *, release_dir, runs_dir: {
            "schema_version": 1,
            "overall_status": "action_required",
            "release_dir": str(release_dir),
            "runs_dir": str(runs_dir),
            "gates": [
                {
                    "id": "macos_distribution",
                    "status": "action_required",
                    "detail": "macOS release artifact is not Developer ID signed and notarized.",
                }
            ],
        },
    )
    runs_dir = tmp_path / "runs"
    release_dir = tmp_path / "release"
    app = create_app(runs_dir=runs_dir, release_dir=release_dir)

    response = app.handle("/release-status.json")

    payload = json.loads(response.text)
    assert response.status == 200
    assert response.header("Content-Type") == "application/json; charset=utf-8"
    assert payload["overall_status"] == "action_required"
    assert payload["release_dir"] == str(release_dir)
    assert payload["runs_dir"] == str(runs_dir)
    assert payload["gates"][0]["id"] == "macos_distribution"


def test_release_status_json_endpoint_accepts_regression_manifest_query(
    monkeypatch,
    tmp_path: Path,
):
    manifest_path = tmp_path / "regression_manifest.json"

    def fake_release_status_report(*, release_dir, runs_dir, regression_manifest_path=None):
        assert regression_manifest_path == manifest_path
        return {
            "schema_version": 1,
            "overall_status": "action_required",
            "release_dir": str(release_dir),
            "runs_dir": str(runs_dir),
            "gates": [
                {
                    "id": "beta_regressions",
                    "status": "action_required",
                    "detail": "1 regression case(s) drifted from expected outcomes.",
                }
            ],
        }

    monkeypatch.setattr(
        "printpipe.web.server.build_release_status_report",
        fake_release_status_report,
    )
    app = create_app(runs_dir=tmp_path / "runs", release_dir=tmp_path / "release")

    response = app.handle(f"/release-status.json?regression_manifest={manifest_path}")

    payload = json.loads(response.text)
    assert response.status == 200
    assert payload["gates"][0]["id"] == "beta_regressions"


def test_doctor_json_endpoint_returns_environment_report(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        "printpipe.web.server.build_environment_report",
        lambda: {
            "schema_version": 1,
            "platform": {"raw": "darwin", "normalized": "macos"},
            "dependencies": [],
            "bambu_studio": {"installed_count": 1, "candidate_count": 1},
            "bambu_profiles": {"candidate_count": 1},
            "summary": {"dependency_status_counts": {}},
        },
    )
    app = create_app(runs_dir=tmp_path / "runs")

    response = app.handle("/doctor.json")

    payload = json.loads(response.text)
    assert response.status == 200
    assert response.header("Content-Type") == "application/json; charset=utf-8"
    assert payload["platform"]["normalized"] == "macos"
    assert payload["bambu_studio"]["installed_count"] == 1


def test_readiness_json_endpoint_returns_combined_gate_report(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        "printpipe.web.server.build_beta_readiness_report",
        lambda runs_dir: {
            "schema_version": 1,
            "overall_status": "action_required",
            "gates": [
                {
                    "id": "physical_validation",
                    "status": "action_required",
                    "detail": "Missing passed physical evidence.",
                }
            ],
        },
    )
    runs_dir = tmp_path / "runs"
    app = create_app(runs_dir=runs_dir)

    response = app.handle("/readiness.json")

    payload = json.loads(response.text)
    assert response.status == 200
    assert response.header("Content-Type") == "application/json; charset=utf-8"
    assert payload["overall_status"] == "action_required"
    assert payload["gates"][0]["id"] == "physical_validation"


def test_readiness_json_endpoint_accepts_regression_manifest_query(
    monkeypatch,
    tmp_path: Path,
):
    manifest_path = tmp_path / "regression_manifest.json"

    def fake_readiness_report(runs_dir, *, regression_manifest_path=None):
        assert runs_dir == tmp_path / "runs"
        assert regression_manifest_path == manifest_path
        return {
            "schema_version": 1,
            "overall_status": "action_required",
            "gates": [
                {
                    "id": "beta_regressions",
                    "status": "action_required",
                    "detail": "1 regression case(s) drifted from expected outcomes.",
                }
            ],
        }

    monkeypatch.setattr(
        "printpipe.web.server.build_beta_readiness_report",
        fake_readiness_report,
    )
    app = create_app(runs_dir=tmp_path / "runs")

    response = app.handle(f"/readiness.json?regression_manifest={manifest_path}")

    payload = json.loads(response.text)
    assert response.status == 200
    assert payload["gates"][0]["id"] == "beta_regressions"


def test_configured_regression_manifest_feeds_home_and_json_endpoints(
    monkeypatch,
    tmp_path: Path,
):
    manifest_path = tmp_path / "regression_manifest.json"
    observed: list[tuple[str, Path | None]] = []

    def fake_readiness_report(runs_dir, *, regression_manifest_path=None):
        observed.append(("readiness", regression_manifest_path))
        return {
            "schema_version": 1,
            "overall_status": "action_required",
            "action_required_count": 1,
            "gates": [
                {
                    "id": "beta_regressions",
                    "label": "Beta regressions",
                    "status": "action_required",
                    "detail": "1 regression case(s) drifted from expected outcomes.",
                    "action": "Run printpipe run-regressions manifest --strict.",
                }
            ],
        }

    def fake_release_status_report(*, release_dir, runs_dir, regression_manifest_path=None):
        observed.append(("release", regression_manifest_path))
        return {
            "schema_version": 1,
            "overall_status": "action_required",
            "action_required_count": 1,
            "release_dir": str(release_dir),
            "runs_dir": str(runs_dir),
            "gates": [
                {
                    "id": "beta_regressions",
                    "label": "Beta regressions",
                    "status": "action_required",
                    "detail": "1 regression case(s) drifted from expected outcomes.",
                    "action": "Run printpipe run-regressions manifest --strict.",
                }
            ],
            "next_actions": ["Run printpipe run-regressions manifest --strict."],
        }

    def fake_beta_plan(runs_dir, *, regression_manifest_path=None):
        observed.append(("beta-plan", regression_manifest_path))
        return {
            "schema_version": 1,
            "overall_status": "action_required",
            "action_required_count": 1,
            "proof_boundary": "proof boundary",
            "actions": [
                {
                    "id": "run_regressions",
                    "label": "Replay captured regressions",
                    "status": "action_required",
                    "detail": "1 regression case(s) drifted from expected outcomes.",
                    "command": "printpipe run-regressions manifest --strict",
                }
            ],
        }

    monkeypatch.setattr(
        "printpipe.web.server.build_beta_readiness_report",
        fake_readiness_report,
    )
    monkeypatch.setattr(
        "printpipe.web.server.build_release_status_report",
        fake_release_status_report,
    )
    monkeypatch.setattr("printpipe.web.server.build_beta_action_plan", fake_beta_plan)
    app = create_app(
        runs_dir=tmp_path / "runs",
        release_dir=tmp_path / "release",
        regression_manifest_path=manifest_path,
    )

    home = app.handle("/")
    readiness = json.loads(app.handle("/readiness.json").text)
    release = json.loads(app.handle("/release-status.json").text)
    beta_plan = json.loads(app.handle("/beta-plan.json").text)

    encoded_manifest = quote(str(manifest_path), safe="")
    assert home.status == 200
    assert "Beta regressions" in home.text
    assert "Replay captured regressions" in home.text
    assert f"/readiness.json?regression_manifest={encoded_manifest}" in home.text
    assert f"/release-status.json?regression_manifest={encoded_manifest}" in home.text
    assert f"/beta-plan.json?regression_manifest={encoded_manifest}" in home.text
    assert readiness["gates"][0]["id"] == "beta_regressions"
    assert release["gates"][0]["id"] == "beta_regressions"
    assert beta_plan["actions"][0]["id"] == "run_regressions"
    assert observed == [
        ("release", manifest_path),
        ("readiness", manifest_path),
        ("beta-plan", manifest_path),
        ("readiness", manifest_path),
        ("release", manifest_path),
        ("beta-plan", manifest_path),
    ]


def test_run_detail_response_renders_visual_workbench_and_print_readiness(tmp_path: Path):
    source = tmp_path / "reference.png"
    source.write_bytes(b"fake image")
    runs_dir = tmp_path / "runs"
    layout = create_run(source, runs_dir, run_id="run-workbench-001")
    generated_mesh = layout.meshgen_dir / "generated.stl"
    repaired_mesh = layout.repair_dir / "repaired.stl"
    oriented_mesh = layout.geometry_dir / "oriented.stl"
    flex_coupon = layout.geometry_dir / "flex_coupon_40x15x3.stl"
    model_preview = layout.geometry_dir / "run_detail_model_preview.svg"
    preview = layout.geometry_dir / "bed-fit.svg"
    bundle = layout.bundle_dir / "ready.3mf"
    slice_result = layout.slice_dir / "slice_result.json"
    for artifact_path in (
        generated_mesh,
        repaired_mesh,
        oriented_mesh,
        flex_coupon,
        model_preview,
        preview,
        bundle,
        slice_result,
    ):
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text("artifact\n", encoding="utf-8")
    stages = (
        StageReceipt(
            stage="mesh_generation",
            status=StageStatus.SUCCEEDED,
            message="Generated watertight candidate mesh.",
            artifacts=(
                Artifact(
                    kind=ArtifactKind.GENERATED_MESH,
                    path=generated_mesh,
                    label="Generated mesh",
                ),
            ),
        ),
        StageReceipt(
            stage="repair",
            status=StageStatus.SUCCEEDED,
            message="Closed small holes and repaired normals.",
            artifacts=(
                Artifact(
                    kind=ArtifactKind.REPAIRED_MESH,
                    path=repaired_mesh,
                    label="Repaired mesh",
                ),
            ),
            metrics={
                "watertight": True,
                "non_manifold_edges": 0,
                "bounds_mm": [118.0, 76.0, 42.0],
            },
        ),
        StageReceipt(
            stage="orient_scale",
            status=StageStatus.SUCCEEDED,
            message="Fits Bambu Lab P2S plate.",
            artifacts=(
                Artifact(
                    kind=ArtifactKind.ORIENTED_MESH,
                    path=oriented_mesh,
                    label="Final STL",
                ),
                Artifact(
                    kind=ArtifactKind.PREVIEW,
                    path=model_preview,
                    label="Run detail model SVG preview",
                ),
                Artifact(
                    kind=ArtifactKind.PREVIEW,
                    path=preview,
                    label="Bed fit preview",
                ),
                Artifact(
                    kind=ArtifactKind.CALIBRATION_MESH,
                    path=flex_coupon,
                    label="Flex coupon ASCII STL",
                ),
            ),
            metrics={"bed_fit": "fits", "support_risk": "medium"},
        ),
        StageReceipt(
            stage="slice_report",
            status=StageStatus.SUCCEEDED,
            message="Bambu slice succeeded.",
            artifacts=(
                Artifact(
                    kind=ArtifactKind.THREEMF,
                    path=bundle,
                    label="3MF bundle",
                ),
                Artifact(
                    kind=ArtifactKind.SLICE_LOG,
                    path=slice_result,
                    label="Slice report",
                ),
            ),
            metrics={"slice_success": True, "profile": "0.20mm Standard @BBL P2S"},
        ),
    )
    report_dict = build_run_report_dict(
        layout,
        stages=stages,
        settings_changes=(
            {
                "printer_label": "Bambu Lab P2S",
                "material_label": "SUNLU TPU 90A",
                "profile_label": "0.20mm Slipper TPU 90A @BBL P2S",
                "use_case": "wearable slipper",
                "target_length_mm": 120.0,
            },
        ),
        warnings=(
            "Support risk is medium around the arch.",
            "Opening too narrow for TPU slipper upper.",
        ),
    )
    write_run_report(
        layout,
        stages=stages,
        settings_changes=report_dict["settings_changes"],
        warnings=report_dict["warnings"],
    )
    write_html_report(layout, report_dict)
    app = create_app(runs_dir=runs_dir)

    response = app.handle("/runs/run-workbench-001")

    assert response.status == 200
    assert "Can this run print?" in response.text
    assert 'class="verdict-strip verdict-strip-warn"' in response.text
    assert "Not yet: rebuild required" in response.text
    assert "Next action" in response.text
    assert (
        "fix the upper/opening, support policy, and slice handoff before trusting this run"
        in response.text
    )
    assert "Widen the upper/opening and rebuild from edits." in response.text
    assert 'class="run-context"' in response.text
    assert 'class="print-context"' in response.text
    assert "Material and preflight context" in response.text
    assert "SUNLU TPU 90A" in response.text
    assert "0.20mm Slipper TPU 90A @BBL P2S" in response.text
    assert "wearable slipper" in response.text
    assert "Required; coupon artifact generated, physical print not recorded" in response.text
    assert "Physical coupon/print evidence not recorded" in response.text
    assert "Warnings" in response.text
    assert "Support risk is medium around the arch." in response.text
    assert "Needs geometry edit: upper/opening too narrow" in response.text
    assert "Model workbench" in response.text
    assert "Edit Geometry" in response.text
    assert "Rebuild from edits" in response.text
    assert "Manifold" in response.text
    assert "Bed fit" in response.text
    assert "TPU profile" in response.text
    assert "Support" in response.text
    assert "Slice" in response.text
    assert "Model" in response.text
    assert "Upper Fit" in response.text
    assert "Support Risk" in response.text
    assert '<button class="tab"' not in response.text
    assert 'href="#model-preview"' in response.text
    assert 'href="#validation-results"' in response.text
    assert 'href="#edit-geometry"' in response.text
    assert '<span class="tab">Bed Fit</span>' not in response.text
    assert 'id="model-preview"' in response.text
    assert 'id="validation-results"' in response.text
    assert 'id="edit-geometry"' in response.text
    assert 'class="model-preview-image"' in response.text
    assert 'src="/runs/run-workbench-001/artifacts/40_geometry/run_detail_model_preview.svg"' in (
        response.text
    )
    assert "Large model preview placeholder" not in response.text
    assert "Run detail model SVG preview" in response.text
    assert "opening risk" in response.text
    assert "Input / reference" in response.text
    assert "Mesh generation" in response.text
    assert "Orient / scale" in response.text
    assert "Original mesh" in response.text
    assert "Repaired mesh" in response.text
    assert "Final STL" in response.text
    assert ">3MF<" in response.text
    assert "3MF bundle" in response.text
    assert 'download="ready.3mf"' in response.text
    assert "Slice report" in response.text
    assert 'href="/runs/run-workbench-001/artifacts/70_slice/slice_result.json"' in response.text
    assert "Warning and Failure Receipts" in response.text
    assert "Failed stages" in response.text
    assert "No failed pipeline stages." in response.text
    assert 'class="workbench-artifacts"' in response.text
    assert 'action="/runs/run-workbench-001/open-folder/bundle"' in response.text
    assert "Open bundle folder" in response.text
    assert 'action="/runs/run-workbench-001/open-folder/report"' in response.text
    assert "Open report folder" in response.text
    assert response.text.find('class="workbench-artifacts"') < response.text.find('class="lower-grid"')
    assert response.text.find('class="workbench-artifacts"') < response.text.find('class="controls"')
    assert "Overall scale" in response.text
    assert "Widen / narrow opening" in response.text
    assert "Raise / lower arch/opening" in response.text
    assert "TPU-safe snug/tree supports + external spool review" in response.text
    assert "Freeform edit instruction" in response.text
    assert 'action="/runs/run-workbench-001/edits" method="post"' in response.text
    assert 'name="opening_delta_mm"' in response.text
    assert 'name="arch_delta_mm"' in response.text
    assert 'name="support_strategy"' in response.text
    assert 'name="edit_instruction"' in response.text
    assert 'href="/runs/run-workbench-001/artifacts/60_bundle/ready.3mf"' in response.text


def test_run_detail_response_surfaces_physical_evidence_packet(tmp_path: Path):
    source = tmp_path / "reference.png"
    source.write_bytes(b"fake image")
    runs_dir = tmp_path / "runs"
    layout = create_run(source, runs_dir, run_id="run-physical-ui-001")
    write_run_report(
        layout,
        stages=(),
        settings_changes=(
            {
                "printer_label": "Bambu Lab P2S",
                "material_label": "SUNLU TPU 90A",
                "profile_label": "0.20mm Slipper TPU 90A @BBL P2S",
                "use_case": "wearable slipper",
            },
        ),
    )
    photo = layout.root / "90_physical" / "artifacts" / "coupon-flex.jpg"
    photo.parent.mkdir(parents=True)
    photo.write_bytes(b"photo")
    evidence = build_physical_print_evidence(
        run_id=layout.run_id,
        material="SUNLU TPU 90A",
        printer="Bambu Lab P2S",
        object_label="flex coupon",
        print_type="coupon",
        print_status="passed",
        operator="Zohar",
        filament_drying="50 C for 6 h",
        layer_bonding="no splits after bending",
        flex_recovery="returned flat after 20 flexes",
        artifacts=(
            PhysicalArtifact(
                label="Flexed coupon photo",
                path="90_physical/artifacts/coupon-flex.jpg",
                kind="photo",
            ),
        ),
    )
    write_physical_evidence_files(run_root=layout.root, evidence=evidence)
    app = create_app(runs_dir=runs_dir)

    response = app.handle("/runs/run-physical-ui-001")

    assert response.status == 200
    assert "Physical evidence" in response.text
    assert "Passed physical coupon: flex coupon" in response.text
    assert "Operator: Zohar" in response.text
    assert "No missing required evidence" in response.text
    assert "Physical coupon/print evidence not recorded" not in response.text
    assert 'href="/runs/run-physical-ui-001/artifacts/90_physical/physical_evidence.json"' in (
        response.text
    )
    assert 'href="/runs/run-physical-ui-001/artifacts/90_physical/physical_evidence.md"' in (
        response.text
    )
    assert 'href="/runs/run-physical-ui-001/artifacts/90_physical/artifacts/coupon-flex.jpg"' in (
        response.text
    )


def test_run_detail_response_surfaces_physical_evidence_context_fields(tmp_path: Path):
    source = tmp_path / "reference.png"
    source.write_bytes(b"fake image")
    runs_dir = tmp_path / "runs"
    layout = create_run(source, runs_dir, run_id="run-physical-ui-context")
    write_run_report(layout, stages=())
    photo = layout.root / "90_physical" / "artifacts" / "first-layer.jpg"
    photo.parent.mkdir(parents=True)
    photo.write_bytes(b"photo")
    write_physical_evidence_files(
        run_root=layout.root,
        evidence=build_physical_print_evidence(
            run_id=layout.run_id,
            material="Bambu PETG Basic",
            printer="Bambu Lab P2S",
            object_label="tiny tetrahedron",
            print_type="small_object",
            print_status="partial",
            operator="Zohar",
            started_at="2026-05-28T18:10:00-07:00",
            completed_at="2026-05-28T18:42:00-07:00",
            first_layer="front corner lifted slightly",
            adhesion="usable with brim",
            warping="minor front lift",
            stringing="light wisps",
            artifacts=(
                PhysicalArtifact(
                    label="First-layer photo",
                    path="90_physical/artifacts/first-layer.jpg",
                    kind="photo",
                ),
            ),
        ),
    )
    app = create_app(runs_dir=runs_dir)

    response = app.handle("/runs/run-physical-ui-context")

    assert response.status == 200
    assert "Partial physical small_object: tiny tetrahedron" in response.text
    assert "Material: Bambu PETG Basic" in response.text
    assert "Printer: Bambu Lab P2S" in response.text
    assert "Started: 2026-05-28T18:10:00-07:00" in response.text
    assert "Completed: 2026-05-28T18:42:00-07:00" in response.text
    assert "Physical evidence recorded: partial" in response.text


def test_run_detail_response_hides_physical_evidence_panel_without_packet(tmp_path: Path):
    source = tmp_path / "reference.png"
    source.write_bytes(b"fake image")
    runs_dir = tmp_path / "runs"
    layout = create_run(source, runs_dir, run_id="run-physical-ui-none")
    write_run_report(layout, stages=())
    app = create_app(runs_dir=runs_dir)

    response = app.handle("/runs/run-physical-ui-none")

    assert response.status == 200
    assert 'aria-label="Physical evidence"' not in response.text
    assert "Physical coupon/print evidence not recorded" in response.text


def test_run_detail_response_surfaces_failed_physical_evidence(tmp_path: Path):
    source = tmp_path / "reference.png"
    source.write_bytes(b"fake image")
    runs_dir = tmp_path / "runs"
    layout = create_run(source, runs_dir, run_id="run-physical-ui-failed")
    write_run_report(layout, stages=())
    photo = layout.root / "90_physical" / "artifacts" / "coupon.jpg"
    photo.parent.mkdir(parents=True)
    photo.write_bytes(b"photo")
    write_physical_evidence_files(
        run_root=layout.root,
        evidence=build_physical_print_evidence(
            run_id=layout.run_id,
            material="SUNLU TPU 90A",
            printer="Bambu Lab P2S",
            object_label="flex coupon",
            print_type="coupon",
            print_status="failed",
            operator="Zohar",
            filament_drying="50 C for 6 h",
            layer_bonding="split at layer 12",
            flex_recovery="not tested because print failed",
            artifacts=(
                PhysicalArtifact(
                    label="Failed coupon photo",
                    path="90_physical/artifacts/coupon.jpg",
                    kind="photo",
                ),
            ),
        ),
    )
    app = create_app(runs_dir=runs_dir)

    response = app.handle("/runs/run-physical-ui-failed")

    assert response.status == 200
    assert "Failed physical coupon: flex coupon" in response.text
    assert "Physical evidence recorded: failed" in response.text
    assert "physically validated" not in response.text.lower()
    assert 'href="/runs/run-physical-ui-failed/artifacts/90_physical/physical_evidence.json"' in (
        response.text
    )
    assert 'href="/runs/run-physical-ui-failed/artifacts/90_physical/artifacts/coupon.jpg"' in (
        response.text
    )


def test_run_detail_response_surfaces_incomplete_physical_evidence(tmp_path: Path):
    source = tmp_path / "reference.png"
    source.write_bytes(b"fake image")
    runs_dir = tmp_path / "runs"
    layout = create_run(source, runs_dir, run_id="run-physical-ui-incomplete")
    flex_coupon = layout.geometry_dir / "flex_coupon_40x15x3.stl"
    flex_coupon.parent.mkdir(parents=True, exist_ok=True)
    flex_coupon.write_text("solid flex\n", encoding="utf-8")
    write_run_report(
        layout,
        stages=(
            StageReceipt(
                stage="orient_scale",
                status=StageStatus.SUCCEEDED,
                message="Oriented for bed fit.",
                artifacts=(
                    Artifact(
                        kind=ArtifactKind.CALIBRATION_MESH,
                        path=flex_coupon,
                        label="Flex coupon ASCII STL",
                    ),
                ),
            ),
        ),
        settings_changes=(
            {
                "printer_label": "Bambu Lab P2S",
                "material_label": "SUNLU TPU 90A",
                "profile_label": "0.20mm Slipper TPU 90A @BBL P2S",
                "use_case": "wearable slipper",
            },
        ),
    )
    write_physical_evidence_files(
        run_root=layout.root,
        evidence=build_physical_print_evidence(
            run_id=layout.run_id,
            material="SUNLU TPU 90A",
            printer="Bambu Lab P2S",
            object_label="flex coupon",
            print_type="coupon",
            print_status="passed",
            operator="Zohar",
        ),
    )
    app = create_app(runs_dir=runs_dir)

    response = app.handle("/runs/run-physical-ui-incomplete")

    assert response.status == 200
    assert "Passed physical coupon: flex coupon" in response.text
    assert "Missing: photo artifact" in response.text
    assert "Physical evidence incomplete: photo artifact" in response.text
    assert "Required; coupon artifact generated, physical print not recorded" in response.text
    assert "Required; physical coupon evidence recorded" not in response.text
    assert "physically validated" not in response.text.lower()


def test_run_detail_response_keeps_not_printed_physical_packet_honest(tmp_path: Path):
    source = tmp_path / "reference.png"
    source.write_bytes(b"fake image")
    runs_dir = tmp_path / "runs"
    layout = create_run(source, runs_dir, run_id="run-physical-ui-not-printed")
    write_run_report(layout, stages=())
    write_physical_evidence_files(
        run_root=layout.root,
        evidence=build_physical_print_evidence(
            run_id=layout.run_id,
            material="SUNLU TPU 90A",
            printer="Bambu Lab P2S",
            object_label="flex coupon",
            print_type="coupon",
            print_status="not_printed",
            operator="Zohar",
        ),
    )
    app = create_app(runs_dir=runs_dir)

    response = app.handle("/runs/run-physical-ui-not-printed")

    assert response.status == 200
    assert "Physical coupon recorded: flex coupon" in response.text
    assert "Physical evidence recorded; review packet" in response.text
    assert "Physical evidence recorded: not_printed" not in response.text
    assert "physical coupon evidence recorded" not in response.text.lower()


def test_run_detail_response_surfaces_prompt_image_quote_receipt(tmp_path: Path):
    source = tmp_path / "prompt.txt"
    source.write_text("small ergonomic wall hook\n", encoding="utf-8")
    runs_dir = tmp_path / "runs"
    layout = create_run(source, runs_dir, run_id="prompt-quote-ui-001")
    stages = (
        StageReceipt(
            stage="classify_input",
            status=StageStatus.SUCCEEDED,
            message="classified input as prompt",
        ),
        StageReceipt(
            stage="prompt_reference_generation",
            status=StageStatus.FAILED,
            message="OpenAI prompt image estimated cost 0.25 USD exceeds cap 0.05 USD",
            metrics={
                "provider": "openai",
                "provider_configured": False,
                "candidate_count": 0,
                "provider_quote": {
                    "provider": "openai",
                    "privacy_mode": "remote_api",
                    "estimated_seconds": 45.0,
                    "estimated_cost_usd": 0.25,
                    "cost_estimate_configured": True,
                    "max_cost_usd": 0.05,
                    "remote_upload": True,
                    "stores_prompt_with_provider": True,
                },
            },
        ),
    )
    write_run_report(layout, stages=stages)
    app = create_app(runs_dir=runs_dir)

    response = app.handle("/runs/prompt-quote-ui-001")

    assert response.status == 200
    assert "Prompt image provider" in response.text
    assert "OpenAI" in response.text
    assert "remote API" in response.text
    assert "Estimated cost" in response.text
    assert "$0.25" in response.text
    assert "Max cost" in response.text
    assert "$0.05" in response.text
    assert "Budget blocked before remote work" in response.text
    assert "Pipeline failed: Input / reference" in response.text
    assert "<strong>Input / reference</strong>" in response.text
    assert "OpenAI prompt image estimated cost 0.25 USD exceeds cap 0.05 USD" in response.text


def test_run_detail_css_uses_generic_placeholder_and_keeps_rebuild_reachable():
    css = web_server._CSS + run_detail.RUN_DETAIL_CSS

    assert "clip-path:" not in css
    assert "print-object" not in css
    assert "mesh-placeholder" in css
    assert ".model-preview-image" in css
    assert ".next-action" in css
    assert ".run-context" in css
    assert ".print-context" in css
    assert ".physical-evidence" in css
    assert ".prompt-provider" in css
    assert ".verdict-strip-warn" in css
    assert ".verdict-issue" in css
    assert ".issue-line" in css
    assert ".workbench-artifacts" in css
    assert ".warning-receipts" in css
    assert ".open-folder-actions" in css
    assert ".edit-actions" in css
    assert "position: sticky" in css
    assert "bottom:0" in css
    assert "@media (max-width:1180px)" in css


def test_run_detail_keeps_generic_verdict_copy_for_non_slipper_runs():
    html = run_detail.render_run_detail_page(
        detail={
            "run_id": "run-flat-bracket-001",
            "input": {"kind": "mesh"},
            "printer": {"label": "Bambu Lab P2S"},
            "material": {"label": "PLA"},
            "profile": {"label": "0.20mm PLA"},
            "print_verdict": {
                "state": "blocked",
                "label": "Not ready to print",
                "reason": "One or more validation checks failed.",
            },
            "validation": [
                {
                    "key": "slice_success",
                    "label": "Slice success",
                    "state": "fail",
                    "detail": "Slice gate failed.",
                }
            ],
        },
        artifact_links=[],
    )

    assert "Not ready to print" in html
    assert "One or more validation checks failed." in html
    assert "wearable TPU geometry" not in html
    assert "Not yet: rebuild required" not in html


def test_run_detail_does_not_label_slice_only_slipper_review_as_narrow_upper():
    html = run_detail.render_run_detail_page(
        detail={
            "run_id": "run-slipper-wide-upper-001",
            "input": {"kind": "mesh"},
            "printer": {"label": "Bambu Lab P2S"},
            "material": {"label": "SUNLU TPU 90A"},
            "profile": {"label": "0.20mm Slipper TPU 90A"},
            "print_verdict": {
                "state": "review",
                "label": "Review before print",
                "reason": "Slice gate has not run.",
            },
            "validation": [
                {
                    "key": "bed_fit",
                    "label": "Bed fit",
                    "state": "pass",
                    "detail": "Fits the bed.",
                },
                {
                    "key": "support_risk",
                    "label": "Support risk",
                    "state": "pass",
                    "detail": "Support policy recorded.",
                },
                {
                    "key": "slice_success",
                    "label": "Slice success",
                    "state": "review",
                    "detail": "Slice gate skipped.",
                },
            ],
        },
        artifact_links=[],
    )

    assert "Slice gate not verified" in html
    assert "Open the 3MF in Bambu Studio and inspect the slice preview before printing." in html
    assert "Needs geometry edit: upper/opening too narrow" not in html
    assert "Not yet: rebuild required" not in html


def test_run_detail_response_rejects_unknown_run(tmp_path: Path):
    app = create_app(runs_dir=tmp_path / "runs")

    response = app.handle("/runs/nope")

    assert response.status == 404


def test_post_run_edit_creates_non_destructive_edit_run(tmp_path: Path):
    source = (
        Path(__file__).parent
        / "fixtures"
        / "objects"
        / "existing_stl_pipeline"
        / "tiny_tetrahedron.stl"
    )
    runs_dir = tmp_path / "runs"
    layout = create_run(source, runs_dir, run_id="run-edit-001")
    app = create_app(runs_dir=runs_dir)
    body = (
        "overall_scale=1.0&x_scale=1.0&y_scale=1.08&z_scale=1.0"
        "&target_length_mm=295&target_width_mm=118&target_height_mm=72"
        "&opening_delta_mm=14&arch_delta_mm=6&wall_thickness_mm=3.2"
        "&flat_base=on&support_strategy=snug_tree_auto"
        "&edit_instruction=Widen+the+upper+without+changing+sole+length"
    ).encode("utf-8")

    response = app.handle(
        "/runs/run-edit-001/edits",
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        body=body,
    )

    edit_root = runs_dir / "run-edit-001_edit_001"
    recipe = load_edit_recipe(edit_root)
    assert response.status == 303
    assert response.header("Location") == "/runs/run-edit-001_edit_001"
    assert edit_root.exists()
    assert (edit_root / "00_input" / "tiny_tetrahedron.stl").read_bytes() == source.read_bytes()
    assert layout.original_input.read_bytes() == source.read_bytes()
    assert (edit_root / "60_bundle").exists()
    assert any(path.suffix == ".3mf" for path in (edit_root / "60_bundle").iterdir())
    assert (edit_root / "80_reports" / "run_report.html").exists()
    assert recipe.parent_run_id == "run-edit-001"
    assert recipe.scale.y == 1.08
    assert recipe.targets_mm.length == 295.0
    assert recipe.geometry_intent.upper_width_delta_mm == 14.0
    assert recipe.geometry_intent.opening_width_delta_mm == 14.0
    assert recipe.geometry_intent.arch_height_delta_mm == 6.0
    assert recipe.geometry_intent.wall_thickness_mm == 3.2
    assert recipe.geometry_intent.flat_base is True
    assert recipe.support_strategy == "snug_tree_auto"
    assert recipe.instruction == "Widen the upper without changing sole length"

    detail_response = app.handle("/runs/run-edit-001_edit_001")
    assert detail_response.status == 200
    assert "Parent run" in detail_response.text
    assert "run-edit-001" in detail_response.text
    assert "Edit delta" in detail_response.text
    assert "opening +14 mm" in detail_response.text
    assert "support snug_tree_auto" in detail_response.text


def test_post_run_edit_redirects_to_failed_child_rebuild_report(tmp_path: Path):
    source = tmp_path / "reference.png"
    source.write_bytes(b"fake image")
    runs_dir = tmp_path / "runs"
    create_run(source, runs_dir, run_id="run-edit-media-001")
    app = create_app(runs_dir=runs_dir)
    body = b"overall_scale=1.0&support_strategy=auto"

    response = app.handle(
        "/runs/run-edit-media-001/edits",
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        body=body,
    )

    edit_root = runs_dir / "run-edit-media-001_edit_001"
    report_path = edit_root / "80_reports" / "run_report.json"
    assert response.status == 303
    assert response.header("Location") == "/runs/run-edit-media-001_edit_001"
    assert report_path.exists()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert ("edit_recipe.source_mesh", "failed") in {
        (stage["stage"], stage["status"]) for stage in report["stages"]
    }
    assert report["warnings"]


def test_home_response_groups_run_artifacts_for_preview_report_and_download(tmp_path: Path):
    source = tmp_path / "reference.png"
    source.write_bytes(b"fake image")
    runs_dir = tmp_path / "runs"
    layout = create_run(source, runs_dir, run_id="run-artifacts-001")
    bundle = layout.bundle_dir / "ready to print.3mf"
    preview_svg = layout.reports_dir / "bed fit.svg"
    preview_html = layout.reports_dir / "preview.html"
    for artifact_path in (bundle, preview_svg, preview_html):
        artifact_path.write_text("artifact\n", encoding="utf-8")
    stages = (
        StageReceipt(
            stage="geometry",
            status=StageStatus.SUCCEEDED,
            message="Preview ready.",
            artifacts=(
                Artifact(
                    kind=ArtifactKind.PREVIEW,
                    path=preview_svg,
                    label="Bed fit preview",
                ),
                Artifact(
                    kind=ArtifactKind.PREVIEW,
                    path=preview_html,
                    label="Interactive preview",
                ),
            ),
        ),
        StageReceipt(
            stage="bundle",
            status=StageStatus.SUCCEEDED,
            message="Bundle ready.",
            artifacts=(
                Artifact(
                    kind=ArtifactKind.THREEMF,
                    path=bundle,
                    label="Bambu bundle",
                ),
            ),
        ),
    )
    report_dict = build_run_report_dict(layout, stages=stages)
    write_run_report(layout, stages=stages)
    write_html_report(layout, report_dict)
    app = create_app(runs_dir=runs_dir)

    response = app.handle("/")

    assert response.status == 200
    assert '<section class="artifact-group artifact-group-bundle">' in response.text
    assert "Downloads" in response.text
    assert (
        'href="/runs/run-artifacts-001/artifacts/60_bundle/ready%20to%20print.3mf" '
        'download="ready to print.3mf"'
    ) in response.text
    assert '<section class="artifact-group artifact-group-preview">' in response.text
    assert "Previews" in response.text
    assert 'href="/runs/run-artifacts-001/artifacts/80_reports/bed%20fit.svg"' in response.text
    assert 'href="/runs/run-artifacts-001/artifacts/80_reports/preview.html"' in response.text
    assert '<section class="artifact-group artifact-group-reports">' in response.text
    assert "Reports" in response.text
    assert 'href="/runs/run-artifacts-001/artifacts/80_reports/run_report.html"' in response.text


def test_post_run_open_folder_opens_safe_bundle_folder_and_redirects(tmp_path: Path):
    source = tmp_path / "reference.stl"
    source.write_text("solid fake\nendsolid fake\n", encoding="utf-8")
    runs_dir = tmp_path / "runs"
    layout = create_run(source, runs_dir, run_id="run-open-001")
    opened: list[Path] = []
    app = create_app(runs_dir=runs_dir, path_opener=opened.append)

    response = app.handle("/runs/run-open-001/open-folder/bundle", method="POST")

    assert response.status == 303
    assert response.header("Location") == "/runs/run-open-001"
    assert opened == [layout.bundle_dir]


def test_post_runs_accepts_multipart_upload_creates_skeleton_run_and_redirects(
    tmp_path: Path,
    monkeypatch,
):
    monkeypatch.setenv(CONFIG_PATH_ENV, str(tmp_path / "missing-config.json"))
    runs_dir = tmp_path / "runs"
    app = create_app(runs_dir=runs_dir)
    body, content_type = _multipart_form_body(
        fields={
            "printer_id": "bambu-p2s-0-4-nozzle",
            "material_id": "sunlu-tpu-90a-slipper",
            "target_length_mm": "123.5",
        },
        file_field="input",
        filename="reference.png",
        content_type="image/png",
        file_content=b"fake image",
    )

    response = app.handle(
        "/runs",
        method="POST",
        headers={"Content-Type": content_type},
        body=body,
    )

    run_roots = [path for path in runs_dir.iterdir() if (path / "manifest.json").exists()]
    assert response.status == 303
    assert len(run_roots) == 1
    run_root = run_roots[0]
    assert response.header("Location") == f"/static/{run_root.name}/80_reports/run_report.html"
    assert (run_root / "00_input" / "reference.png").read_bytes() == b"fake image"
    assert (run_root / "10_frames" / "selected" / "reference.png").exists()
    assert (run_root / "80_reports" / "run_report.json").exists()
    assert (run_root / "80_reports" / "run_report.md").exists()
    assert (run_root / "80_reports" / "run_report.html").exists()

    manifest = json.loads((run_root / "manifest.json").read_text(encoding="utf-8"))
    launch_options = manifest["launch_options"]
    assert launch_options["source"] == "web_form"
    assert launch_options["uploaded_filename"] == "reference.png"
    assert launch_options["printer_id"] == "bambu-p2s-0-4-nozzle"
    assert launch_options["material_id"] == "sunlu-tpu-90a-slipper"
    assert launch_options["target_length_mm"] == 123.5

    report = json.loads((run_root / "80_reports" / "run_report.json").read_text(encoding="utf-8"))
    assert report["settings_changes"] == [launch_options]
    stages = {(stage["stage"], stage["status"]) for stage in report["stages"]}
    assert ("classify_input", "succeeded") in stages
    assert ("extract_references", "succeeded") in stages
    assert ("select_references", "succeeded") in stages
    assert ("contact_sheet", "succeeded") in stages
    assert ("meshgen", "failed") in stages
    assert report["warnings"] == [
        "No live image/GIF/video meshgen provider is configured. "
        "Run printpipe media-meshgen-template --preset comfyui-api "
        "--output scripts/media_meshgen_adapter.py, "
        "set PRINTPIPE_MEDIA_MESHGEN_COMMAND, set PRINTPIPE_HUNYUAN3D_COMMAND, "
        "or configure a hosted mesh provider."
    ]

    workbench = app.handle(f"/runs/{run_root.name}")
    assert workbench.status == 200
    assert "Warning and Failure Receipts" in workbench.text
    assert "printpipe media-meshgen-template" in workbench.text
    assert "<strong>Mesh generation</strong>" in workbench.text


def test_post_runs_accepts_prompt_only_creates_prompt_run_and_failed_receipts(tmp_path: Path):
    runs_dir = tmp_path / "runs"
    app = create_app(runs_dir=runs_dir)
    body, content_type = _multipart_fields_body(
        {
            "prompt": "small ergonomic wall hook with rounded screw tabs",
            "printer_id": "bambu-p2s-0-4-nozzle",
            "material_id": "pla",
            "prompt_image_provider": "command",
            "target_length_mm": "80",
        }
    )

    response = app.handle(
        "/runs",
        method="POST",
        headers={"Content-Type": content_type},
        body=body,
    )

    run_root = next(path for path in runs_dir.iterdir() if (path / "manifest.json").exists())
    assert response.status == 303
    assert response.header("Location") == f"/static/{run_root.name}/80_reports/run_report.html"
    assert (run_root / "00_input" / "prompt.txt").read_text(encoding="utf-8") == (
        "small ergonomic wall hook with rounded screw tabs\n"
    )

    manifest = json.loads((run_root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["input"]["kind"] == "prompt"
    assert manifest["input"]["prompt"] == "small ergonomic wall hook with rounded screw tabs"
    assert manifest["launch_options"]["input_mode"] == "prompt"
    assert manifest["launch_options"]["prompt_image_provider"] == "command"
    assert manifest["launch_options"]["prompt"] == "small ergonomic wall hook with rounded screw tabs"
    assert "uploaded_filename" not in manifest["launch_options"]

    report = json.loads((run_root / "80_reports" / "run_report.json").read_text(encoding="utf-8"))
    stages = {(stage["stage"], stage["status"]) for stage in report["stages"]}
    assert ("classify_input", "succeeded") in stages
    assert ("prompt_reference_generation", "failed") in stages
    assert report["settings_changes"] == [manifest["launch_options"]]
    assert report["warnings"] == [
        "prompt image command provider requires PRINTPIPE_PROMPT_IMAGE_COMMAND"
    ]


def test_post_runs_upload_with_prompt_preserves_prompt_hint_in_launch_options(tmp_path: Path):
    runs_dir = tmp_path / "runs"
    app = create_app(runs_dir=runs_dir)
    source = (
        Path(__file__).parent
        / "fixtures"
        / "objects"
        / "existing_stl_pipeline"
        / "tiny_tetrahedron.stl"
    )
    body, content_type = _multipart_form_body(
        fields={
            "prompt": "keep the base flat and add a softer rounded top",
            "printer_id": "bambu-p2s-0-4-nozzle",
            "material_id": "pla",
            "target_length_mm": "50",
        },
        file_field="input",
        filename="tiny_tetrahedron.stl",
        content_type="model/stl",
        file_content=source.read_bytes(),
    )

    response = app.handle(
        "/runs",
        method="POST",
        headers={"Content-Type": content_type},
        body=body,
    )

    run_root = next(path for path in runs_dir.iterdir() if (path / "manifest.json").exists())
    manifest = json.loads((run_root / "manifest.json").read_text(encoding="utf-8"))
    assert response.status == 303
    assert manifest["input"]["kind"] == "mesh"
    assert manifest["launch_options"]["input_mode"] == "file+prompt"
    assert manifest["launch_options"]["uploaded_filename"] == "tiny_tetrahedron.stl"
    assert manifest["launch_options"]["prompt"] == "keep the base flat and add a softer rounded top"
    assert (run_root / "60_bundle" / "existing_stl_tiny_tetrahedron.3mf").exists()


def test_post_runs_existing_stl_creates_bundle_and_report(tmp_path: Path):
    runs_dir = tmp_path / "runs"
    app = create_app(runs_dir=runs_dir)
    source = (
        Path(__file__).parent
        / "fixtures"
        / "objects"
        / "existing_stl_pipeline"
        / "tiny_tetrahedron.stl"
    )
    body, content_type = _multipart_form_body(
        fields={
            "printer_id": "bambu-p2s-0-4-nozzle",
            "material_id": "pla",
            "target_length_mm": "50",
        },
        file_field="input",
        filename="tiny_tetrahedron.stl",
        content_type="model/stl",
        file_content=source.read_bytes(),
    )

    response = app.handle(
        "/runs",
        method="POST",
        headers={"Content-Type": content_type},
        body=body,
    )

    run_root = next(path for path in runs_dir.iterdir() if (path / "manifest.json").exists())
    assert response.status == 303
    assert response.header("Location") == f"/static/{run_root.name}/80_reports/run_report.html"
    assert (run_root / "60_bundle" / "existing_stl_tiny_tetrahedron.3mf").exists()
    assert (run_root / "40_geometry" / "tiny_tetrahedron_oriented.stl").exists()

    report = json.loads((run_root / "80_reports" / "run_report.json").read_text(encoding="utf-8"))
    assert report["settings_changes"][0]["material_id"] == "pla"
    stages = {(stage["stage"], stage["status"]) for stage in report["stages"]}
    assert ("bundle", "succeeded") in stages
    assert ("slice", "skipped") in stages
    assert report["pre_print_checklist"]


def test_home_response_skips_unreadable_recent_runs_dir(tmp_path: Path):
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    app = create_app(runs_dir=runs_dir)

    runs_dir.chmod(0)
    try:
        response = app.handle("/")
    finally:
        runs_dir.chmod(0o700)

    assert response.status == 200
    assert "PrintPipe" in response.text


def test_run_artifact_response_serves_safe_downloads_from_runs_dir(tmp_path: Path):
    source = tmp_path / "reference.png"
    source.write_bytes(b"fake image")
    runs_dir = tmp_path / "runs"
    layout = create_run(source, runs_dir, run_id="run-download-001")
    bundle = layout.bundle_dir / "ready.3mf"
    bundle.write_bytes(b"bundle")
    app = create_app(runs_dir=runs_dir)

    response = app.handle("/runs/run-download-001/artifacts/60_bundle/ready.3mf")

    assert response.status == 200
    assert response.body == b"bundle"
    assert response.header("Content-Type") == "model/3mf"
    assert response.header("Content-Disposition") == 'attachment; filename="ready.3mf"'

    traversal = app.handle("/runs/run-download-001/artifacts/../outside.txt")
    assert traversal.status == 404


def test_health_response_returns_json_status():
    app = PrintPipeWebApp()

    response = app.handle("/health")

    assert response.status == 200
    assert response.header("Content-Type") == "application/json; charset=utf-8"
    assert json.loads(response.text) == {"service": "printpipe-web", "status": "ok"}


def test_favicon_response_is_empty_success():
    app = PrintPipeWebApp()

    response = app.handle("/favicon.ico")

    assert response.status == 204
    assert response.body == b""
    assert response.header("Content-Length") == "0"


def test_static_response_serves_local_generated_html(tmp_path: Path):
    nested = tmp_path / "runs" / "example"
    nested.mkdir(parents=True)
    page = nested / "report & summary.html"
    html = "<!doctype html><title>Example report</title>\n"
    page.write_text(html, encoding="utf-8")
    app = PrintPipeWebApp(static_roots=(tmp_path,))

    response = app.handle("/static/runs/example/report%20%26%20summary.html")

    assert response.status == 200
    assert response.header("Content-Type") == "text/html; charset=utf-8"
    assert response.text == html


def test_static_response_rejects_path_traversal(tmp_path: Path):
    public = tmp_path / "public"
    public.mkdir()
    secret = tmp_path / "secret.html"
    secret.write_text("<!doctype html>secret\n", encoding="utf-8")
    app = PrintPipeWebApp(static_roots=(public,))

    response = app.handle("/static/../secret.html")

    assert response.status == 404
    assert "secret" not in response.text


def test_static_response_only_serves_html_files(tmp_path: Path):
    data = tmp_path / "run_report.json"
    data.write_text('{"status": "ok"}\n', encoding="utf-8")
    app = PrintPipeWebApp(static_roots=(tmp_path,))

    response = app.handle("/static/run_report.json")

    assert response.status == 404


def test_serve_builds_app_from_runs_dir_without_import_side_effects(monkeypatch, tmp_path: Path):
    calls: list[object] = []
    created_apps: list[PrintPipeWebApp] = []

    class FakeServer:
        def serve_forever(self) -> None:
            calls.append("serve_forever")

        def server_close(self) -> None:
            calls.append("server_close")

    def fake_create_server(
        app: PrintPipeWebApp | None = None,
        *,
        host: str = "127.0.0.1",
        port: int = 0,
    ) -> FakeServer:
        assert host == "0.0.0.0"
        assert port == 9876
        assert app is not None
        created_apps.append(app)
        return FakeServer()

    monkeypatch.setattr(web_server, "create_server", fake_create_server)

    web_server.serve(host="0.0.0.0", port=9876, runs_dir=tmp_path)

    assert calls == ["serve_forever", "server_close"]
    assert created_apps[0].static_roots == (tmp_path,)
    assert created_apps[0].runs_dir == tmp_path
