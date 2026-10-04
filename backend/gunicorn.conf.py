"""
Production server settings (v0.9 phase 5; docs/SECURITY_MODEL.md "Production server").

gthread workers: each request (including a ~55 s Server-Sent Events stream from routes/events.py
and a Storyteller reply of up to ~55 s) holds one thread, so the thread count must leave room
next to the SSE cap (SR_EVENTS_MAX_STREAMS, per process). For gthread workers `timeout` is the
worker heartbeat, not a per-request limit, so long streams are fine.

--preload: the app (and migrate_db) is built once in the master, then forked; background
threads (RAG re-embed, rule book backfill) are started in the first worker after the fork,
because threads don't survive fork() and locks held by them could deadlock the children.
Every value can be overridden with the environment variable named next to it.
"""

import os

os.environ.setdefault("SR_DEFER_BACKGROUND_JOBS", "1")


def _int(name, default):
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


# Loopback only: nginx on this host is the only client. Anything that can reach this port can
# send its own X-Forwarded-For, which the app trusts for one hop (rate limits, lockouts).
bind = os.environ.get("GUNICORN_BIND", "127.0.0.1:5000")
workers = _int("GUNICORN_WORKERS", 2)
worker_class = "gthread"
threads = _int("GUNICORN_THREADS", 48)
timeout = _int("GUNICORN_TIMEOUT", 120)             # heartbeat for gthread workers
graceful_timeout = _int("GUNICORN_GRACEFUL_TIMEOUT", 30)
keepalive = _int("GUNICORN_KEEPALIVE", 5)
preload_app = True
max_requests = 0                                     # no periodic recycling (SSE streams would drop)
forwarded_allow_ips = os.environ.get("FORWARDED_ALLOW_IPS", "127.0.0.1,::1")
limit_request_line = 8190
limit_request_fields = 100
limit_request_field_size = 8190

# Access log to stdout; %(U)s is the path WITHOUT the query string so SSE ?ticket= values and
# other query parameters never land in the logs. %({x-forwarded-for}i)s is the client nginx saw.
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("GUNICORN_LOGLEVEL", "info")
access_log_format = '%({x-forwarded-for}i)s "%(m)s %(U)s" %(s)s %(B)s %(M)sms "%(a)s"'
proc_name = "shadowrealms-backend"


def post_fork(server, worker):
    # Startup jobs once, in the first worker (worker ages start at 1). They are idempotent and
    # the re-embed takes a PostgreSQL advisory lock, so a restarted worker skipping them is fine.
    if worker.age == 1:
        try:
            import wsgi

            wsgi.start_background_jobs(wsgi.app)
        except Exception as e:  # noqa: BLE001
            server.log.warning("Background jobs not started: %s", e)
