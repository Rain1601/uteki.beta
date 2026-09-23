"""Compatibility alias; implementation: :mod:`uteki.agents.analysis.analysis_comparison`."""
import sys
from .analysis import analysis_comparison as _implementation

sys.modules[__name__] = _implementation
