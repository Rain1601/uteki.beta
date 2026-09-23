"""Compatibility alias; implementation: :mod:`uteki.agents.archive.hypothesis_contract`."""
import sys
from .archive import hypothesis_contract as _implementation

sys.modules[__name__] = _implementation
