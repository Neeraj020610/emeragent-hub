from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import time

import asyncio
import logging
from app.config import settings
from app.api.v1.api import api_router
from app.database import SessionLocal
from app.db_init import init_db
from app.models.autonomous import AutonomousSystemState
from app.services.autonomous.worker_engine import AutonomousWorkerEngine

logger = logging.getLogger("autonomous_worker")

async def autonomous_background_worker():
    """Background polling loop for autonomous tasks and pipeline jobs."""
    engine = AutonomousWorkerEngine()
    while True:
        try:
            await asyncio.sleep(4)
            db = SessionLocal()
            try:
                system_state = db.query(AutonomousSystemState).first()
                if system_state and system_state.status == "RUNNING":
                    engine.poll_and_dispatch_next_task(db=db)
            except Exception as e:
                logger.debug(f"Background worker step pass: {e}")
            finally:
                db.close()
        except asyncio.CancelledError:
            break
        except Exception:
            await asyncio.sleep(4)

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Centralized administration platform for Emergent AI accounts, credits, build requests, and OTP orchestration.",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Security and Performance Headers Middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = f"{process_time:.4f}s"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response


@app.on_event("startup")
async def on_startup():
    from app.services.autonomous.adapters.emergent_browser_adapter import set_main_loop

    set_main_loop(asyncio.get_running_loop())
    db = SessionLocal()
    try:
        init_db(db)
        # Ensure system state is RUNNING
        sys_state = db.query(AutonomousSystemState).first()
        if not sys_state:
            sys_state = AutonomousSystemState(status="RUNNING", last_command="START")
            db.add(sys_state)
            db.commit()
        elif sys_state.status == "STOPPED":
            sys_state.status = "RUNNING"
            sys_state.last_command = "START"
            db.commit()
    finally:
        db.close()
    
    # Spawn background autonomous worker
    asyncio.create_task(autonomous_background_worker())


@app.get("/health", tags=["system"])
def health_check():
    """
    Application health and readiness probe.
    """
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": "1.0.0",
        "timestamp": time.time(),
    }


# Include modular API v1 router
app.include_router(api_router, prefix=settings.API_V1_STR)
