from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.routes_ai_effects import router as ai_effects_router
from app.api.routes_debug import router as debug_router
from app.api.routes_generation import router as generation_router
from app.api.routes_health import router as health_router
from app.api.routes_immich import router as immich_router
from app.api.routes_metrics import router as metrics_router
from app.api.routes_presets import router as presets_router
from app.api.routes_push import router as push_router
from app.api.routes_schedules import router as schedules_router
from app.api.routes_settings import router as settings_router
from app.api.routes_studio import router as studio_router
from app.config import get_settings
from app.database import init_db
from app.limiter import limiter
from app.observability.logging import setup_logging
from app.version import APP_VERSION

setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # Reset any stuck RUNNING tasks to FAILED
    from app.database import SessionLocal
    from app.models.generation_history import GenerationHistoryModel

    db = SessionLocal()
    try:
        stuck_tasks = db.query(GenerationHistoryModel).filter(GenerationHistoryModel.status == "RUNNING").all()
        if stuck_tasks:
            for task in stuck_tasks:
                task.status = "FAILED"
                task.error = "Interrupted by system restart"
            db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()
    yield


app = FastAPI(
    title="DailyFX for Immich",
    description="Self-hosted creative companion for Immich. Transform your photo library with 40+ built-in effects and AI-generated styles.",
    version=APP_VERSION,
    license_info={
        "name": "PolyForm Noncommercial License 1.0.0",
        "url": "https://polyformproject.org/licenses/noncommercial/1.0.0/",
    },
    openapi_tags=[
        {"name": "health", "description": "API and component health checks"},
        {"name": "settings", "description": "Application settings and provider connection tests"},
        {"name": "immich", "description": "Immich asset search, thumbnails, EXIF metadata, and filter options"},
        {"name": "generation", "description": "Image generation pipeline, history, accept/reject, and SSE stream"},
        {"name": "ai-effects", "description": "Manage AI effect definitions (CRUD, import/export)"},
        {"name": "presets", "description": "Filter, effect, and notification presets"},
        {"name": "schedules", "description": "Automation schedules for recurring generation"},
        {"name": "studio", "description": "Manual effect preview on uploaded images"},
        {"name": "notifications", "description": "Web Push subscriptions and VAPID key"},
        {"name": "metrics", "description": "Prometheus-style metrics endpoint"},
        {"name": "debug", "description": "Debug endpoints (logs, scheduler state)"},
    ],
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(immich_router)
app.include_router(settings_router)
app.include_router(generation_router)
app.include_router(push_router)
app.include_router(debug_router)
app.include_router(presets_router)
app.include_router(ai_effects_router)
app.include_router(schedules_router)
app.include_router(studio_router)
app.include_router(metrics_router)
