"""Aggregated models package.

Split from the former monolithic models.py. Re-exports every symbol so that
existing `from ..models import X` / `from app.models import X` imports keep
working unchanged.
"""
from .base import *  # noqa: F401,F403
from .tables import *  # noqa: F401,F403
from .schemas import *  # noqa: F401,F403
