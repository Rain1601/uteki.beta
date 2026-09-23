"""Compatibility alias; implementation: :mod:`uteki.agents.analysis.narrative_runner`."""
import sys
from .analysis import narrative_runner as _implementation

sys.modules[__name__] = _implementation
