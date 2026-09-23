"""Compatibility alias; implementation: :mod:`uteki.agents.reading.document_reader`."""
import sys
from .reading import document_reader as _implementation

sys.modules[__name__] = _implementation
