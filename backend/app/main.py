from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.api import routes, bill_review

init_db()

app = FastAPI(
    title="K-12 AI Legislative Map API",
    description="K-12 AI legislation and state guidance across U.S. jurisdictions",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes.router)
app.include_router(bill_review.router)


@app.get("/")
def root():
    return {"name": "K-12 AI Legislative Map API", "version": "0.2.0", "docs_url": "/docs"}
