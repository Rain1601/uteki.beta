"""Compatibility alias; implementation: :mod:`uteki.agents.analysis.narrative_contract`."""
import sys
from .analysis import narrative_contract as _implementation

sys.modules[__name__] = _implementation
