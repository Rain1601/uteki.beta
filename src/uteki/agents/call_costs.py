"""Compatibility alias; implementation: :mod:`uteki.agents.runtime.call_costs`."""
import sys
from .runtime import call_costs as _implementation

sys.modules[__name__] = _implementation
