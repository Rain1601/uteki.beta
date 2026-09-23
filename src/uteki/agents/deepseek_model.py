"""Compatibility alias; implementation: :mod:`uteki.agents.runtime.deepseek_model`."""
import sys
from .runtime import deepseek_model as _implementation

sys.modules[__name__] = _implementation
