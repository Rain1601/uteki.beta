"""Compatibility alias; implementation: :mod:`uteki.agents.analysis.narrative_reader`."""
import sys
from .analysis import narrative_reader as _implementation

sys.modules[__name__] = _implementation
