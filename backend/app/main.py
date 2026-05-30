from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.routes_immich import router as immich_router
from app.api.routes_generation import router as generation_router
from app.api.routes_health import router as health_router
from app.api.routes_settings import router as settings_router
from app.api.routes_push import router as push_router
from app.api.routes_debug import router as debug_router
from app.api.routes_presets import router as presets_router
from app.api.routes_schedules import router as schedules_router
from app.config import get_settings
from app.database import init_db

limiter = Limiter(key_func=get_remote_address, default_limits=["120/minute"])


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


app = FastAPI(title="DailyFX for immich", version="0.1.0", lifespan=lifespan)
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
app.include_router(schedules_router)
