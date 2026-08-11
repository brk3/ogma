import watch
from watch import CompletedDownloadHandler, process_entry, scan_existing


class TestProcessEntry:
    def test_prefers_folder_title_over_lowercase_file_title(self, tmp_path):
        entry = tmp_path / "downloads" / "King.of.the.Hill.S15E08.1080p.WEB.H264-CAKES"
        entry.mkdir(parents=True)
        video = entry / "king.of.the.hill.s15e08.1080p.web.h264-cakes.mkv"
        video.write_bytes(b"0" * 10)
        tv_root = tmp_path / "tv"

        process_entry(entry, tv_root=tv_root, min_size_mb=0)

        linked = list(tv_root.rglob("*.mkv"))
        assert linked == [tv_root / "King of the Hill" / "Season 15" / "King of the Hill - S15E08.mkv"]

    def test_single_file_entry_uses_its_own_title(self, tmp_path):
        entry = tmp_path / "downloads" / "Knives Out 2019 1080p BluRay HEVC x265 5.1 BONE.mkv"
        entry.parent.mkdir(parents=True)
        entry.write_bytes(b"0" * 10)
        movies_root = tmp_path / "movies"

        process_entry(entry, movies_root=movies_root, min_size_mb=0)

        linked = list(movies_root.rglob("*.mkv"))
        assert linked == [movies_root / "Knives Out (2019)" / "Knives Out (2019).mkv"]

    def test_nonexistent_path_is_a_noop(self, tmp_path):
        process_entry(tmp_path / "does-not-exist")


class TestFailureContainment:
    """A single bad entry must never take down the watcher thread."""

    def test_handler_swallows_processing_errors(self, tmp_path, monkeypatch):
        monkeypatch.setattr(watch, "WATCH_DIR", tmp_path)
        monkeypatch.setattr(watch, "SETTLE_SECONDS", 0)

        def boom(*args, **kwargs):
            raise RuntimeError("guessit exploded")

        monkeypatch.setattr(watch, "process_entry", boom)

        CompletedDownloadHandler()._handle(str(tmp_path / "Some.Release.mkv"))

    def test_scan_continues_past_a_failing_entry(self, tmp_path, monkeypatch):
        for name in ("a", "b", "c"):
            (tmp_path / name).mkdir()
        seen = []

        def flaky(path, **kwargs):
            seen.append(path.name)
            if path.name == "b":
                raise RuntimeError("bad entry")

        monkeypatch.setattr(watch, "process_entry", flaky)
        scan_existing(tmp_path)

        assert seen == ["a", "b", "c"]

    def test_handler_ignores_writes_inside_an_entry(self, tmp_path, monkeypatch):
        monkeypatch.setattr(watch, "WATCH_DIR", tmp_path)
        monkeypatch.setattr(watch, "SETTLE_SECONDS", 0)
        called = []
        monkeypatch.setattr(watch, "process_entry", lambda p, **kw: called.append(p))

        CompletedDownloadHandler()._handle(str(tmp_path / "Release" / "part.mkv"))

        assert called == []
