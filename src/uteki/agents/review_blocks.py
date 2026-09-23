"""Compatibility alias; implementation: :mod:`uteki.agents.archive.review_blocks`."""
import sys
from .archive import review_blocks as _implementation

sys.modules[__name__] = _implementation
