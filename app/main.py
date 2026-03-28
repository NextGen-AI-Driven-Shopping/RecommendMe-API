from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.api.v1.router import router as v1_router
from app.core.exceptions import register_exception_handlers
from app.core.logger import get_logger
from app.core.middleware import register_middleware
from app.core.security import configure_cors
from app.api.v1 import auth

logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up RecommendMe API...")
    if not hasattr(app.state, "session_store"):
        app.state.session_store = {}
    yield
    logger.info("Shutting down RecommendMe API...")

app = FastAPI(
    title="RecommendMe API",
    description="AI-powered product recommendation engine.",
    version="1.0.0",
    lifespan=lifespan,
)

configure_cors(app)
register_middleware(app)
register_exception_handlers(app)

app.include_router(v1_router, prefix="/v1")
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])

@app.get("/", include_in_schema=False)
async def root():
    return JSONResponse(
        status_code=200,
        content={
            "message": "Welcome to RecommendMe API",
            "status": "✅ Server is running",
            "version": "1.0.0",
        },
    )

@app.get("/health", include_in_schema=False)
async def liveness():
    return JSONResponse(status_code=200, content={"status": "ok"})