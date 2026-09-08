import os
import sys

os.environ.setdefault("DATABASE_URL", "sqlite://")  # in-memory unless overridden
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base


@pytest.fixture
def engine():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    from app import models  # noqa: F401
    Base.metadata.create_all(bind=eng)
    return eng


@pytest.fixture
def db(engine):
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()


@pytest.fixture
def client(engine):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.database import get_db
    Session = sessionmaker(bind=engine)

    def _override():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


RAW_CA = [
    {"bill_id": 101, "bill_number": "SB1288", "title": "Public schools: artificial intelligence working group.",
     "relevance": 41, "status": 4, "url": "u", "last_action_date": "2024-09-01", "change_hash": "h101"},
    {"bill_id": 102, "bill_number": "AB1064", "title": "Leading Ethical AI Development (LEAD) for Kids Act.",
     "relevance": 51, "status": 5, "url": "u", "last_action_date": "2024-09-30", "change_hash": "h102"},
    {"bill_id": 103, "bill_number": "AB1979", "title": "Health care services: artificial intelligence.",
     "relevance": 49, "status": 1, "url": "u", "last_action_date": "2024-02-01", "change_hash": "h103"},
    {"bill_id": 104, "bill_number": "SB1381", "title": "Crimes: child pornography.",
     "relevance": 29, "status": 4, "url": "u", "last_action_date": "2024-08-01", "change_hash": "h104"},
]


@pytest.fixture
def raw_ca():
    return [dict(b) for b in RAW_CA]
