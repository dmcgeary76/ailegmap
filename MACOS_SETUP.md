# macOS Local Development Setup (No Docker)

Run the K-12 AI Legislative Map directly on your MacBook without Docker.

## Prerequisites

You'll need Homebrew. If you don't have it:
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

## Step 1: Install Dependencies

### Python
```bash
brew install python@3.11
```

### Node.js
```bash
brew install node@18
```

### PostgreSQL
```bash
brew install postgresql@15
```

### Verify Installations
```bash
python3.11 --version
node --version
npm --version
psql --version
```

## Step 2: Set Up PostgreSQL

### Start PostgreSQL service
```bash
brew services start postgresql@15
```

### Create database and user
```bash
# Login to PostgreSQL
psql postgres

# Inside psql, run these commands:
CREATE USER k12_user WITH PASSWORD 'k12_password';
CREATE DATABASE k12_ai_db OWNER k12_user;
GRANT ALL PRIVILEGES ON DATABASE k12_ai_db TO k12_user;
\q
```

### Verify it worked
```bash
psql -U k12_user -d k12_ai_db
# Should connect without error. Type \q to exit.
```

## Step 3: Set Up Backend

```bash
cd ~/Claude/Projects/AI\ Legislative\ Map/backend

# Create virtual environment
python3.11 -m venv venv

# Activate it
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env

# Verify .env has correct database URL
# It should be: postgresql://k12_user:k12_password@localhost:5432/k12_ai_db
cat .env
```

### Start Backend
```bash
# Make sure venv is activated (you should see (venv) in your prompt)
source venv/bin/activate

# Run the server
python -m uvicorn app.main:app --reload
```

Backend will start at **http://localhost:8000**

You should see:
```
Uvicorn running on http://127.0.0.1:8000
Press CTRL+C to quit
```

## Step 4: Set Up Frontend

Open a **new terminal tab** (keep backend running in first tab):

```bash
cd ~/Claude/Projects/AI\ Legislative\ Map/frontend

# Install dependencies (one-time only)
npm install

# Start dev server
npm run dev
```

Frontend will start at **http://localhost:5173**

You should see:
```
VITE v5.0.8  ready in 123 ms

➜  Local:   http://localhost:5173/
```

## Step 5: Access the App

Open your browser:
- **App**: http://localhost:5173
- **API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/api/health

## Daily Workflow

### Start everything in the morning

**Terminal 1 - Backend:**
```bash
cd ~/Claude/Projects/AI\ Legislative\ Map/backend
source venv/bin/activate
python -m uvicorn app.main:app --reload
```

**Terminal 2 - Frontend:**
```bash
cd ~/Claude/Projects/AI\ Legislative\ Map/frontend
npm run dev
```

**Terminal 3 - PostgreSQL (if not running):**
```bash
brew services start postgresql@15
```

### Stop everything
```bash
# Terminal 1 & 2: Ctrl+C
# PostgreSQL (optional):
brew services stop postgresql@15
```

## Loading Sample Data

Once backend is running, create a state record:

```bash
curl -X POST http://localhost:8000/api/states \
  -H "Content-Type: application/json" \
  -d '{
    "state_code": "CA",
    "state_name": "California",
    "bill_number": "AB 1159",
    "bill_title": "Student Data Protection Act",
    "bill_status": "In Committee",
    "bill_status_details": "Senate Education Committee as of May 20, 2026",
    "guidance_exists": true,
    "guidance_type": "ADVISORY",
    "guidance_issued_by": "California Department of Education",
    "guidance_core_principles": ["data_privacy", "equity", "academic_integrity"],
    "regulatory_stance": "PROHIBIT",
    "maturity": "ACTIVE",
    "key_focus_areas": ["data_privacy", "student_protection"],
    "sources": ["https://cde.ca.gov"]
  }'
```

Or use this bash script to load all pilot states:

Create `~/Claude/Projects/AI\ Legislative\ Map/load_pilot_data.sh`:

