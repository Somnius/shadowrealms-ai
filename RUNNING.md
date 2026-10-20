# Running the site

How to start, stop and check ShadowRealms AI on the machine it runs on. For the first install (`.env`, invite codes, downloading the models, building the frontend) see the [README](README.md#quick-start).

## After a reboot

Docker is not set to start at boot on this machine, and LM Studio does not start its server by itself, so after every reboot the site is down (nginx answers with nothing or a 502) until you run:

```bash
./site.sh start
```

It does, in order:

1. Starts the LM Studio server and loads `llama-krikri-8b-instruct` (32768 context) and `text-embedding-bge-m3`, unless they are already loaded. Use `./site.sh start --no-ai` to skip this, or `KRIKRI_CONTEXT=16384 ./site.sh start` on a smaller card.
2. Starts Docker if it is not running.
3. Starts every container: nginx, backend, PostgreSQL, Redis, ChromaDB, monitoring, and the speech container when `SPEECH_SECRET` is set in `.env`.
4. Waits until the backend is healthy, then prints what the site answers and whether LM Studio and Ollama are up.

When it ends with `Site: http://localhost/ -> 200, backend v…` the site is up.

Ollama runs as its own system service and normally starts at boot; `./site.sh status` tells you if it isn't answering.

## Commands

| Command | What it does |
|---|---|
| `./site.sh start` | Start LM Studio and its models, Docker and all containers, and wait for the backend. |
| `./site.sh start --no-ai` | The same without LM Studio. |
| `./site.sh stop` | Stop all containers. Nothing is deleted: the database and files stay in the Docker volumes and `data/`. LM Studio is left running. |
| `./site.sh restart` | Stop, then start. |
| `./site.sh status` | The containers, the site's answer and the version, LM Studio and Ollama. It does not wake Docker if Docker is off. |
| `./site.sh logs` | Follow the logs of every container. `./site.sh logs backend` for one. Ctrl+C to leave. |

`./docker-up.sh` still works: it only runs `docker compose up -d` (extra arguments pass through, e.g. `--build`).

## Why stop with the script

The containers have `restart: unless-stopped`. Stopped with `./site.sh stop`, they stay stopped even when Docker restarts. Left running, they come back as soon as Docker starts, and any `docker` command (even `docker ps`) starts Docker through its socket.

## When something is wrong

- **502 Bad Gateway:** nginx is up but the backend isn't answering yet. Wait for `./site.sh start` to finish, or check `./site.sh logs backend`.
- **No answer at all:** Docker or nginx is down. Run `./site.sh status`, then `./site.sh start`.
- **The site loads but the Storyteller doesn't answer:** LM Studio is down or the model isn't loaded. Run `./site.sh status`; in a chronicle chat, `/ai health` checks LM Studio, Ollama and ChromaDB.
- **After a code update:** `./scripts/build-frontend.sh` for the frontend, and `docker compose up -d --force-recreate backend` for the backend.

## Starting at boot instead

If you ever want the containers back on their own after a reboot, enable Docker once with `sudo systemctl enable docker.service`. LM Studio would still need `lms server start` and the model loads, or `./site.sh start`.
