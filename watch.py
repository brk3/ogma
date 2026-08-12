#!/usr/bin/env python3
"""Ogma: watches for finished qBittorrent downloads and links them into Plex's TV/Movies folders.

Watches WATCH_DIR (qBittorrent's completed-downloads folder) for new top-level
entries and hands each one to link_media's linking logic. Also scans whatever's
already there on startup -- link_media.link_file() is idempotent (skips
destinations that already exist), so re-processing existing entries is safe
and lets Ogma catch up on anything it missed while it wasn't running.

One unparseable entry logs and is skipped; a dead watcher thread exits the
process so Kubernetes restarts it.
"""
import logging
import os
import sys
import time
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from health import Health, start_health_server
from link_media import (
    MIN_VIDEO_SIZE_MB,
    MOVIES_ROOT,
    TV_ROOT,
    build_movie_dest,
    build_tv_dest,
    guess_media_type,
    guessit,
    iter_video_files,
    link_file,
    setup_logging,
)

WATCH_DIR = Path(os.environ.get("WATCH_DIR", "/data/downloads/complete"))
SETTLE_SECONDS = int(os.environ.get("SETTLE_SECONDS", "5"))
HEALTH_PORT = int(os.environ.get("HEALTH_PORT", "8080"))
BEAT_SECONDS = int(os.environ.get("BEAT_SECONDS", "15"))


def process_entry(
    path: Path,
    tv_root: Path = TV_ROOT,
    movies_root: Path = MOVIES_ROOT,
    min_size_mb: int = MIN_VIDEO_SIZE_MB,
):
    if not path.exists():
        return
    # Prefer the containing folder's title/year over the file's: release folder
    # names are almost always properly cased even when the file inside isn't.
    folder_info = guessit(path.name) if path.is_dir() else {}
    for f in iter_video_files(path, min_size_mb=min_size_mb):
        info = guessit(f.name)
        if folder_info.get("title"):
            info["title"] = folder_info["title"]
        if folder_info.get("year"):
            info["year"] = folder_info["year"]
        media_type = guess_media_type(info)
        dest = build_tv_dest(f, info, root=tv_root) if media_type == "episode" else build_movie_dest(f, info, root=movies_root)
        if dest is None:
            logging.warning("Could not determine destination for %s (guessit: %s)", f, info)
            continue
        link_file(f, dest, info)


class CompletedDownloadHandler(FileSystemEventHandler):
    def on_created(self, event):
        self._handle(event.src_path)

    def on_moved(self, event):
        self._handle(event.dest_path)

    def _handle(self, raw_path: str):
        path = Path(raw_path)
        if path.parent != WATCH_DIR:
            return  # only react to new top-level entries, not incremental writes inside them
        logging.info("New entry detected: %s", path)
        time.sleep(SETTLE_SECONDS)
        # watchdog's dispatcher only catches queue.Empty; anything else escaping
        # here kills the thread.
        try:
            process_entry(path)
        except Exception:
            logging.exception("Failed to process %s", path)


def scan_existing(watch_dir: Path = WATCH_DIR):
    """Process everything already sitting in watch_dir, skipping entries that fail."""
    logging.info("Scanning existing entries under %s", watch_dir)
    for entry in sorted(watch_dir.iterdir()):
        try:
            process_entry(entry)
        except Exception:
            logging.exception("Failed to process %s", entry)
    logging.info("Initial scan complete")


def main() -> int:
    setup_logging()
    health = Health()
    start_health_server(health, HEALTH_PORT)

    if not WATCH_DIR.exists():
        logging.error("Watch directory does not exist: %s", WATCH_DIR)
        return 1

    # Watch before scanning, or a download completing mid-scan is missed until
    # the next restart. Double-processing is harmless.
    observer = Observer()
    observer.schedule(CompletedDownloadHandler(), str(WATCH_DIR), recursive=False)
    observer.start()
    health.track(observer)
    logging.info("Watching %s for new downloads", WATCH_DIR)

    scan_existing()
    health.mark_ready()

    try:
        while True:
            if not observer.is_alive():
                logging.error("Watcher thread died; exiting so Kubernetes restarts us")
                return 1
            health.beat()
            time.sleep(BEAT_SECONDS)
    except KeyboardInterrupt:
        logging.info("Shutting down")
        observer.stop()
        observer.join()
        return 0


if __name__ == "__main__":
    sys.exit(main())
