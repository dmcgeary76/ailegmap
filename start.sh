#!/bin/bash

echo "🚀 Starting K-12 AI Legislative Map"
echo "===================================="
echo ""

# Check PostgreSQL
if ! brew services list | grep postgresql@15 | grep -q "started"; then
    echo "🗄️  Starting PostgreSQL..."
    brew services start postgresql@15
    sleep 2
fi

echo ""
echo "📋 Backend will start in Terminal 1"
echo "📋 Frontend will start in Terminal 2"
echo ""
echo "Once both are running:"
echo "  🌐 Frontend: http://localhost:5173"
echo "  ⚙️  Backend: http://localhost:8000"
echo "  📚 API Docs: http://localhost:8000/docs"
echo ""

# Function to start backend
start_backend() {
    cd "$(dirname "$0")/backend"
    source venv/bin/activate
    echo "🚀 Backend starting on http://localhost:8000"
    python -m uvicorn app.main:app --reload
}

# Function to start frontend
start_frontend() {
    cd "$(dirname "$0")/frontend"
    echo "🚀 Frontend starting on http://localhost:5173"
    npm run dev
}

# Start both in separate processes
start_backend &
BACKEND_PID=$!

sleep 3

start_frontend &
FRONTEND_PID=$!

# Handle cleanup
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT

wait
