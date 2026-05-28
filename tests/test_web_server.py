from __future__ import annotations

import json
from pathlib import Path

from printpipe.beta.physical import (
    PhysicalArtifact,
    build_physical_print_evidence,
    write_physical_evidence_files,
)
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
    assert 'href="/doctor.json"' in response.text


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
    assert "printpipe record-physical-evidence" in response.text
    assert "printpipe physical-plan --runs-dir runs" in response.text


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


def test_post_runs_accepts_multipart_upload_creates_skeleton_run_and_redirects(tmp_path: Path):
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
        "Hunyuan3D local command is not configured; set "
        "PRINTPIPE_HUNYUAN3D_COMMAND or pass a command path."
    ]

    workbench = app.handle(f"/runs/{run_root.name}")
    assert workbench.status == 200
    assert "Warning and Failure Receipts" in workbench.text
    assert "Hunyuan3D local command is not configured" in workbench.text
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
