import asyncio
import time
from pathlib import Path

from watchdog.events import FileSystemEventHandler, FileSystemEvent
from watchdog.observers import Observer

from songwriter.api.schemas import Song
from songwriter.api.ws import ConnectionManager


_SELF_WRITE_WINDOW_S = 0.5


class _Handler(FileSystemEventHandler):
    def __init__(self, watcher: "SongFileWatcher") -> None:
        self.watcher = watcher

    def on_modified(self, event: FileSystemEvent):
        if event.is_directory:
            return
        self.watcher._on_file_event(Path(event.src_path))

    def on_created(self, event: FileSystemEvent):
        if event.is_directory:
            return
        self.watcher._on_file_event(Path(event.src_path))


class SongFileWatcher:
    def __init__(self, songs_dir: Path, manager: ConnectionManager,
                 loop: asyncio.AbstractEventLoop | None = None) -> None:
        self.songs_dir = songs_dir
        self.manager = manager
        self.loop = loop
        self._observer = Observer()
        self._self_writes: dict[str, float] = {}

    def start(self) -> None:
        self.songs_dir.mkdir(parents=True, exist_ok=True)
        self._observer.schedule(_Handler(self), str(self.songs_dir), recursive=False)
        self._observer.start()

    def stop(self) -> None:
        self._observer.stop()
        self._observer.join(timeout=2)

    def note_self_write(self, slug: str) -> None:
        self._self_writes[slug] = time.time()

    def _is_self_write(self, slug: str) -> bool:
        ts = self._self_writes.get(slug)
        if ts is None:
            return False
        return (time.time() - ts) < _SELF_WRITE_WINDOW_S

    def _on_file_event(self, path: Path) -> None:
        if path.suffix != ".json":
            return
        slug = path.stem
        if self._is_self_write(slug):
            return
        try:
            song = Song.model_validate_json(path.read_text())
        except Exception:
            return
        payload = {"type": "update", "source": "external", "song": song.model_dump(mode="json")}
        if self.loop is not None:
            asyncio.run_coroutine_threadsafe(self.manager.broadcast(slug, payload), self.loop)
        else:
            # fallback for tests without a running loop
            try:
                loop = asyncio.get_event_loop()
                loop.create_task(self.manager.broadcast(slug, payload))
            except RuntimeError:
                asyncio.run(self.manager.broadcast(slug, payload))
