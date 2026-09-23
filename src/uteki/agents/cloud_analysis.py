"""Compatibility alias; implementation: :mod:`uteki.agents.analysis.cloud_analysis`."""
import sys
from .analysis import cloud_analysis as _implementation

sys.modules[__name__] = _implementation