```bash
#!/bin/bash

API_URL="http://localhost:8000/api/states"

# California
curl -X POST $API_URL -H "Content-Type: application/json" -d '{
  "state_code": "CA", "state_name": "California",
  "bill_number": "AB 1159", "bill_title": "Student Data Protection Act",
  "bill_status": "In Committee", "guidance_exists": true,
  "guidance_type": "ADVISORY", "guidance_issued_by": "California Department of Education",
  "guidance_core_principles": ["data_privacy", "equity"],
  "regulatory_stance": "PROHIBIT", "maturity": "ACTIVE"
}'

# Texas
curl -X POST $API_URL -H "Content-Type: application/json" -d '{
  "state_code": "TX", "state_name": "Texas",
  "bill_status": "Absent", "guidance_exists": false,
  "regulatory_stance": "ABSENT", "maturity": "NASCENT",
  "districts_have_policies": true,
  "example_district_actions": ["El Paso ISD creating custom policies"],
  "tools_in_use": ["PowerBuddy", "MagicSchool AI"]
}'

# Massachusetts
curl -X POST $API_URL -H "Content-Type: application/json" -d '{
  "state_code": "MA", "state_name": "Massachusetts",
  "bill_number": "S.429", "bill_title": "Commission to Investigate AI in Education",
  "bill_status": "Proposed", "guidance_exists": true,
  "guidance_type": "ADVISORY", "guidance_issued_by": "Massachusetts DESE",
  "guidance_core_principles": ["data_privacy", "transparency", "bias_mitigation", "human_oversight"],
  "regulatory_stance": "SUPPORT", "maturity": "IN_PROGRESS"
}'

# Rhode Island
curl -X POST $API_URL -H "Content-Type: application/json" -d '{
  "state_code": "RI", "state_name": "Rhode Island",
  "bill_status": "Absent", "guidance_exists": true,
  "guidance_type": "ADVISORY", "guidance_issued_by": "Rhode Island Department of Education",
  "guidance_issued_date": "2025-08-15",
  "guidance_core_principles": ["academic_integrity", "equity", "security_privacy"],
  "regulatory_stance": "SUPPORT", "maturity": "IN_PROGRESS",
  "adoption_metrics": {"student_usage_pct": 20, "educator_usage_pct": 6}
}'

# Alaska
curl -X POST $API_URL -H "Content-Type: application/json" -d '{
  "state_code": "AK", "state_name": "Alaska",
  "bill_status": "Absent", "guidance_exists": true,
  "guidance_type": "ADVISORY", "guidance_issued_by": "Alaska Department of Education",
  "guidance_issued_date": "2025-10-01",
  "guidance_core_principles": ["human_centered_design", "fair_access", "transparency", "cultural_responsiveness"],
  "regulatory_stance": "SUPPORT", "maturity": "IN_PROGRESS",
  "unique_context": "Remote/rural state with strong emphasis on cultural responsiveness"
}'

# Hawaii
curl -X POST $API_URL -H "Content-Type: application/json" -d '{
  "state_code": "HI", "state_name": "Hawaii",
  "bill_number": "HB 1887", "bill_title": "AI Literacy Graduation Requirement",
  "bill_status": "Passed", "guidance_exists": true,
  "guidance_type": "ADVISORY", "guidance_issued_by": "Hawaii Department of Education",
  "guidance_core_principles": ["human_oversight", "data_protection", "equity"],
  "regulatory_stance": "MANDATE", "maturity": "MATURE",
  "graduation_requirement": true, "graduation_year": 2028,
  "teacher_certification_required": true,
  "unique_context": "Island state with integrated cultural curriculum"
}'

echo "✅ Pilot states loaded!"
```

Run it:
```bash
chmod +x ~/Claude/Projects/AI\ Legislative\ Map/load_pilot_data.sh
~/Claude/Projects/AI\ Legislative\ Map/load_pilot_data.sh
```

## Database Management

### View all states
```bash
psql -U k12_user -d k12_ai_db -c "SELECT state_code, state_name, regulatory_stance, maturity FROM state_legislation ORDER BY state_code;"
```

### Get stats
```bash
psql -U k12_user -d k12_ai_db -c "SELECT regulatory_stance, COUNT(*) FROM state_legislation GROUP BY regulatory_stance;"
```

### Clear all data (careful!)
```bash
psql -U k12_user -d k12_ai_db -c "DELETE FROM state_legislation CASCADE;"
```

### Access interactive terminal
```bash
psql -U k12_user -d k12_ai_db
```

## Troubleshooting

### PostgreSQL won't start
```bash
# Check if it's already running
brew services list

# Stop and restart
brew services stop postgresql@15
brew services start postgresql@15

# Or see what's wrong
postgres -D /usr/local/var/postgres
```

### Port already in use
```bash
# Kill process on port 8000 (backend)
lsof -ti:8000 | xargs kill -9

# Kill process on port 5173 (frontend)
lsof -ti:5173 | xargs kill -9
```

### Database connection error in backend
```bash
# Verify you can connect to PostgreSQL
psql -U k12_user -d k12_ai_db

# Check .env file has correct DATABASE_URL
cat ~/Claude/Projects/AI\ Legislative\ Map/backend/.env

# Should be: postgresql://k12_user:k12_password@localhost:5432/k12_ai_db
```

### Frontend can't connect to backend
- Make sure backend is running (http://localhost:8000 should work in browser)
- Check browser console for CORS errors
- Try hard refresh (Cmd+Shift+R)

### pip install fails
```bash
# Make sure you're in the venv
source venv/bin/activate

# Try upgrading pip
pip install --upgrade pip

# Try again
pip install -r requirements.txt
```

## Editor Setup (Optional)

### VS Code
```bash
# Open project
code ~/Claude/Projects/AI\ Legislative\ Map
```

Useful extensions:
- Python (Microsoft)
- Pylance
- ES7+ React/Redux/React-Native snippets
- Prettier

### Run both servers in VS Code
1. Terminal > New Terminal (Ctrl+`)
2. Split terminal (Cmd+\)
3. Left: Backend. Right: Frontend

## Tips

- **Keep terminal windows organized**: One for each service (backend, frontend)
- **Hot reload**: Both dev servers auto-reload on file changes
- **Database**: Run `psql` in a fourth terminal if you need to query
- **Logs**: Backend logs appear in terminal, frontend logs in browser console
- **API Testing**: Use http://localhost:8000/docs for interactive API testing

## Next Steps

1. Run the startup commands above
2. Load pilot data with the script
3. Click on states in the app to see details
4. Edit files and watch them hot-reload
5. Build out features locally (SVG map, timeline, etc.)

That's it—no Docker needed!
