from __future__ import annotations

from pathlib import Path

from printpipe.contracts import Artifact, ArtifactKind, StageReceipt, StageStatus
from printpipe.reports import build_run_report_dict
from printpipe.reports.html import render_html_report, write_html_report
from printpipe.runs.paths import create_run


def test_render_html_report_shows_receipts_and_escapes_content(tmp_path: Path):
    source = tmp_path / "reference & tricky.gif"
    source.write_bytes(b"fake gif")
    layout = create_run(source, tmp_path / "runs", run_id="run-html-001")

    raw_mesh = layout.meshgen_dir / "mesh & raw.stl"
    repaired_mesh = layout.repair_dir / "repaired.stl"
    bed_preview = layout.reports_dir / "bed fit.png"
    bundle = layout.bundle_dir / "ready.3mf"
    slice_log = layout.slice_dir / "slice.log"
    for artifact_path in (raw_mesh, repaired_mesh, bed_preview, bundle, slice_log):
        artifact_path.write_text("artifact\n", encoding="utf-8")

    stages = (
        StageReceipt(
            stage="input",
            status=StageStatus.SUCCEEDED,
            message='Stored original input <script>alert("x")</script>.',
            artifacts=(
                Artifact(
                    kind=ArtifactKind.ORIGINAL_INPUT,
                    path=layout.original_input,
                    label="Original <GIF>",
                ),
            ),
        ),
        StageReceipt(
            stage="mesh",
            status=StageStatus.SUCCEEDED,
            message="Generated and repaired mesh.",
            artifacts=(
                Artifact(
                    kind=ArtifactKind.GENERATED_MESH,
                    path=raw_mesh,
                    label="Raw mesh & preview",
                ),
                Artifact(
                    kind=ArtifactKind.REPAIRED_MESH,
                    path=repaired_mesh,
                    label="Repaired mesh",
                ),
            ),
            metrics={"faces": 1280, "watertight": True},
        ),
        StageReceipt(
            stage="slice",
            status=StageStatus.SUCCEEDED,
            message="Bambu CLI slice passed.",
            artifacts=(
                Artifact(kind=ArtifactKind.PREVIEW, path=bed_preview, label="Bed fit preview"),
                Artifact(kind=ArtifactKind.THREEMF, path=bundle, label="Bambu bundle"),
                Artifact(kind=ArtifactKind.SLICE_LOG, path=slice_log, label="Slice log"),
            ),
            metrics={"layers": 425, "mass_g": 196.2, "time": "21h 30m"},
        ),
    )
    report_dict = build_run_report_dict(
        layout,
        stages=stages,
        warnings=('Review support contact <carefully> & dry TPU.',),
        settings_changes=(
            {
                "key": "support_style",
                "default": "default",
                "value": "snug",
                "reason": "TPU support <safer> & removable",
            },
        ),
        pre_print_checklist=(
            {"title": "Dry TPU", "status": "required", "detail": "50 C before printing."},
            {"item": "Open .3mf in Bambu Studio", "status": "pending"},
            "Confirm first layer <clean> & purge line.",
        ),
    )

    html = render_html_report(report_dict, layout=layout)

    assert "<script>" not in html
    assert 'Stored original input &lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;.' in html
    assert "run-html-001" in html
    assert "input" in html
    assert "mesh" in html
    assert "slice" in html
    assert "succeeded" in html
    assert "425" in html
    assert "196.2" in html
    assert 'href="../00_input/reference%20%26%20tricky.gif"' in html
    assert 'href="../20_meshgen/mesh%20%26%20raw.stl"' in html
    assert 'href="bed%20fit.png"' in html
    assert "Original &lt;GIF&gt;" in html
    assert "Raw mesh &amp; preview" in html
    assert "Review support contact &lt;carefully&gt; &amp; dry TPU." in html
    assert "support_style" in html
    assert "snug" in html
    assert "TPU support &lt;safer&gt; &amp; removable" in html
    assert "Open .3mf in Bambu Studio" in html
    assert "Dry TPU" in html
    assert "50 C before printing." in html
    assert "Confirm first layer &lt;clean&gt; &amp; purge line." in html


