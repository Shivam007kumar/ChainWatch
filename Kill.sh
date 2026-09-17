#!/bin/bash
#
# Kill.sh — stops all ChainWatch services started by Start.sh.

set -uo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$PROJECT_ROOT/.chainwatch_pids"

echo "Stopping ChainWatch Network System..."
echo ""

kill_group() {
  local name="$1" pid="$2"
  if [ -z "$pid" ]; then
    return
  fi
  if kill -0 "$pid" 2>/dev/null; then
    echo "  Stopping $name (PID $pid)..."
    kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null
    sleep 1
    if kill -0 "$pid" 2>/dev/null; then
      echo "    still alive, sending SIGKILL"
      kill -KILL -- "-$pid" 2>/dev/null || kill -KILL "$pid" 2>/dev/null
    fi
  else
    echo "  $name (PID $pid) already stopped"
  fi
}

if [ -f "$PID_FILE" ]; then
  while IFS=: read -r name pid; do
    [ -z "${name:-}" ] && continue
    kill_group "$name" "$pid"
  done < "$PID_FILE"
  rm -f "$PID_FILE"
else
  echo "  No PID file found ($PID_FILE) — skipping PID-based stop."
fi

echo ""
echo "Sweeping for any leftover matching processes..."

pkill -f "uvicorn main:app" 2>/dev/null && echo "  Killed leftover uvicorn process(es)"
pkill -f "streamlit run generator_app.py" 2>/dev/null && echo "  Killed leftover streamlit process(es)"
pkill -f "vite" 2>/dev/null && echo "  Killed leftover vite process(es)"

echo ""
echo "ChainWatch shutdown complete."