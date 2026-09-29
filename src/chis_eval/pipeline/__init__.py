from .deduplicate import DeduplicationResult, deduplicate_records
from .normalize import normalise_record, normalise_records
from .validate import ValidationSummary, validate_records

__all__ = [
    "DeduplicationResult",
    "ValidationSummary",
    "deduplicate_records",
    "normalise_record",
    "normalise_records",
    "validate_records",
]
