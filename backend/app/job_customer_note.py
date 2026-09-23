"""Customer-facing status notes on repair jobs.

Staff notes on a status change (``change_note``) are written for the bench and
are never shown publicly. ``customer_note`` is the separate, deliberate message
to the customer ("Waiting on parts from our Swiss supplier"), shown on their
status page next to the current status.
"""
from __future__ import annotations

from datetime import datetime, timezone


def apply_customer_note(job, *, status_changed: bool, customer_note: str | None) -> None:
    """Set, replace or clear ``job.customer_note``.

    * A note given with the update replaces the current one ("" clears it).
    * A status change without a note clears it: the old note described the old
      status and would mislead once the job has moved on.
    * A same-status update without a note leaves it alone.
    """
    if customer_note is not None:
        text = customer_note.strip()
        job.customer_note = text[:280] or None
        job.customer_note_at = datetime.now(timezone.utc) if text else None
    elif status_changed:
        job.customer_note = None
        job.customer_note_at = None
