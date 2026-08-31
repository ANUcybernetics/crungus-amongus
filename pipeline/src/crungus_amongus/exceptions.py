"""Exception taxonomy for the per-prediction boundary.

These are the only exceptions caught during a batch run; everything else
bubbles and kills the run loudly.
"""


class PredictionError(Exception):
    """Base for errors attributable to a single prediction."""


class RetryablePredictionError(PredictionError):
    """Transient failure (timeout, 429/5xx, network) — retry with backoff."""


class PermanentPredictionError(PredictionError):
    """The model ran and failed, or its output was unusable — do not retry."""


class NsfwBlockedError(PermanentPredictionError):
    """The model's safety checker rejected the output."""


class SchemaIncompatibleError(Exception):
    """No confident prompt field found — skip the model, never guess-and-spend."""
