# Backend

FastAPI + SQLAlchemy on a single SQLite file (`k12_ai.db`). The top-level [README](../README.md) is the
full guide; this is the short version.

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                 # add LEGISCAN_API_KEY
python -m app.seed                   # profiles, local actions, review decisions -> DB
uvicorn app.main:app --reload        # http://localhost:8000  (Swagger at /docs)
pytest                               # ~2 s, in-memory SQLite, no API key
```

| Module | Does |
|---|---|
| `app/models/legislation.py` | `state_profiles`, `bills`, `local_actions`, `sync_runs`, `bill_status_changes`; `is_resolution()`; `AUTO_INCLUDE_CONFIDENCE` |
| `app/derive.py` | read-time derivations: legislation stage, headline bill, review counts, local signal |
| `app/api/routes.py`, `app/api/bill_review.py` | the map's read model; the review queue |
| `app/sync/legiscan_sync.py` | LegiScan search + status sync, title scorer, `--rescore`, `--query`, carry-over linking |
| `app/sync/text_scorer.py` | `--score-text`: reads bill text, counts AI-term density, folds into confidence |
| `app/seed.py` / `app/export.py` | JSON + CSV in `data/` -> DB; DB -> `docs/data.json` for the static map |
| `app/decisions.py` | `data/decisions.csv` is the source of truth for include/exclude calls |

Everything a person curates lives in `data/` and is tracked in git; the `.db` is a cache you can delete
and rebuild with a sync + `python -m app.seed`.

Environment (`.env`): `LEGISCAN_API_KEY` (required for syncing), optional `DATABASE_URL` (any SQLAlchemy
URL; defaults to the SQLite file next to this README).
