# Security Policy

ShadowRealms AI is a hobby project that you host yourself (Docker + a local LLM). There are no hosted instances that I run for other people.

## Supported versions

Only the latest `main` gets fixes. If you're on an older release, update first and check if the problem is still there.

## Reporting a vulnerability

Please don't open a public issue for security problems.

Use GitHub's private reporting instead: go to the **Security** tab of this repo and click **Report a vulnerability**. Include what you found, how to reproduce it, and what version or commit you tested.

I'll reply as soon as I can, usually within a week, and let you know if and when it gets fixed. Happy to credit you in the changelog if you want.

## Things that are your job when self-hosting

- Generate your own secrets in `.env` (see `env.template` and `docs/POSTGRESQL_ENV_SETUP.md`), never reuse the examples.
- Keep `.env` and `backend/invites.json` out of git (both are gitignored).
- Don't expose the stack to the internet without HTTPS in front of it. The backend runs Flask's dev server.
