"""Compatibility alias; implementation: :mod:`uteki.agents.runtime.run_budget`."""
import sys
from .runtime import run_budget as _implementation

sys.modules[__name__] = _implementation
