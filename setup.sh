#!/bin/bash

set -e

echo "🚀 K-12 AI Legislative Map - Local Setup"
echo "========================================"
echo ""

# Check if running on macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo "⚠️  This script is optimized for macOS. You may need to adjust commands for your OS."
fi

# Check if Homebrew is installed
if ! command -v brew &> /dev/null; then
    echo "❌ Homebrew not found. Install it first:"
    echo "   /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
    exit 1
fi

echo "✅ Homebrew found"

# Install Python 3.11
if ! brew list python@3.11 &> /dev/null; then
    echo "📦 Installing Python 3.11..."
    brew install python@3.11
else
    echo "✅ Python 3.11 already installed"
fi

# Install Node.js
if ! brew list node@18 &> /dev/null; then
    echo "📦 Installing Node.js 18..."
    brew install node@18
else
    echo "✅ Node.js 18 already installed"
fi

# Install PostgreSQL
if ! brew list postgresql@15 &> /dev/null; then
    echo "📦 Installing PostgreSQL 15..."
    brew install postgresql@15
else
    echo "✅ PostgreSQL 15 already installed"
fi

# Start PostgreSQL
echo "🗄️  Starting PostgreSQL..."
brew services start postgresql@15
sleep 2

# Create database and user
echo "🔨 Setting up database..."
if ! psql postgres -tc "SELECT 1 FROM pg_database WHERE datname = 'k12_ai_db'" | grep -q 1; then
    psql -U $(whoami) postgres << EOF
CREATE USER k12_user WITH PASSWORD 'k12_password';
CREATE DATABASE k12_ai_db OWNER k12_user;
GRANT ALL PRIVILEGES ON DATABASE k12_ai_db TO k12_user;
EOF
    echo "✅ Database and user created"
else
    echo "✅ Database already exists"
fi

# Setup backend
echo ""
echo "⚙️  Setting up backend..."
cd backend

if [ ! -d "venv" ]; then
    echo "📦 Creating Python virtual environment..."
    python3.11 -m venv venv
fi

echo "🐍 Activating virtual environment..."
source venv/bin/activate

echo "📦 Installing Python dependencies..."
pip install --upgrade pip > /dev/null 2>&1
pip install -r requirements.txt > /dev/null 2>&1

# Create .env if it doesn't exist
if [ ! -f ".env" ]; then
    echo "📝 Creating .env file..."
    cp .env.example .env
fi

echo "✅ Backend setup complete"
cd ..

# Setup frontend
echo ""
echo "⚙️  Setting up frontend..."
cd frontend

if [ ! -d "node_modules" ]; then
    echo "📦 Installing Node.js dependencies..."
    npm install > /dev/null 2>&1
else
    echo "✅ Node.js dependencies already installed"
fi

echo "✅ Frontend setup complete"
cd ..

# Create startup script
echo ""
echo "📝 Creating startup script..."
cat > start.sh << 'EOF'
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
EOF

chmod +x start.sh

# Create load data script
echo "📝 Creating data loading script..."
cat > load_data.sh << 'EOF'
#!/bin/bash

API_URL="http://localhost:8000/api/states"

echo "📊 Loading pilot state data..."

# California
curl -s -X POST $API_URL -H "Content-Type: application/json" -d '{
  "state_code": "CA", "state_name": "California",
  "bill_number": "AB 1159", "bill_title": "Student Data Protection Act",
  "bill_status": "In Committee", "bill_status_details": "Senate Education Committee as of May 20, 2026",
  "guidance_exists": true, "guidance_type": "ADVISORY",
  "guidance_issued_by": "California Department of Education",
  "guidance_core_principles": ["data_privacy", "equity", "academic_integrity"],
  "regulatory_stance": "PROHIBIT", "maturity": "ACTIVE",
  "key_focus_areas": ["data_privacy", "student_protection"]
}' > /dev/null && echo "✅ California"

