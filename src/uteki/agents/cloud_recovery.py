"""Compatibility alias; implementation: :mod:`uteki.agents.analysis.cloud_recovery`."""
import sys
from .analysis import cloud_recovery as _implementation

sys.modules[__name__] = _implementation
