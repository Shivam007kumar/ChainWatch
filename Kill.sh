#!/bin/bash
#
# kill.sh — stops all ChainWatch services started by start.sh.
#
# Primary strategy: kill the whole process GROUP for each PID recorded by
# start.sh (start.sh used `set -m`, so each job is its own group leader).
# This takes down uvicorn's reload subprocess and npm/vite's child node
# process too, not just the top-level shell.
#
# Fallback strategy: pattern-match on the known commands, in case the PID
# file is missing/stale or something escaped its process group.

set -uo pipefail

PROJECT_ROOT="/Users/shivamkumar/laptop/chainwatch"
PID_FILE="$PROJECT_ROOT/.chainwatch_pids"

echo "Stopping ChainWatch..."
echo ""

kill_group() {
  local name="$1" pid="$2"
  if [ -z "$pid" ]; then
    return
  fi
  if kill -0 "$pid" 2>/dev/null; then
    echo "  Stopping $name (PID $pid)..."
    # negative PID = kill the whole process group
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

# Fallback pattern-based cleanup, in case anything escaped its group
pkill -f "uvicorn main:app" 2>/dev/null && echo "  Killed leftover uvicorn process(es)"
pkill -f "streamlit run generator_app.py" 2>/dev/null && echo "  Killed leftover streamlit process(es)"
pkill -f "vite" 2>/dev/null && echo "  Killed leftover vite process(es)"

echo ""
echo "Done."