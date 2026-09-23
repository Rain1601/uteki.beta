"""Compatibility alias; implementation: :mod:`uteki.agents.archive.research_archive`."""
import sys
from .archive import research_archive as _implementation

sys.modules[__name__] = _implementation
