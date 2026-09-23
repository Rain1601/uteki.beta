"""Compatibility alias; implementation: :mod:`uteki.agents.analysis.numeric_review`."""
import sys
from .analysis import numeric_review as _implementation

sys.modules[__name__] = _implementation
