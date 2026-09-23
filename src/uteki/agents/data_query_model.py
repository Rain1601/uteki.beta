"""Compatibility alias; implementation: :mod:`uteki.agents.data_query.model`."""
import sys
from .data_query import model as _implementation

sys.modules[__name__] = _implementation
