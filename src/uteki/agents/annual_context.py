"""Compatibility alias; implementation: :mod:`uteki.agents.archive.annual_context`."""
import sys
from .archive import annual_context as _implementation

sys.modules[__name__] = _implementation
