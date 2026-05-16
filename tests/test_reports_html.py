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
    assert 'class="artifact-card artifact-preview"' in html
    assert 'class="slice-metric-grid"' in html
    assert 'class="warning-list"' in html
    assert 'class="settings-change"' in html
    assert 'class="checklist-item checklist-status-pending"' in html
    assert "Mesh and Repair" in html
    assert "Bed Fit" in html
    assert "min_margin_mm" in html
    assert "140" in html
    assert "3h 12m" in html


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
