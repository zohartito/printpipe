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
    "RegressionCase",
    "RegressionManifest",
    "build_failure_report",
    "case_from_run",
    "load_regression_manifest",
    "missing_required_headings",
    "parse_failure_report_sections",
    "render_command",
    "validate_regression_manifest",
    "write_regression_manifest",
)
