import asyncio
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .config import settings
from .models.database import init_db
from .routers import session, files, tasks
from .utils.cleanup import periodic_cleanup

# Frontend dist directory
FRONTEND_DIST = settings.PROJECT_ROOT / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    init_db()
    
    # Start background cleanup task
    cleanup_task = asyncio.create_task(run_periodic_cleanup())
    
    yield
    
    # Shutdown
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass


async def run_periodic_cleanup():
    """Run cleanup every hour."""
    while True:
        await asyncio.sleep(settings.CLEANUP_INTERVAL_HOURS * 3600)
        await periodic_cleanup()


app = FastAPI(
    title=settings.APP_NAME,
    description="Web service for BA-Modding-Toolkit",
    version="0.1.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(session.router, prefix="/api")
app.include_router(files.router, prefix="/api")
app.include_router(tasks.router, prefix="/api")


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


# Serve frontend static files
if FRONTEND_DIST.exists():
    # Mount static assets directory
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")
    
    @app.get("/{path:path}")
    async def serve_spa(request: Request, path: str):
        """
        Serve SPA - return index.html for all non-API routes.
        This enables client-side routing.
        """
        # Try to serve the exact file if it exists
        file_path = FRONTEND_DIST / path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        
        # Otherwise return index.html for SPA routing
        index_path = FRONTEND_DIST / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
        
        return {"detail": "Not found"}
else:
    # Development mode - return simple response
    @app.get("/")
    def root():
        """Root endpoint (dev mode)."""
        return {
            "name": settings.APP_NAME,
            "version": "0.1.0",
            "status": "running",
            "mode": "development",
            "frontend": "Run 'npm run dev' in frontend/ directory"
        }