def test_render_html_report_promotes_local_print_readiness_sections(tmp_path: Path):
    source = tmp_path / "reference.png"
    source.write_bytes(b"fake image")
    layout = create_run(source, tmp_path / "runs", run_id="run-html-roadmap")

    raw_mesh = layout.meshgen_dir / "raw.stl"
    repaired_mesh = layout.repair_dir / "repaired.stl"
    bed_preview = layout.reports_dir / "bed-fit.png"
    bundle = layout.bundle_dir / "ready.3mf"
    slice_log = layout.slice_dir / "slice.log"
    for artifact_path in (raw_mesh, repaired_mesh, bed_preview, bundle, slice_log):
        artifact_path.write_text("artifact\n", encoding="utf-8")

    stages = (
        StageReceipt(
            stage="input",
            status=StageStatus.SUCCEEDED,
            message="Stored original input.",
            artifacts=(
                Artifact(
                    kind=ArtifactKind.ORIGINAL_INPUT,
                    path=layout.original_input,
                    label="Reference input",
                ),
            ),
        ),
        StageReceipt(
            stage="mesh",
            status=StageStatus.SUCCEEDED,
            message="Generated mesh.",
            artifacts=(
                Artifact(
                    kind=ArtifactKind.GENERATED_MESH,
                    path=raw_mesh,
                    label="Generated mesh",
                ),
            ),
            metrics={"faces": 1200},
        ),
        StageReceipt(
            stage="repair",
            status=StageStatus.SUCCEEDED,
            message="Repair passed.",
            artifacts=(
                Artifact(
                    kind=ArtifactKind.REPAIRED_MESH,
                    path=repaired_mesh,
                    label="Repaired mesh",
                ),
            ),
            metrics={"watertight": True},
        ),
        StageReceipt(
            stage="bed fit",
            status=StageStatus.SUCCEEDED,
            message="Fits selected bed.",
            artifacts=(
                Artifact(
                    kind=ArtifactKind.PREVIEW,
                    path=bed_preview,
                    label="Bed fit preview",
                ),
            ),
            metrics={
                "bed": {"width_mm": 256, "depth_mm": 256},
                "min_margin_mm": 18.4,
                "rotation_degrees": 45,
            },
        ),
        StageReceipt(
            stage="slice",
            status=StageStatus.SUCCEEDED,
            message="Slice passed.",
            artifacts=(
                Artifact(kind=ArtifactKind.THREEMF, path=bundle, label="Bambu bundle"),
                Artifact(kind=ArtifactKind.SLICE_LOG, path=slice_log, label="Slice log"),
            ),
            metrics={"layers": 140, "time": "3h 12m", "mass_g": 42.5},
        ),
    )
    report_dict = build_run_report_dict(
        layout,
        stages=stages,
        warnings=("Watch first layer adhesion.",),
        settings_changes=(
            {
                "key": "brim_width",
                "default": "0",
                "value": "5",
                "reason": "Improve bed adhesion",
            },
        ),
        pre_print_checklist=(
            {"item": "Open bundle in Bambu Studio", "status": "pending"},
        ),
    )

    html = render_html_report(report_dict, layout=layout)

    assert 'class="report-section section-input"' in html
    assert 'class="report-section section-mesh-repair"' in html
    assert 'class="report-section section-bed-fit"' in html
    assert 'class="report-section section-slice-summary"' in html
    assert 'class="report-section section-warnings"' in html
    assert 'class="report-section section-settings-changes"' in html
    assert 'class="report-section section-pre-print-checklist"' in html
    assert 'class="artifact-card artifact-original-input"' in html
    assert 'class="artifact-card artifact-generated-mesh"' in html
    assert 'class="artifact-card artifact-repaired-mesh"' in html
    assert 'class="artifact-card artifact-preview artifact-preview-card"' in html
    assert 'class="slice-metric-grid"' in html
    assert 'class="warning-list"' in html
    assert 'class="settings-change"' in html
    assert 'class="checklist-item checklist-status-pending"' in html
    assert "Mesh and Repair" in html
    assert "Bed Fit" in html
    assert "min_margin_mm" in html
    assert "140" in html
    assert "3h 12m" in html


