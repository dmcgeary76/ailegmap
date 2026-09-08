#!/bin/bash
# Start the backend (port 8000) and the frontend (port 5173). No database
# server needed -- the backend uses backend/k12_ai.db (SQLite).
cd "$(dirname "$0")"

if [ ! -d backend/venv ]; then
  echo "No backend/venv yet -- run ./setup.sh first"; exit 1
fi

(cd backend && source venv/bin/activate && python -m uvicorn app.main:app --reload) &
BACKEND_PID=$!
sleep 2
(cd frontend && npm run dev) &
FRONTEND_PID=$!

echo ""
echo "  Frontend: http://localhost:5173"
echo "  API:      http://localhost:8000   (docs at /docs)"
echo ""
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT
wait
