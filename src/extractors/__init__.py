"""Extractors package.

Importing this package registers all built-in extractors (the import side effect
populates the registry). New extractors should be imported here too.
"""

from . import ats_extractor  # noqa: F401  (registration side effect)
from . import csv_extractor  # noqa: F401  (registration side effect)
from . import github_extractor  # noqa: F401  (registration side effect)
from . import notes_extractor  # noqa: F401  (registration side effect)
from . import resume_extractor  # noqa: F401  (registration side effect)
from .base import Extractor, get_extractor, known_sources, register

__all__ = ["Extractor", "get_extractor", "known_sources", "register"]
