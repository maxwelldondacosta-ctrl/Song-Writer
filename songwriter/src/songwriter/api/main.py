import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from songwriter.api.settings import Settings, get_settings
from songwriter.api.routes import lookups, production, songwriters, descriptors, songs, validate, draft, suno_prompt, alternatives, anchors, coverage
from songwriter.api.watcher import SongFileWatcher
from songwriter.api.ws import manager as ws_manager


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        settings.songs_dir.mkdir(parents=True, exist_ok=True)
        loop = asyncio.get_running_loop()
        watcher = SongFileWatcher(songs_dir=settings.songs_dir, manager=ws_manager, loop=loop)
        watcher.start()
        app.state.watcher = watcher
        try:
            yield
        finally:
            watcher.stop()

    app = FastAPI(title="Songwriter API", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/")
    def root():
        return RedirectResponse(url=settings.cors_origins[0] if settings.cors_origins else "http://localhost:3000")

    @app.get("/healthz")
    def healthz():
        return {"status": "ok", "db": str(settings.db_path), "songs_dir": str(settings.songs_dir)}

    app.include_router(lookups.router)
    app.include_router(production.router)
    app.include_router(songwriters.router)
    app.include_router(descriptors.router)
    app.include_router(songs.router)
    app.include_router(validate.router)
    app.include_router(draft.router)
    app.include_router(suno_prompt.router)
    app.include_router(alternatives.router)
    app.include_router(anchors.router)
    app.include_router(coverage.router)

    app.state.settings = settings
    return app


app = create_app()
