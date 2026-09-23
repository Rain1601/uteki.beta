"""Compatibility alias; implementation: :mod:`uteki.agents.reading.reading_groups`."""
import sys
from .reading import reading_groups as _implementation

sys.modules[__name__] = _implementation
