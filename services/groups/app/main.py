import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings, logger
from app.db.database import engine
from app.db import models

models.Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize DB, gRPC server, RabbitMQ
    logger.info("Starting Groups Service...")
    # Start gRPC server
    from app.grpc.server import serve_grpc
    grpc_server = await serve_grpc()
    
    # Connect to RabbitMQ
    from app.core.events import publisher
    publisher.connect()
    yield
    # Shutdown: Clean up resources
    logger.info("Shutting down Groups Service...")
    await grpc_server.stop(0)
    publisher.close()

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/healthz")
def healthz():
    return {"status": "ok"}

@app.get("/readyz")
def readyz():
    return {"status": "ready"}

from app.api.v1 import groups, contacts

app.include_router(groups.router, prefix=f"{settings.API_V1_STR}/groups", tags=["groups"])
app.include_router(contacts.router, prefix=f"{settings.API_V1_STR}/contacts", tags=["contacts"])
