# Ogma

Watches qBittorrent's completed-downloads folder and hardlinks finished
downloads into Plex-friendly `TV/` and `Movies/` trees. Replaces the *arr stack
for the case where you just want files named correctly.

## How it works

Hardlinks, never moves: the source stays where qBittorrent expects it, so
seeding continues, and the link costs no extra disk. Falls back to a copy if
source and destination are on different filesystems.

`link_media.py` holds the naming and linking logic as plain functions.
`watch.py` is the filesystem-watching entrypoint. `health.py` serves the
Kubernetes probes.

Everything is idempotent — `link_file()` skips destinations that already exist —
so the startup scan safely catches up on anything missed while Ogma was down.

## Configuration

| Env var | Default | Meaning |
| --- | --- | --- |
| `WATCH_DIR` | `/data/downloads/complete` | qBittorrent's completed folder |
| `TV_ROOT` | `/data/tv` | Plex TV library |
| `MOVIES_ROOT` | `/data/movies` | Plex Movies library |
| `MIN_VIDEO_SIZE_MB` | `50` | Skip files smaller than this |
| `SETTLE_SECONDS` | `5` | Wait after an entry appears before linking |
| `HEALTH_PORT` | `8080` | Port for `/healthz` and `/readyz` |
| `LOG_FILE` | _(unset)_ | Also log to this file |

## Health

- `/healthz` — 503 if the watcher thread has died or the main loop has stalled.
  The watcher thread dying while the process stays up is the failure this is
  here to catch.
- `/readyz` — 503 until the startup scan finishes.

## Development

```sh
make venv
make test
```

## Releasing

Built locally and pushed to GHCR; there is no CI.

```sh
git tag v0.1.0
make release
```

Flux's ImagePolicy in [brk3/homelab](https://github.com/brk3/homelab) watches
`ghcr.io/brk3/ogma` and commits the new tag into the deployment manifest.

The image is always built `linux/amd64` (the homelab node is Intel) even when
built from an arm64 Mac; `make build` fails loudly if the architecture comes
out wrong.
