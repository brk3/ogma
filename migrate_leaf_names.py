#!/usr/bin/env python3
"""One-off migration: renames files already linked under TV_ROOT/MOVIES_ROOT
from their old clean-name leaf to their original release filename, matching
what build_tv_dest/build_movie_dest now produce for new links.

Only renames files still hardlinked to a source in WATCH_DIR (recoverable);
anything else is left untouched.
"""
import logging
import os
import sys
from pathlib import Path

from link_media import MOVIES_ROOT, TV_ROOT, sanitize, setup_logging

WATCH_DIR = Path(os.environ.get("WATCH_DIR", "/data/downloads/complete"))


def index_watch_dir(watch_dir: Path) -> dict[tuple[int, int], Path]:
    index = {}
    for f in watch_dir.rglob("*"):
        if f.is_file():
            st = f.stat()
            index[(st.st_dev, st.st_ino)] = f
    return index


def migrate(root: Path, source_index: dict[tuple[int, int], Path]):
    renamed = orphaned = no_match = collision = 0
    for f in sorted(root.rglob("*")):
        if not f.is_file():
            continue
        st = f.stat()
        if st.st_nlink <= 1:
            logging.info("Orphaned, no source, leaving as-is: %s", f)
            orphaned += 1
            continue
        source = source_index.get((st.st_dev, st.st_ino))
        if source is None:
            logging.warning("Hardlinked but no matching WATCH_DIR entry, leaving as-is: %s", f)
            no_match += 1
            continue
        new_name = sanitize(source.name)
        if new_name == f.name:
            continue
        new_path = f.with_name(new_name)
        if new_path.exists():
            logging.warning("Target name already exists, leaving as-is: %s -> %s", f, new_path)
            collision += 1
            continue
        f.rename(new_path)
        logging.info("Renamed %s -> %s", f, new_path)
        renamed += 1
    return renamed, orphaned, no_match, collision


def main() -> int:
    setup_logging()
    if not WATCH_DIR.exists():
        logging.error("Watch directory does not exist: %s", WATCH_DIR)
        return 1

    logging.info("Indexing %s", WATCH_DIR)
    source_index = index_watch_dir(WATCH_DIR)
    logging.info("Indexed %d source files", len(source_index))

    totals = [0, 0, 0, 0]
    for root in (TV_ROOT, MOVIES_ROOT):
        if not root.exists():
            continue
        logging.info("Migrating %s", root)
        results = migrate(root, source_index)
        totals = [t + r for t, r in zip(totals, results)]

    renamed, orphaned, no_match, collision = totals
    logging.info(
        "Done: renamed=%d orphaned=%d no_match=%d collision=%d",
        renamed, orphaned, no_match, collision,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
