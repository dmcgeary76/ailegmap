> **Out of date (2026-09-02):** this document describes the PostgreSQL / `state_legislation` design. The current setup, data model and endpoints are in the top-level [README](../README.md) and `CHANGELOG.md`; the live API reference is at http://localhost:8000/docs.

# Backend API

FastAPI application for K-12 AI Legislative Map.

## Setup

### With Docker
```bash
docker-compose up backend
```

### Manual Setup
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Set DATABASE_URL environment variable
export DATABASE_URL=postgresql://user:password@localhost:5432/k12_ai_db

# Run migrations (when needed)
alembic upgrade head

# Start dev server
python -m uvicorn app.main:app --reload
```

API will be available at http://localhost:8000

## Endpoints

### Get States
- `GET /api/states` - List all states
- `GET /api/states?stance=SUPPORT&maturity=ACTIVE` - Filter by stance/maturity
- `GET /api/states/{state_code}` - Get specific state

### Create State Record
- `POST /api/states` - Create new state legislation record

### Update State Record
- `PUT /api/states/{state_code}` - Update state record

### Dashboard
- `GET /api/dashboard/summary` - Get summary statistics

### Health
- `GET /api/health` - Health check

## Database

PostgreSQL database with tables:
- `state_legislation` - State records
- `legislation_updates` - Audit trail

See `docs/DATA_SCHEMA.md` for field definitions.

## Environment Variables

```
DATABASE_URL=postgresql://user:password@host:port/dbname
ENVIRONMENT=development
DEBUG=True
```
