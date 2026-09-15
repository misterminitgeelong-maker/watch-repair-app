"""The worker CLI is an operational tool — it has to fail clearly, not quietly.

`--once` in particular is what someone reaches for at 2am to force a sweep by
hand, so a typo in a sweep name must say so rather than exiting 0 having done
nothing.
"""
from __future__ import annotations

import pytest

from app import worker
from app.sweeps import Sweep


def test_list_shows_every_sweep_with_its_state(capsys):
    assert worker.main(["--list"]) == 0
    out = capsys.readouterr().out
    for name in ("quote_reminders", "retention", "notification_redelivery"):
        assert name in out
    assert "every" in out


def test_unknown_sweep_name_is_rejected_loudly():
    """Exiting 0 on a typo would let an operator believe the sweep had run."""
    with pytest.raises(SystemExit) as exc:
        worker._select(["retention", "quote_remindrs"])
    assert "quote_remindrs" in str(exc.value)
    assert "Known:" in str(exc.value), "the error should say what the valid names are"


def test_no_names_means_every_enabled_sweep():
    from app.sweeps import enabled_sweeps

    assert [s.name for s in worker._select([])] == [s.name for s in enabled_sweeps()]


def test_named_sweeps_resolve_in_the_order_given():
    selected = worker._select(["retention", "quote_reminders"])
    assert [s.name for s in selected] == ["retention", "quote_reminders"]


def test_run_once_reports_failure_in_the_exit_code(monkeypatch):
    """A cron or one-shot job that fails must not look successful."""
    boom = Sweep(
        name="boom",
        enabled=True,
        interval_minutes=1,
        load=lambda: (_ for _ in ()).throw(RuntimeError("nope")),
    )
    monkeypatch.setattr(worker, "_select", lambda names: [boom])
    assert worker.run_once(["boom"]) == 1


def test_run_once_succeeds_when_the_sweep_succeeds(monkeypatch):
    ok = Sweep(
        name="ok",
        enabled=True,
        interval_minutes=1,
        load=lambda: (lambda _session: {"did": 1}),
    )
    monkeypatch.setattr(worker, "_select", lambda names: [ok])
    assert worker.run_once(["ok"]) == 0


def test_sweep_names_without_once_is_an_error():
    """`python -m app.worker retention` reads like 'run retention now'; running
    the full daemon instead would be a surprising way to be wrong."""
    with pytest.raises(SystemExit) as exc:
        worker.main(["retention"])
    assert exc.value.code != 0


def test_worker_does_not_run_the_startup_seed():
    """Seeding is deployment bootstrap. Running it from both the web process and
    the worker is how two seed attempts end up racing on boot."""
    source = (worker.__file__ or "")
    assert source
    with open(source, encoding="utf-8") as fh:
        text = fh.read()
    assert "_run_optional_startup_tasks" not in text
    assert "startup_seed" not in text