def test_render_html_report_promotes_prompt_reference_quote_receipt(tmp_path: Path):
    source = tmp_path / "prompt.txt"
    source.write_text("small ergonomic wall hook\n", encoding="utf-8")
    layout = create_run(source, tmp_path / "runs", run_id="run-html-prompt-provider")
    stages = (
        StageReceipt(
            stage="prompt_reference_generation",
            status=StageStatus.FAILED,
            message="OpenAI prompt image estimated cost 0.25 USD exceeds cap 0.05 USD",
            metrics={
                "provider": "openai",
                "provider_quote": {
                    "provider": "openai",
                    "privacy_mode": "remote_api",
                    "estimated_seconds": 45.0,
                    "estimated_cost_usd": 0.25,
                    "max_cost_usd": 0.05,
                    "remote_upload": True,
                    "stores_prompt_with_provider": True,
                },
            },
        ),
    )
    report_dict = build_run_report_dict(layout, stages=stages)

    html = render_html_report(report_dict, layout=layout)

    assert 'class="report-section section-prompt-reference"' in html
    assert "Prompt Reference" in html
    assert "OpenAI" in html
    assert "failed" in html
    assert "remote API" in html
    assert "$0.25" in html
    assert "$0.05" in html
    assert "Budget blocked before remote work" in html
    assert "prompt may be stored by provider" in html
    assert "OpenAI prompt image estimated cost 0.25 USD exceeds cap 0.05 USD" in html


def test_render_html_report_uses_honest_empty_slice_and_preflight_copy(
    tmp_path: Path,
) -> None:
    source = tmp_path / "reference.png"
    source.write_bytes(b"fake image")
    layout = create_run(source, tmp_path / "runs", run_id="run-html-empty-receipts")
    report_dict = build_run_report_dict(layout, stages=())

    html = render_html_report(report_dict, layout=layout)

    assert "No slice receipt recorded for this report." in html
    assert "No pre-print checklist recorded for this report." in html
    assert "pending final slice gate integration" not in html


def test_render_html_report_surfaces_physical_evidence_packet(tmp_path: Path) -> None:
    source = tmp_path / "reference.png"
    source.write_bytes(b"fake image")
    layout = create_run(source, tmp_path / "runs", run_id="run-html-physical")
    report_dict = build_run_report_dict(
        layout,
        stages=(),
        physical_evidence={
            "print_status": "passed",
            "object_label": "flex coupon",
            "operator": "Zohar",
            "material": "SUNLU TPU 90A",
            "printer": "Bambu Lab P2S",
            "missing_required_evidence": [],
            "packet_paths": {
                "json": "90_physical/physical_evidence.json",
                "markdown": "90_physical/physical_evidence.md",
            },
            "artifacts": [
                {
                    "label": "Flexed coupon photo",
                    "kind": "photo",
                    "path": "90_physical/artifacts/coupon.jpg",
                }
            ],
        },
    )

    html = render_html_report(report_dict, layout=layout)

    assert 'class="report-section section-physical-evidence"' in html
    assert "Physical Evidence" in html
    assert "passed" in html
    assert "flex coupon" in html
    assert "Zohar" in html
    assert "No missing required evidence" in html
    assert 'href="../90_physical/physical_evidence.json"' in html
    assert 'href="../90_physical/physical_evidence.md"' in html
    assert 'href="../90_physical/artifacts/coupon.jpg"' in html


