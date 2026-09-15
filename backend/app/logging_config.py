"""One place that decides where this application's log records go.

Until now nothing configured logging at all. Under uvicorn that is not neutral:
uvicorn's own dictConfig sets up only the ``uvicorn*`` loggers, leaving the root
logger with no handler, so every record from this application fell through to
``logging.lastResort`` — a bare stderr handler fixed at WARNING.

The consequences were specific, and worth stating because the second one is the
opposite of what "no logging configured" usually implies:

* every ``logger.info`` in the application was dropped. That included the
  startup schema-check line and each sweep's summary, so the log said nothing
  about whether background work was running at all.
* ``logger.warning`` and ``logger.exception`` *did* reach stderr — failing
  sweeps were never silent — but with no timestamp, no level and no logger
  name, because lastResort formats the bare message and nothing else.

So this is not "turn logging on". It is "make the records that were already
being emitted legible, and stop dropping the informational ones".

Third-party loggers stay at WARNING. Setting the root to INFO would turn on
SQLAlchemy, httpx and botocore's INFO streams, which is how a log becomes
something nobody reads.
"""
from __future__ import annotations

import logging
import sys

# The two logger trees this application actually uses: `app.*` from
# getLogger(__name__), and `mainspring.*` from the explicitly named loggers.
APP_LOGGER_NAMES = ("app", "mainspring")

_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Marks the handler as ours so repeated calls update it instead of stacking a
# second copy and printing everything twice.
_MARKER = "_mainspring_handler"


def configure_logging(level: str | int | None = None) -> None:
    """Install one stdout handler and set this application's loggers to ``level``.

    Safe to call more than once — the web process calls it at import and the
    worker calls it at startup, and a reload should not double every line.
    """
    from .config import settings

    resolved = level if level is not None else settings.log_level
    if isinstance(resolved, str):
        resolved = logging.getLevelName(resolved.strip().upper())
    if not isinstance(resolved, int):
        # getLevelName returns "Level %s" for anything it does not know, rather
        # than raising, so a typo would otherwise silently disable logging.
        resolved = logging.INFO

    root = logging.getLogger()
    existing = next((h for h in root.handlers if getattr(h, _MARKER, False)), None)
    if existing is None:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(_FORMAT, datefmt=_DATE_FORMAT))
        setattr(handler, _MARKER, True)
        root.addHandler(handler)
    else:
        handler = existing

    # StreamHandler binds the stream object, not the name, so a handler built at
    # import time keeps whatever sys.stdout was then. Re-point it when it has
    # changed, so reconfiguring after something replaced sys.stdout takes effect.
    if handler.stream is not sys.stdout:
        try:
            handler.setStream(sys.stdout)
        except ValueError:
            # setStream flushes the outgoing stream first, which raises if that
            # stream has already been closed. Nothing to flush in that case, and
            # a logging-setup call must not be able to bring the process down.
            handler.stream = sys.stdout
    handler.setLevel(logging.DEBUG)  # the loggers decide, not the handler
    # Leave the root at WARNING so third-party INFO stays out of the log.
    if root.level == logging.NOTSET or root.level > logging.WARNING:
        root.setLevel(logging.WARNING)
    for name in APP_LOGGER_NAMES:
        logging.getLogger(name).setLevel(resolved)
