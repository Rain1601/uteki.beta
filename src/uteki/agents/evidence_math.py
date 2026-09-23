"""Compatibility alias; implementation: :mod:`uteki.agents.analysis.evidence_math`."""
import sys
from .analysis import evidence_math as _implementation

sys.modules[__name__] = _implementation
