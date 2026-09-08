#!/bin/bash
# One-time local setup: Python venv, Node deps, SQLite schema, seed profiles.
set -e
cd "$(dirname "$0")"

command -v python3 >/dev/null || { echo "python3 not found (3.10+ required)"; exit 1; }
command -v npm >/dev/null || { echo "npm not found (Node 18+ required)"; exit 1; }

echo "Backend..."
cd backend
[ -d venv ] || python3 -m venv venv
source venv/bin/activate
pip install -q -r requirements.txt
[ -f .env ] || { cp .env.example .env; echo "  Created backend/.env -- add your LEGISCAN_API_KEY"; }
python -c "from app.database import init_db; init_db()"
python -m app.seed
cd ..

echo "Frontend..."
cd frontend && npm install --no-audit --no-fund && cd ..

echo ""
echo "Done. Next:"
echo "  ./start.sh                                       # run the app"
echo "  cd backend && python -m app.sync.legiscan_sync --state CA   # pull bills"
