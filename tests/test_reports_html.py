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
