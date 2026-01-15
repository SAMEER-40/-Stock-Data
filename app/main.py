"""
Stock Data Intelligence Platform - FastAPI Application

Production-grade REST API for Indian equity analysis.
Demonstrates:
- Clean architecture with separation of concerns
- Pre-computed analytics (avoiding real-time computation overhead)
- Proper error handling with meaningful responses
- Comprehensive Swagger documentation
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import API_TITLE, API_DESCRIPTION, API_VERSION
from app.api.routes import router
from app.db.database import init_db

# Initialize FastAPI application
app = FastAPI(
    title=API_TITLE,
    description=API_DESCRIPTION,
    version=API_VERSION,
    docs_url="/docs",      # Swagger UI
    redoc_url="/redoc",    # ReDoc alternative
    openapi_url="/openapi.json",
)

# CORS middleware for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix="/api/v1", tags=["Stock Data"])

# Serve static files
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

# Mount static directory
static_path = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_path), name="static")

@app.get("/", tags=["UI"], include_in_schema=False)
@app.head("/", tags=["UI"], include_in_schema=False)
async def read_root():
    """Serve the dashboard UI."""
    return FileResponse(static_path / "index.html")


# Run with: uvicorn app.main:app --reload --port 8000
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
