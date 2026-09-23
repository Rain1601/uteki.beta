"""Compatibility alias; implementation: :mod:`uteki.agents.runtime.local_credentials`."""
import sys
from .runtime import local_credentials as _implementation

sys.modules[__name__] = _implementation
