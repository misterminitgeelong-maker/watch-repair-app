"""Logging was never configured, so the application's INFO records were dropped.

These tests pin the two things that were actually wrong — INFO going nowhere,
and warnings arriving without a timestamp or logger name — plus the two ways a
fix like this usually goes wrong: printing everything twice, and turning on
every third-party library's INFO stream.
"""
from __future__ import annotations

import logging
import sys

import pytest

from app.logging_config import APP_LOGGER_NAMES, _MARKER, configure_logging


@pytest.fixture
def clean_logging():
    """Restore the real logging state; these tests mutate global config."""
    root = logging.getLogger()
    saved_handlers = list(root.handlers)
    saved_root_level = root.level
    saved_levels = {n: logging.getLogger(n).level for n in APP_LOGGER_NAMES}
    saved_levels["sqlalchemy.engine"] = logging.getLogger("sqlalchemy.engine").level
    # The handler is a module-level singleton, so it survives this test and keeps
    # whatever stream it was last pointed at. capsys closes its pipe at the end of
    # the test, so without restoring the stream the next test writes to a closed
    # file. Save the stream, not just the handler list.
    saved_streams = [(h, h.stream) for h in saved_handlers if isinstance(h, logging.StreamHandler)]
    try:
        yield
    finally:
        root.handlers = saved_handlers
        root.setLevel(saved_root_level)
        for name, level in saved_levels.items():
            logging.getLogger(name).setLevel(level)
        for handler, stream in saved_streams:
            # Assign directly: setStream() flushes the current stream first, and
            # by teardown that is capsys's already-closed pipe.
            handler.stream = stream


def _our_handlers():
    return [h for h in logging.getLogger().handlers if getattr(h, _MARKER, False)]


def test_application_info_records_are_emitted(clean_logging, capsys):
    """The regression: every logger.info in the app went nowhere."""
    configure_logging("INFO")
    logging.getLogger("mainspring.startup").info("schema check passed")
    logging.getLogger("app.sweeps").info("sweep summary")

    out = capsys.readouterr().out
    assert "schema check passed" in out
    assert "sweep summary" in out


def test_records_carry_a_timestamp_level_and_logger_name(clean_logging, capsys):
    """Warnings did reach stderr before this, via logging.lastResort — but as a
    bare message, which is close to useless in a platform log viewer."""
    configure_logging("INFO")
    logging.getLogger("mainspring.worker").warning("sweep skipped")

    out = capsys.readouterr().out.strip()
    assert "WARNING" in out
    assert "mainspring.worker" in out
    assert "sweep skipped" in out
    # A leading ISO-ish date, e.g. "2026-09-15 04:42:02".
    assert out[:4].isdigit() and out[4] == "-", f"no timestamp on: {out!r}"


def test_both_logger_trees_are_covered(clean_logging, capsys):
    """The app uses getLogger(__name__) ('app.*') in 32 places and explicit
    'mainspring.*' names in the rest. Covering only one would silence the other."""
    configure_logging("INFO")
    for name in APP_LOGGER_NAMES:
        assert logging.getLogger(name).level == logging.INFO


def test_third_party_info_stays_out_of_the_log(clean_logging, capsys):
    """Setting the root logger to INFO would turn on SQLAlchemy's statement log
    and drown everything that matters."""
    configure_logging("INFO")
    logging.getLogger("sqlalchemy.engine").info("SELECT 1")
    logging.getLogger("httpx").info("HTTP Request: GET ...")

    out = capsys.readouterr().out
    assert "SELECT 1" not in out
    assert "HTTP Request" not in out
    assert logging.getLogger().level == logging.WARNING


def test_third_party_warnings_still_get_through(clean_logging, capsys):
    """Quieting INFO must not also hide a library telling us something is wrong."""
    configure_logging("INFO")
    logging.getLogger("sqlalchemy.engine").warning("connection pool exhausted")
    assert "connection pool exhausted" in capsys.readouterr().out


def test_calling_twice_does_not_duplicate_every_line(clean_logging, capsys):
    """The web process configures at import; the worker configures at startup.
    Stacking handlers would print each record once per call."""
    configure_logging("INFO")
    configure_logging("INFO")
    assert len(_our_handlers()) == 1

    logging.getLogger("mainspring.startup").info("only once please")
    assert capsys.readouterr().out.count("only once please") == 1


def test_level_is_configurable(clean_logging, capsys):
    configure_logging("WARNING")
    logging.getLogger("mainspring.startup").info("should not appear")
    logging.getLogger("mainspring.startup").warning("should appear")

    out = capsys.readouterr().out
    assert "should not appear" not in out
    assert "should appear" in out


def test_an_unknown_level_falls_back_to_info_instead_of_silencing_everything(
    clean_logging, capsys
):
    """logging.getLevelName returns 'Level BOGUS' rather than raising, so a typo
    in LOG_LEVEL would otherwise disable logging with no indication why."""
    configure_logging("BOGUS")
    logging.getLogger("mainspring.startup").info("still logging")
    assert "still logging" in capsys.readouterr().out


def test_logs_go_to_stdout(clean_logging):
    """Platform log collectors read stdout; stderr gets treated as error output."""
    configure_logging("INFO")
    assert _our_handlers()[0].stream is sys.stdout


def test_reconfiguring_survives_a_closed_previous_stream(clean_logging):
    """configure_logging is called at import and again at worker startup, so it
    must never be able to bring the process down.

    setStream() flushes the outgoing stream before swapping, which raises if that
    stream has been closed — which is exactly what happens when the first call
    bound a stream that something later closed.
    """
    import tempfile

    configure_logging("INFO")
    handler = _our_handlers()[0]

    # A closed io.StringIO would not do: its flush() is a silent no-op. Only a
    # real file object raises on flush after close, which is what the actual
    # failure looked like (pytest's capture file, closed at end of test).
    dead = tempfile.TemporaryFile(mode="w")
    dead.close()
    with pytest.raises(ValueError):
        dead.flush()  # the precondition this test depends on
    handler.stream = dead

    configure_logging("INFO")  # must not raise

    assert handler.stream is sys.stdout
    logging.getLogger("mainspring.startup").info("recovered")
