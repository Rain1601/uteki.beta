"""Compatibility alias; implementation: :mod:`uteki.agents.archive.archive_rerun`."""
import sys
from .archive import archive_rerun as _implementation

sys.modules[__name__] = _implementation
