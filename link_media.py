"""Linking logic for organizing finished downloads into Plex-friendly TV/Movies folders.

Pure functions used by watch.py (and by the tests). No CLI entrypoint here.
"""
import logging
import os
import shutil
import sys
from pathlib import Path

from guessit import guessit  # noqa: F401  (re-exported for watch.py)

VIDEO_EXTENSIONS = {".mkv", ".mp4", ".avi", ".m4v", ".ts", ".wmv", ".mov"}
MIN_VIDEO_SIZE_MB = int(os.environ.get("MIN_VIDEO_SIZE_MB", "50"))
TV_ROOT = Path(os.environ.get("TV_ROOT", "/data/tv"))
MOVIES_ROOT = Path(os.environ.get("MOVIES_ROOT", "/data/movies"))
LOG_FILE = os.environ.get("LOG_FILE", "")


def setup_logging():
    handlers = [logging.StreamHandler(sys.stdout)]
    if LOG_FILE:
        Path(LOG_FILE).parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(LOG_FILE))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=handlers,
    )


def sanitize(name: str) -> str:
    name = name.strip().rstrip(".")
    for ch in '<>:"/\\|?*':
        name = name.replace(ch, "")
    return " ".join(name.split())


def iter_video_files(content_path: Path, min_size_mb: int = MIN_VIDEO_SIZE_MB):
    candidates = [content_path] if content_path.is_file() else sorted(content_path.rglob("*"))
    for f in candidates:
        if not f.is_file() or f.suffix.lower() not in VIDEO_EXTENSIONS:
            continue
        if "sample" in f.name.lower():
            continue
        if f.stat().st_size < min_size_mb * 1024 * 1024:
            continue
        yield f


def guess_media_type(info: dict, category: str = "") -> str:
    category = (category or "").lower()
    if category in ("tv", "series", "shows"):
        return "episode"
    if category in ("movies", "movie"):
        return "movie"
    return info.get("type", "movie")


def build_tv_dest(f: Path, info: dict, root: Path = TV_ROOT):
    title = info.get("title")
    season = info.get("season")
    episode = info.get("episode")
    if not title or season is None or episode is None:
        return None
    year = info.get("year")
    show_dir = f"{sanitize(title)} ({year})" if year else sanitize(title)
    episodes = episode if isinstance(episode, list) else [episode]
    ep_str = "".join(f"E{e:02d}" for e in episodes)
    episode_title = info.get("episode_title")
    filename = f"{sanitize(title)} - S{season:02d}{ep_str}"
    if episode_title:
        filename += f" - {sanitize(episode_title)}"
    filename += f.suffix.lower()
    return root / show_dir / f"Season {season:02d}" / filename


def build_movie_dest(f: Path, info: dict, root: Path = MOVIES_ROOT):
    title = info.get("title")
    if not title:
        return None
    year = info.get("year")
    name = f"{sanitize(title)} ({year})" if year else sanitize(title)
    return root / name / f"{name}{f.suffix.lower()}"


def link_file(src: Path, dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        logging.warning("Destination already exists, skipping: %s", dest)
        return
    try:
        os.link(src, dest)
        logging.info("Hardlinked %s -> %s", src, dest)
    except OSError as e:
        logging.warning("Hardlink failed (%s), falling back to copy: %s -> %s", e, src, dest)
        shutil.copy2(src, dest)
