"""
PaciFund — Funding Rate Arbitrage Scanner & Auto-Executor
Built for Pacifica Hackathon 2025

Run:
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload
"""
import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.routes import router

# ── Logging ──────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(name)-20s │ %(levelname)-5s │ %(message)s",
    datefmt="%H:%M:%S",
)

# ── App ──────────────────────────────────────
app = FastAPI(
    title="PaciFund",
    description="Funding rate arbitrage scanner & auto-executor on Pacifica",
    version="1.0.0",
)

# CORS for local frontend dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API
app.include_router(router)

# Serve frontend (static build)
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.isdir(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")


@app.on_event("startup")
async def startup():
    os.makedirs("data", exist_ok=True)
    logging.info("PaciFund started — scanning for funding rate arb opportunities")


@app.on_event("shutdown")
async def shutdown():
    from api.routes import pacifica_collector, binance_collector, executor
    await pacifica_collector.close()
    await binance_collector.close()
    await executor.close()
    logging.info("PaciFund shut down")
