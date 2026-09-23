"""Compatibility alias; implementation: :mod:`uteki.agents.data_query.loop`."""
import sys
from .data_query import loop as _implementation

sys.modules[__name__] = _implementation
