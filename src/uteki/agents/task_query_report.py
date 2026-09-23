"""Compatibility alias; implementation: :mod:`uteki.agents.data_query.report`."""
import sys
from .data_query import report as _implementation

sys.modules[__name__] = _implementation
