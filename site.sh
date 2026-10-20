#!/usr/bin/env bash
#
# ShadowRealms AI — start, stop and check the whole site.
#
#   ./site.sh start     start LM Studio and its models, Docker if needed, every container,
#                       and wait for the backend (--no-ai skips LM Studio)
#   ./site.sh stop      stop every container (data stays in the volumes and data/)
#   ./site.sh restart   stop, then start
#   ./site.sh status    containers, the site's answer, LM Studio and Ollama
#   ./site.sh logs [service]   follow the logs (all services, or one: backend, nginx, ...)
#
# The voice container (profile "voice") is included when SPEECH_SECRET is set in .env.
# See RUNNING.md.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

PROFILES=()
if [ -f .env ] && grep -q '^SPEECH_SECRET=.\+' .env; then
  PROFILES=(--profile voice)
fi

compose() { docker compose "${PROFILES[@]}" "$@"; }

need_docker() {
  if docker info >/dev/null 2>&1; then
    return
  fi
  # docker.service is not enabled at boot; the first call through docker.socket starts it.
  echo "Docker is not running, waiting for it to start..."
  for _ in $(seq 1 30); do
    docker info >/dev/null 2>&1 && return
    sleep 1
  done
  echo "Docker did not start. Try: sudo systemctl start docker" >&2
  exit 1
}

site_answer() {
  local code version
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 http://localhost/ || true)
  version=$(curl -s --max-time 5 http://localhost/api/version | sed -n 's/.*"version":"\([^"]*\)".*/\1/p' || true)
  echo "Site: http://localhost/ -> ${code:-no answer}${version:+, backend $version}"
}

host_ai() {
  if curl -s --max-time 3 http://localhost:1234/v1/models >/dev/null; then
    echo "LM Studio: running"
  else
    echo "LM Studio: not answering on :1234 (run: lms server start, then load the models, see RUNNING.md)"
  fi
  if curl -s --max-time 3 http://localhost:11434/api/tags >/dev/null; then
    echo "Ollama: running"
  else
    echo "Ollama: not answering on :11434"
  fi
}

wait_backend() {
  local id state
  id=$(compose ps -q backend)
  for _ in $(seq 1 90); do
    state=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$id" 2>/dev/null || true)
    case "$state" in
      healthy|running) echo "Backend: $state"; return ;;
    esac
    sleep 2
  done
  echo "Backend is not healthy after 3 minutes. Check: ./site.sh logs backend" >&2
  return 1
}

# LM Studio runs on the host, not in Docker. Start its server and load the two models
# the README lists, unless they are already loaded. Skipped when lms is not installed.
LMS="$(command -v lms || echo "$HOME/.lmstudio/bin/lms")"
start_lm_studio() {
  if [ ! -x "$LMS" ]; then
    echo "LM Studio: lms not found, skipped"
    return
  fi
  "$LMS" server start
  local loaded
  loaded=$("$LMS" ps --json 2>/dev/null || true)
  if ! grep -q 'llama-krikri-8b-instruct' <<<"$loaded"; then
    "$LMS" load llama-krikri-8b-instruct -y --context-length "${KRIKRI_CONTEXT:-32768}"
  fi
  if ! grep -q 'text-embedding-bge-m3' <<<"$loaded"; then
    "$LMS" load text-embedding-bge-m3 -y
  fi
}

start() {
  [ "${1:-}" = "--no-ai" ] || start_lm_studio
  need_docker
  compose up -d
  wait_backend
  site_answer
  host_ai
}

stop() {
  need_docker
  compose stop
}

status() {
  # Ask systemd, not docker: any docker call wakes the daemon through its socket,
  # and the containers (restart: unless-stopped) would come up with it.
  if ! systemctl is-active --quiet docker.service; then
    echo "Docker is not running, so the site is down. Start it with: ./site.sh start"
    host_ai
    return
  fi
  compose ps -a --format 'table {{.Name}}\t{{.Status}}'
  echo
  site_answer
  host_ai
}

case "${1:-}" in
  start) start "${2:-}" ;;
  stop) stop ;;
  restart) stop; start "${2:-}" ;;
  status) status ;;
  logs) need_docker; shift; compose logs -f --tail 100 "$@" ;;
  *)
    sed -n '3,13p' "$0" | sed 's/^# \{0,1\}//'
    exit 1
    ;;
esac
