"""Compatibility alias; implementation: :mod:`uteki.agents.reading.material_library`."""
import sys
from .reading import material_library as _implementation

sys.modules[__name__] = _implementation
