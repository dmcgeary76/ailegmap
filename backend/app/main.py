from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base
from app.api import routes, review_queue, bill_review
from app.models.legislation import StateLegislation, LegislationUpdate, BillReviewItem

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="K-12 AI Legislative Map API",
    description="API for tracking K-12 AI legislation and policies across U.S. states",
    version="0.1.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development; restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(routes.router)
app.include_router(review_queue.router)
app.include_router(bill_review.router)


@app.get("/")
def root():
    """Root endpoint."""
    return {
        "name": "K-12 AI Legislative Map API",
        "version": "0.1.0",
        "docs_url": "/docs",
    }
