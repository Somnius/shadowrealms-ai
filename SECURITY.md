# Security Policy

ShadowRealms AI is a hobby project that you host yourself (Docker + a local LLM). My own running instance is a private test server, not a public service. Please don't scan or attack it. If you find something, report it against the code and I'll check it there.

## Supported versions

Only the latest `main` gets fixes. If you're on an older release, update first and check if the problem is still there.

## Reporting a vulnerability

Please don't open a public issue for security problems.

Use GitHub's private reporting instead: go to the **Security** tab of this repo and click **Report a vulnerability**. Include what you found, how to reproduce it, and what version or commit you tested.

I'll reply as soon as I can, usually within a week, and let you know if and when it gets fixed. Happy to credit you in the changelog if you want.

## Scope

In scope: the code in this repository (backend, frontend, nginx config, Docker setup, scripts) running as documented.

Out of scope: my own running instance, setups that ignore the steps below (default secrets, services exposed without HTTPS), third-party services like LM Studio, Ollama or cloud AI providers, and findings from `npm audit` that only affect build and test tooling such as Tailwind (it never ships to the browser).

## How it's protected

The backend runs under gunicorn by default, listening on `127.0.0.1` only, with nginx in front serving the production frontend build with a strict Content-Security-Policy. Logins are rate limited and locked out after repeated failures, access tokens expire and are renewed through an HttpOnly refresh cookie, and logout revokes them on the server. The details are in [docs/SECURITY_MODEL.md](docs/SECURITY_MODEL.md).

## Things that are your job when self-hosting

- Generate your own secrets in `.env` (see `env.template` and [docs/POSTGRESQL_ENV_SETUP.md](docs/POSTGRESQL_ENV_SETUP.md)), never reuse the examples.
- Keep `.env` and `backend/invites.json` out of git (both are gitignored).
- Only expose nginx. PostgreSQL, Redis, ChromaDB, the monitoring service and the backend listen on `127.0.0.1`; keep it that way.
- Don't expose the stack to the internet without HTTPS in front of it (a reverse proxy that terminates TLS). If that proxy is on another host, put its address in `set_real_ip_from` and the `$sr_forwarded_proto` map in `nginx/nginx.conf` (they ship with the author's proxy address).
- Don't switch to the Flask dev server (`APP_SERVER=flask`) on anything reachable from outside.
