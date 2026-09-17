#!/bin/bash
#
# Start.sh — launches all 3 ChainWatch services in parallel:
#   1. FastAPI backend   (uvicorn main:app --reload)
#   2. Streamlit generator (generator_app.py)
#   3. Frontend dev server (npm run dev)
#
# Logs go to ./logs/*.log, PIDs go to .chainwatch_pids

set -euo pipefail
set -m   # enable job control so each background job gets its own process group

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$PROJECT_ROOT/chainwatch_backend"
FRONTEND_DIR="$PROJECT_ROOT/chainwatch_frontend"
LOG_DIR="$PROJECT_ROOT/logs"
PID_FILE="$PROJECT_ROOT/.chainwatch_pids"

mkdir -p "$LOG_DIR"
: > "$PID_FILE"

echo "Starting ChainWatch Network System..."
echo ""

# ---- T1: FastAPI backend ----
cd "$BACKEND_DIR"
(source venv/bin/activate && uvicorn main:app --reload) \
  > "$LOG_DIR/backend.log" 2>&1 &
BACKEND_PID=$!
echo "backend:$BACKEND_PID" >> "$PID_FILE"
echo "  [1/3] FastAPI backend   -> PID $BACKEND_PID   (log: logs/backend.log)"

# ---- T2: Streamlit generator ----
cd "$BACKEND_DIR"
(source venv/bin/activate && streamlit run generator_app.py) \
  > "$LOG_DIR/generator.log" 2>&1 &
GENERATOR_PID=$!
echo "generator:$GENERATOR_PID" >> "$PID_FILE"
echo "  [2/3] Streamlit generator -> PID $GENERATOR_PID   (log: logs/generator.log)"

# ---- T3: Frontend dev server ----
cd "$FRONTEND_DIR"
npm run dev > "$LOG_DIR/frontend.log" 2>&1 &
FRONTEND_PID=$!
echo "frontend:$FRONTEND_PID" >> "$PID_FILE"
echo "  [3/3] Frontend (npm run dev) -> PID $FRONTEND_PID   (log: logs/frontend.log)"

echo ""
echo "All 3 ChainWatch services launched successfully."
echo "  Tail all logs:   tail -f logs/*.log"
echo "  Stop everything: ./Kill.sh"