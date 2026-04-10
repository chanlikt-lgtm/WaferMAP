"""
exceptions.py
=============
Custom exception hierarchy for the wafer plotting toolkit.

Catching WaferToolError is enough to handle any domain-level failure;
sub-classes let callers react to specific failure modes.
"""


class WaferToolError(Exception):
    """Base class for all wafer-tool errors."""


class DataLoadError(WaferToolError):
    """Raised when a data file cannot be read or parsed."""


class InsufficientDataError(WaferToolError):
    """Raised when there are too few data points to produce a plot."""


class ReportGenerationError(WaferToolError):
    """Raised when PDF / CSV / PPTX generation fails."""
