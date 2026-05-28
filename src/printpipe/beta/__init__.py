"""Beta capture helpers for PrintPipe."""

from printpipe.beta.failures import (
    FAILURE_REPORT_REQUIRED_HEADINGS,
    FAILURE_REPORT_SCHEMA_VERSION,
    FailureArtifact,
    FailureReport,
    build_failure_report,
    missing_required_headings,
    parse_failure_report_sections,
    render_failure_report_markdown,
    write_failure_report_files,
)
from printpipe.beta.physical import (
    PHYSICAL_EVIDENCE_REQUIRED_HEADINGS,
    PHYSICAL_EVIDENCE_SCHEMA_VERSION,
    PhysicalArtifact,
    PhysicalPrintEvidence,
    build_physical_print_evidence,
    missing_required_evidence,
    render_physical_evidence_markdown,
    write_physical_evidence_files,
)
from printpipe.beta.physical_status import (
    build_physical_validation_status,
    render_physical_validation_status,
)
from printpipe.beta.physical_start import start_physical_validation
from printpipe.beta.physical_plan import (
    PROOF_BOUNDARY,
    build_physical_validation_plan,
    render_physical_validation_plan,
)
from printpipe.beta.readiness import build_beta_readiness_report, render_beta_readiness_report
from printpipe.beta.regression import (
    ExpectedOutcome,
    RegressionCase,
    RegressionManifest,
    case_from_run,
    load_regression_manifest,
    render_command,
    run_regression_manifest,
    validate_regression_manifest,
    write_regression_manifest,
)

__all__ = (
    "ExpectedOutcome",
    "FAILURE_REPORT_REQUIRED_HEADINGS",
    "FAILURE_REPORT_SCHEMA_VERSION",
    "FailureArtifact",
    "FailureReport",
    "PHYSICAL_EVIDENCE_REQUIRED_HEADINGS",
    "PHYSICAL_EVIDENCE_SCHEMA_VERSION",
    "PROOF_BOUNDARY",
    "PhysicalArtifact",
    "PhysicalPrintEvidence",
    "RegressionCase",
    "RegressionManifest",
    "build_failure_report",
    "build_beta_readiness_report",
    "build_physical_print_evidence",
    "build_physical_validation_plan",
    "build_physical_validation_status",
    "case_from_run",
    "load_regression_manifest",
    "missing_required_evidence",
    "missing_required_headings",
    "parse_failure_report_sections",
    "render_failure_report_markdown",
    "render_physical_evidence_markdown",
    "render_physical_validation_plan",
    "render_physical_validation_status",
    "render_beta_readiness_report",
    "start_physical_validation",
    "render_command",
    "run_regression_manifest",
    "validate_regression_manifest",
    "write_physical_evidence_files",
    "write_failure_report_files",
    "write_regression_manifest",
)
