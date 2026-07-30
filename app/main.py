from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import configure_logging
from fastapi import Request
from fastapi.responses import JSONResponse

configure_logging()
settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "Generates AI-recreated Magic: The Gathering-style proxy cards. "
        "Pulls accurate card data from Scryfall and generates artwork via a "
        "pluggable AI image provider, in either 'hybrid' (accurate composited "
        "text) or 'full_ai' (single generated image) mode."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")

# Serve generated images so the client can view them directly via URL,
# e.g. http://localhost:8000/outputs/goblin-hybrid-1a2b3c4d.png
app.mount("/outputs", StaticFiles(directory=settings.OUTPUT_DIR), name="outputs")


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


@app.get("/", tags=["root"])
async def root():
    return {
        "message": f"{settings.APP_NAME} is running.",
        "docs": "/docs",
        "demo_endpoint": "/api/v1/cards/demo/client-cards",
    }