# Texas
curl -s -X POST $API_URL -H "Content-Type: application/json" -d '{
  "state_code": "TX", "state_name": "Texas",
  "bill_status": "Absent", "guidance_exists": false,
  "regulatory_stance": "ABSENT", "maturity": "NASCENT",
  "districts_have_policies": true,
  "example_district_actions": ["El Paso ISD creating custom policies"],
  "tools_in_use": ["PowerBuddy", "MagicSchool AI"]
}' > /dev/null && echo "✅ Texas"

# Massachusetts
curl -s -X POST $API_URL -H "Content-Type: application/json" -d '{
  "state_code": "MA", "state_name": "Massachusetts",
  "bill_number": "S.429", "bill_title": "Commission to Investigate AI in Education",
  "bill_status": "Proposed", "guidance_exists": true,
  "guidance_type": "ADVISORY", "guidance_issued_by": "Massachusetts DESE",
  "guidance_issued_date": "2025-08-01",
  "guidance_core_principles": ["data_privacy", "transparency", "bias_mitigation", "human_oversight", "academic_integrity"],
  "regulatory_stance": "SUPPORT", "maturity": "IN_PROGRESS"
}' > /dev/null && echo "✅ Massachusetts"

# Rhode Island
curl -s -X POST $API_URL -H "Content-Type: application/json" -d '{
  "state_code": "RI", "state_name": "Rhode Island",
  "bill_status": "Absent", "guidance_exists": true,
  "guidance_type": "ADVISORY", "guidance_issued_by": "Rhode Island Department of Education",
  "guidance_issued_date": "2025-08-15",
  "guidance_core_principles": ["academic_integrity", "equity", "security_privacy"],
  "regulatory_stance": "SUPPORT", "maturity": "IN_PROGRESS",
  "adoption_metrics": "{\"student_usage_pct\": 20, \"educator_usage_pct\": 6}"
}' > /dev/null && echo "✅ Rhode Island"

# Alaska
curl -s -X POST $API_URL -H "Content-Type: application/json" -d '{
  "state_code": "AK", "state_name": "Alaska",
  "bill_status": "Absent", "guidance_exists": true,
  "guidance_type": "ADVISORY", "guidance_issued_by": "Alaska Department of Education",
  "guidance_issued_date": "2025-10-01",
  "guidance_core_principles": ["human_centered_design", "fair_access", "transparency", "oversight", "security", "ethical_use", "cultural_responsiveness"],
  "regulatory_stance": "SUPPORT", "maturity": "IN_PROGRESS",
  "unique_context": "Remote/rural state with strong emphasis on cultural responsiveness and including elders/local educators in policy"
}' > /dev/null && echo "✅ Alaska"

# Hawaii
curl -s -X POST $API_URL -H "Content-Type: application/json" -d '{
  "state_code": "HI", "state_name": "Hawaii",
  "bill_number": "HB 1887", "bill_title": "AI Literacy Graduation Requirement",
  "bill_status": "Passed", "guidance_exists": true,
  "guidance_type": "ADVISORY", "guidance_issued_by": "Hawaii Department of Education",
  "guidance_core_principles": ["human_oversight", "data_protection", "equity", "accountability"],
  "regulatory_stance": "MANDATE", "maturity": "MATURE",
  "graduation_requirement": true, "graduation_year": 2028,
  "teacher_certification_required": true,
  "pilot_programs": "[{\"duration\": \"3 years\", \"funding\": 5000000, \"focus\": \"Teacher training and curriculum development\"}]",
  "unique_context": "Island state with integrated cultural curriculum - how AI relates to Hawaii history and culture"
}' > /dev/null && echo "✅ Hawaii"

echo ""
echo "✅ All pilot states loaded!"
echo ""
echo "🎉 Visit http://localhost:5173 to see the data"
EOF

chmod +x load_data.sh

echo "✅ Scripts created"

echo ""
echo "=========================================="
echo "✅ Setup Complete!"
echo "=========================================="
echo ""
echo "To start developing:"
echo ""
echo "  ./start.sh"
echo ""
echo "Then in another terminal, once both services are running:"
echo ""
echo "  ./load_data.sh"
echo ""
echo "Then visit:"
echo "  🌐 http://localhost:5173"
echo ""