def test_render_html_report_embeds_preview_cards_and_highlights_print_artifacts(
    tmp_path: Path,
):
    source = tmp_path / "reference.png"
    source.write_bytes(b"fake image")
    layout = create_run(source, tmp_path / "runs", run_id="run-html-previews")

    preview_svg = layout.reports_dir / "bed-fit.svg"
    contact_sheet = layout.reports_dir / "contact-sheet.html"
    oriented_mesh = layout.geometry_dir / "oriented.stl"
    repaired_mesh = layout.repair_dir / "repaired.stl"
    bundle = layout.bundle_dir / "ready.3mf"
    slice_log = layout.slice_dir / "slice.log"
    preview_svg.write_text("<svg></svg>\n", encoding="utf-8")
    contact_sheet.write_text("<!doctype html><title>Contact</title>\n", encoding="utf-8")
    for artifact_path in (oriented_mesh, repaired_mesh, bundle, slice_log):
        artifact_path.write_text("artifact\n", encoding="utf-8")

    report_dict = {
        "schema_version": 1,
        "run_id": "run-html-previews",
        "stages": [
            {
                "stage": "mesh repair",
                "status": "succeeded",
                "message": "Mesh repaired and oriented.",
                "artifacts": [
                    {
                        "kind": "repaired_mesh",
                        "path": "30_repair/repaired.stl",
                        "label": "Repaired mesh",
                    },
                    {
                        "kind": "oriented_mesh",
                        "path": "40_geometry/oriented.stl",
                        "label": "Oriented mesh",
                    },
                ],
            },
            {
                "stage": "bed fit",
                "status": "succeeded",
                "message": "Generated bed-fit preview.",
                "artifacts": [
                    {
                        "kind": "preview",
                        "path": "80_reports/bed-fit.svg",
                        "label": "Bed-fit preview",
                    },
                ],
            },
            {
                "stage": "slice",
                "status": "succeeded",
                "message": "Slice completed.",
                "artifacts": [
                    {
                        "kind": "3mf",
                        "path": "60_bundle/ready.3mf",
                        "label": "Bambu 3MF bundle",
                    },
                    {
                        "kind": "slice_log",
                        "path": "70_slice/slice.log",
                        "label": "Slice log",
                    },
                ],
                "metrics": {"layers": 222, "mass_g": 118.5},
            },
        ],
        "artifacts": [
            {
                "kind": "preview",
                "path": "80_reports/bed-fit.svg",
                "label": "Bed-fit preview",
            },
            {
                "kind": "preview",
                "path": "80_reports/contact-sheet.html",
                "label": "Contact sheet",
            },
            {
                "kind": "oriented_mesh",
                "path": "40_geometry/oriented.stl",
                "label": "Oriented mesh",
            },
            {
                "kind": "repaired_mesh",
                "path": "30_repair/repaired.stl",
                "label": "Repaired mesh",
            },
            {
                "kind": "3mf",
                "path": "60_bundle/ready.3mf",
                "label": "Bambu 3MF bundle",
            },
            {
                "kind": "slice_log",
                "path": "70_slice/slice.log",
                "label": "Slice log",
            },
        ],
    }

    html = render_html_report(report_dict, layout=layout)

    assert 'class="report-section section-previews"' in html
    assert 'class="artifact-card artifact-preview artifact-preview-card"' in html
    assert '<img class="artifact-preview-embed"' in html
    assert 'src="bed-fit.svg"' in html
    assert '<iframe class="artifact-preview-embed"' in html
    assert 'src="contact-sheet.html"' in html
    assert 'class="artifact-card artifact-repaired-mesh"' in html
    assert 'class="artifact-card artifact-oriented-mesh"' in html
    assert 'class="artifact-card artifact-3mf artifact-print-bundle"' in html
    assert 'download="ready.3mf"' in html
    assert 'class="artifact-card artifact-slice-log artifact-slice-artifact"' in html


def test_write_html_report_writes_report_artifact(tmp_path: Path):
    source = tmp_path / "reference.png"
    source.write_bytes(b"fake image")
    layout = create_run(source, tmp_path / "runs", run_id="run-html-002")
    receipt = StageReceipt(
        stage="input",
        status=StageStatus.SUCCEEDED,
        message="Stored original input.",
        artifacts=(
            Artifact(
                kind=ArtifactKind.ORIGINAL_INPUT,
                path=layout.original_input,
                label="Original input",
            ),
        ),
    )
    report_dict = build_run_report_dict(layout, stages=(receipt,))

    artifact = write_html_report(layout, report_dict)

    report_path = layout.reports_dir / "run_report.html"
    assert artifact == Artifact(
        kind=ArtifactKind.REPORT,
        path=report_path,
        label="Run report HTML",
    )
    html = report_path.read_text(encoding="utf-8")
    assert "<!doctype html>" in html
    assert "run-html-002" in html
    assert 'href="../00_input/reference.png"' in html
