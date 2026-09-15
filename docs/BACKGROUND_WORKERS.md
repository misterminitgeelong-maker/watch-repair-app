# Background workers

The recurring sweeps — quote reminders, dispatch pool moves and alerts, report
emails, notification redelivery, retention — can run in either of two places:

1. **Inside the web process** (the default, and how this has always run).
2. **As a separate worker service** running `python -m app.worker`.

Both use the same image and the same code. The only difference is the start
command and one environment variable.

## Why move them out

The sweeps are not cheap. They render and send email and SMS, and run report
queries across a whole tenant. They run on threads inside a uvicorn process
started with `--workers 1`, so a sweep and an HTTP request compete for the same
GIL and the same database connection pool. A slow sweep shows up as slow
requests, and it does so at whatever interval the sweep runs on — which is why
it looks intermittent and unrelated to load.

Splitting them out also means the web service can be scaled, restarted, or
rolled without thinking about what that does to a half-finished sweep.

## Deploying the worker

The rollout is deliberately two steps, and **it is safe to sit between them for
as long as you like**. Every sweep takes a Postgres advisory lock before doing
anything, so if both the web process and the worker are running sweeps at the
same time, one of them does the work and the other skips. Nothing fires twice.

### 1. Create the worker service

On Railway: add a second service from the same repository, so it builds the same
image, and set its start command to:

```
python -m app.worker
```

Give it the same environment variables as the web service — at minimum
`DATABASE_URL`, `JWT_SECRET`, and whatever mail/SMS provider credentials are set.
It needs no `PORT` and no health check: it serves no HTTP.

Do **not** give it the `preDeployCommand`. Migrations should run once per deploy,
from the web service, not from two services racing the same DDL.

### 2. Hand the sweeps over

Once the worker is up and you can see it logging `Worker starting with N
sweep(s)`, set on the **web** service:

```
RUN_SWEEPS_IN_WEB_PROCESS=false
```

The web process then serves HTTP and nothing else.

To roll back, set it to `true` (or remove it) and redeploy. The worker can keep
running while you do; the lock sorts it out.

## Operating it

```bash
python -m app.worker --list        # what exists, whether enabled, how often
python -m app.worker --once        # one pass of every enabled sweep, then exit
python -m app.worker --once retention quote_reminders
```

`--once` exits non-zero if any sweep raised, so it is safe to use from a cron or
a one-shot job. It reports `skipped: another instance holds the lock` rather than
silently doing nothing, so a hand-run during an active sweep is not mistaken for
a sweep that found no work.

An unknown sweep name is an error, not a no-op — `--once quote_remindrs` tells
you the name is wrong and lists the valid ones.

## Shutdown

The worker handles `SIGTERM` and `SIGINT`. The sweep loops wait on an event
rather than sleeping, so they stop as soon as they are asked instead of sleeping
out the rest of their interval — retention runs every six hours, so the
difference is between stopping in under a second and being `SIGKILL`ed by the
platform.

In-flight sweeps get `WORKER_SHUTDOWN_GRACE_SECONDS` (default 20) to finish. If
one is still running after that, the worker logs which one and exits anyway,
rather than reporting a clean shutdown it did not have.

## Settings

| Variable | Default | Meaning |
|---|---|---|
| `RUN_SWEEPS_IN_WEB_PROCESS` | `true` | Whether the web process runs the sweeps itself. Set `false` once the worker service is deployed. |
| `WORKER_SHUTDOWN_GRACE_SECONDS` | `20` | How long a stopping worker waits for an in-flight sweep. |

Each sweep keeps its own existing `*_ENABLED` and `*_CHECK_INTERVAL_MINUTES`
settings, and those apply wherever the sweep runs. Disabling a sweep disables it
in both places.

## What the worker does not do

It does not run the optional startup seed. That is deployment bootstrap rather
than recurring work, and running it from two processes is how two seed attempts
end up racing on boot. It stays in the web process.

## A note on replicas

Moving the sweeps out does **not** change the web service's replica count, and
this change does not raise it.

If you later scale the web service past one replica, note that
`RATE_LIMIT_STORAGE_URI` is unset, so the slowapi limiter keeps its counters in
each process's memory. Two replicas means two independent counters, and the
effective rate limit doubles — silently, with no error and nothing in the logs.
Point the limiter at Redis in the same change that raises the replica count.

The worker service itself is exempt from this: it serves no HTTP, so it has no
rate limiter, and running one worker alongside any number of web replicas is
fine. The advisory locks mean running more than one worker is also safe, though
there is currently no reason to.
