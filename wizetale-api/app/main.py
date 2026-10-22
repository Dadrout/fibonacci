from contextlib import asynccontextmanager
import logging
import redis.asyncio as redis
import requests
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Add a global exception handler to catch all unhandled exceptions
async def global_exception_handler(request: Request, exc: Exception):
    if isinstance(exc, (requests.Timeout, requests.ConnectionError)):
        logging.warning("Upstream service request failed (%s)", type(exc).__name__, exc_info=True)
        return JSONResponse(
            status_code=503,
            content={
                "error": "Service Unavailable",
                "detail": "A required service is temporarily unavailable. Please try again.",
            },
        )
    logging.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal Server Error", "detail": "An unexpected error occurred."},
    )


# Load environment variables from .env file
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Import API components after loading environment settings.
from app.core.config import settings
from app.api.v1 import generate
from app.api.v1 import stories
from app.api.v1 import account
from app.api.v1 import teacher
from app.api.v1 import teacher_documents
from app.api.v1 import study_materials
from app.api.v1 import teacher_presentation_renders
from app.api.v1 import teacher_video_renders
from app.api.brain import routes as brain_routes

# Initialize Limiter with stricter limits
limiter = Limiter(key_func=get_remote_address)

environment = settings.ENVIRONMENT.strip().lower()
origins = [origin.strip() for origin in settings.API_ALLOWED_ORIGINS.split(",") if origin.strip()]
if environment == "development":
    origins.append("*")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Validate production settings and initialize required infrastructure."""
    if environment == "production":
        errors = settings.production_configuration_errors()
        if errors:
            raise RuntimeError("Production configuration is incomplete: " + ", ".join(errors))

    redis_client = None
    try:
        redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        await redis_client.ping()
        app.state.redis_client = redis_client
        logging.info("Redis connection initialized successfully.")
    except Exception as error:
        app.state.redis_client = None
        if redis_client is not None:
            await redis_client.aclose()
        if environment == "production":
            raise RuntimeError("Redis is required in production but could not be reached.") from error
        logging.warning("Redis initialization failed; continuing without Redis: %s", error)

    try:
        yield
    finally:
        if redis_client is not None and app.state.redis_client is not None:
            await redis_client.aclose()

app = FastAPI(
    title="Fibonacci API",
    description="AI-powered educational video generation",
    version="1.0.0",
    docs_url=None if environment == "production" else "/docs",
    redoc_url=None if environment == "production" else "/redoc",
    openapi_url=None if environment == "production" else "/openapi.json",
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_exception_handler(Exception, global_exception_handler)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*", "Authorization"],
)

# Include API routers
app.include_router(generate.router, prefix="/api/v1")
app.include_router(stories.router, prefix="/api/v1")
app.include_router(account.router, prefix="/api/v1")
app.include_router(teacher.router, prefix="/api/v1")
app.include_router(study_materials.router, prefix="/api/v1")
app.include_router(teacher_presentation_renders.router, prefix="/api/v1")
app.include_router(teacher_video_renders.router, prefix="/api/v1")
app.include_router(brain_routes.router, prefix="/api/v1")
app.add_exception_handler(brain_routes.BrainError, brain_routes.brain_error_handler)

@app.get("/ping", status_code=200)
@limiter.limit("100/minute")
async def ping(request: Request):
    return {"status": "pong"}

@app.get("/health", status_code=200)
@limiter.limit("60/minute")
async def health_check(request: Request):
    return {"status": "ok"}

app.include_router(teacher_documents.router, prefix="/api/v1")

from app.api.upload_limit import DocumentUploadLimit
app.add_middleware(DocumentUploadLimit)
