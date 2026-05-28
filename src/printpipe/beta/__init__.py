"""Beta capture helpers for PrintPipe."""

from printpipe.beta.failures import (
    FAILURE_REPORT_REQUIRED_HEADINGS,
    FAILURE_REPORT_SCHEMA_VERSION,
    FailureArtifact,
    FailureReport,
    build_failure_report,
    missing_required_headings,
    parse_failure_report_sections,
)
from printpipe.beta.physical import (
    PHYSICAL_EVIDENCE_REQUIRED_HEADINGS,
    PHYSICAL_EVIDENCE_SCHEMA_VERSION,
    PhysicalArtifact,
    PhysicalPrintEvidence,
    build_physical_print_evidence,
    missing_required_evidence,
    render_physical_evidence_markdown,
)
from printpipe.beta.regression import (
    ExpectedOutcome,
    RegressionCase,
    RegressionManifest,
    case_from_run,
    load_regression_manifest,
    render_command,
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
    "PhysicalArtifact",
    "PhysicalPrintEvidence",
    "RegressionCase",
    "RegressionManifest",
    "build_failure_report",
    "build_physical_print_evidence",
    "case_from_run",
    "load_regression_manifest",
    "missing_required_evidence",
    "missing_required_headings",
    "parse_failure_report_sections",
    "render_physical_evidence_markdown",
    "render_command",
    "validate_regression_manifest",
    "write_regression_manifest",
)
