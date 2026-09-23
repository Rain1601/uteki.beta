"""Compatibility alias; implementation: :mod:`uteki.agents.data_query.agent`."""
import sys
from .data_query import agent as _implementation

sys.modules[__name__] = _implementation
