class ChisEvalError(Exception):
    """Base class for user-facing pipeline errors."""


class ConfigurationError(ChisEvalError):
    """Raised when a configuration file is invalid."""


class SourceNotApprovedError(ChisEvalError):
    """Raised when a source does not pass the crawl safety gate."""


class AdapterNotFoundError(ChisEvalError):
    """Raised when an approved source has no implemented adapter."""


class OcrRequiredError(ChisEvalError):
    """Raised when a scanned PDF requires the optional OCR workflow."""


class ReviewMergeError(ChisEvalError):
    """Raised when a review sheet cannot be safely merged."""
