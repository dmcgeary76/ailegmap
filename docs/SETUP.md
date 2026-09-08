> **Out of date (2026-09-02):** this document describes the PostgreSQL / `state_legislation` design. The current setup, data model and endpoints are in the top-level [README](../README.md) and `CHANGELOG.md`; the live API reference is at http://localhost:8000/docs.

# Local Development Setup

## Prerequisites

You need one of the following setups:

### Option A: Docker & Docker Compose (Recommended)
- Docker Desktop (includes Docker & Docker Compose)
- Download: https://www.docker.com/products/docker-desktop

### Option B: Manual Setup
- Python 3.11+
- Node.js 18+
- PostgreSQL 14+

## Quick Start (Docker)

1. **Navigate to project directory:**
   ```bash
   cd ~/Claude/Projects/AI\ Legislative\ Map
   ```

2. **Start all services:**
   ```bash
   docker-compose up -d
   ```

3. **Access the app:**
   - Frontend: http://localhost:5173
   - Backend API: http://localhost:8000
   - API Docs: http://localhost:8000/docs

4. **View logs:**
   ```bash
   docker-compose logs -f
   ```

5. **Stop services:**
   ```bash
   docker-compose down
   ```

## Manual Setup (Without Docker)

### Backend Setup

1. **Create virtual environment:**
   ```bash
   cd backend
   python3.11 -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your database credentials
   ```

4. **Start PostgreSQL:**
   ```bash
   # macOS with Homebrew
   brew services start postgresql

   # Or Docker
   docker run --name k12_db -e POSTGRES_PASSWORD=password -d -p 5432:5432 postgres:15
   ```

5. **Run migrations (if needed):**
   ```bash
   alembic upgrade head
   ```

6. **Start development server:**
   ```bash
   python -m uvicorn app.main:app --reload
   ```

Backend will be available at http://localhost:8000

### Frontend Setup

1. **Navigate to frontend directory:**
   ```bash
   cd frontend
   ```

2. **Install dependencies:**
   ```bash
   npm install
   ```

3. **Start development server:**
   ```bash
   npm run dev
   ```

Frontend will be available at http://localhost:5173

## Database Setup

### With Docker Compose
Database is automatically created and running.

Access PostgreSQL:
```bash
docker exec -it k12_ai_db psql -U k12_user -d k12_ai_db
```

### Manual PostgreSQL Setup

1. **Create database:**
   ```bash
   createdb k12_ai_db
   ```

2. **Create user:**
   ```bash
   createuser k12_user -P
   # Enter password: k12_password
   ```

3. **Grant privileges:**
   ```bash
   psql -d k12_ai_db -c "ALTER USER k12_user CREATEDB;"
   ```

4. **Connect and verify:**
   ```bash
   psql -d k12_ai_db -U k12_user
   ```

## Loading Sample Data

Once the backend is running:

1. **Create sample records via API:**
   ```bash
   curl -X POST http://localhost:8000/api/states \
     -H "Content-Type: application/json" \
     -d '{
       "state_code": "CA",
       "state_name": "California",
       "bill_number": "AB 1159",
       "bill_title": "Student Data Protection Act",
       "bill_status": "In Committee",
       "guidance_exists": true,
       "regulatory_stance": "PROHIBIT",
       "maturity": "ACTIVE"
     }'
   ```

2. **Or load a batch script (when available):**
   ```bash
   python backend/scripts/seed_data.py
   ```

## Environment Variables

**Backend (.env):**
```
DATABASE_URL=postgresql://k12_user:k12_password@localhost:5432/k12_ai_db
ENVIRONMENT=development
DEBUG=True
```

**Frontend (.env):**
```
VITE_API_URL=http://localhost:8000
```

## Testing the Setup

1. **Backend health check:**
   ```bash
   curl http://localhost:8000/api/health
   ```

   Should return:
   ```json
   {"status": "ok"}
   ```

2. **Get all states:**
   ```bash
   curl http://localhost:8000/api/states
   ```

3. **View API docs:**
   Visit http://localhost:8000/docs in your browser

4. **Frontend loads:**
   Visit http://localhost:5173 in your browser

## Troubleshooting

### Port already in use
```bash
# Kill process on port (macOS/Linux)
lsof -ti:5173 | xargs kill -9
lsof -ti:8000 | xargs kill -9

# Windows
netstat -ano | findstr :5173
taskkill /PID <PID> /F
```

### Database connection error
- Verify PostgreSQL is running: `psql --version`
- Check DATABASE_URL in .env
- Verify credentials match

### Docker issues
```bash
# Remove all containers and volumes
docker-compose down -v

# Rebuild images
docker-compose build --no-cache

# Start fresh
docker-compose up
```

### Frontend not connecting to backend
- Verify backend is running on port 8000
- Check VITE_API_URL in frontend .env
- Check browser console for CORS errors
- Backend CORS is set to allow all origins in development

## Next Steps

1. Load sample data (see "Loading Sample Data" above)
2. Click on states in the frontend to view details
3. Use filters to explore by stance/maturity
4. Read `DATA_SCHEMA.md` to understand data structure
5. Read `API_SPEC.md` for API details

## File Structure

```
.
├── docker-compose.yml    # Docker setup
├── .env.example          # Environment template
├── README.md             # Project overview
├── backend/
│   ├── app/
│   │   ├── main.py       # FastAPI app
│   │   ├── database.py   # DB config
│   │   ├── models/       # SQLAlchemy models
│   │   ├── schemas/      # Pydantic schemas
│   │   └── api/          # Route handlers
│   ├── Dockerfile
│   ├── requirements.txt
│   └── README.md
├── frontend/
│   ├── src/
│   │   ├── main.jsx      # Entry point
│   │   ├── App.jsx       # Main component
│   │   └── components/   # React components
│   ├── Dockerfile
│   ├── package.json
│   ├── vite.config.js
│   └── README.md
└── docs/
    ├── DATA_SCHEMA.md    # Database schema
    ├── API_SPEC.md       # API endpoints
    └── SETUP.md          # This file
```

## Documentation

- **DATA_SCHEMA.md**: Complete database field definitions and examples
- **API_SPEC.md**: All API endpoints and request/response formats
- **backend/README.md**: Backend-specific notes
- **frontend/README.md**: Frontend-specific notes

## Getting Help

1. Check logs: `docker-compose logs -f service_name`
2. Review API docs: http://localhost:8000/docs
3. Check browser console for frontend errors
4. Verify environment variables are set correctly
