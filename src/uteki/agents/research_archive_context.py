"""Compatibility alias; implementation: :mod:`uteki.agents.archive.research_archive_context`."""
import sys
from .archive import research_archive_context as _implementation

sys.modules[__name__] = _implementation
