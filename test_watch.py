import watch
from watch import CompletedDownloadHandler, process_entry, scan_existing


class TestProcessEntry:
    def test_prefers_folder_title_over_lowercase_file_title(self, tmp_path):
        """The folder-cased title still governs the show/season folder even though
        the leaf filename is now preserved as-is, lowercase and all."""
        entry = tmp_path / "downloads" / "Example.Show.S15E08.1080p.WEB.H264-GRP"
        entry.mkdir(parents=True)
        video = entry / "example.show.s15e08.1080p.web.h264-grp.mkv"
        video.write_bytes(b"0" * 10)
        tv_root = tmp_path / "tv"

        process_entry(entry, tv_root=tv_root, min_size_mb=0)

        linked = list(tv_root.rglob("*.mkv"))
        assert linked == [
            tv_root / "Example Show" / "Season 15" / "example.show.s15e08.1080p.web.h264-grp.mkv"
        ]

    def test_single_file_entry_uses_its_own_title(self, tmp_path):
        entry = tmp_path / "downloads" / "Example Movie 2019 1080p BluRay HEVC x265 5.1 GRP.mkv"
        entry.parent.mkdir(parents=True)
        entry.write_bytes(b"0" * 10)
        movies_root = tmp_path / "movies"

        process_entry(entry, movies_root=movies_root, min_size_mb=0)

        linked = list(movies_root.rglob("*.mkv"))
        assert linked == [
            movies_root / "Example Movie (2019)" / "Example Movie 2019 1080p BluRay HEVC x265 5.1 GRP.mkv"
        ]

    def test_nonexistent_path_is_a_noop(self, tmp_path):
        process_entry(tmp_path / "does-not-exist")

    def test_same_movie_different_quality_both_linked(self, tmp_path):
        """Distinct release names already keep these apart -- link_file()'s quality-tag
        disambiguation is a fallback for same-named collisions, not the primary mechanism."""
        movies_root = tmp_path / "movies"
        entry_1080 = tmp_path / "downloads-1080p" / "Example Movie 2019 1080p BluRay HEVC x265 5.1 GRP.mkv"
        entry_1080.parent.mkdir(parents=True)
        entry_1080.write_bytes(b"1" * 10)
        entry_2160 = tmp_path / "downloads-2160p" / "Example Movie 2019 2160p UHD BluRay HEVC x265 5.1 GRP.mkv"
        entry_2160.parent.mkdir(parents=True)
        entry_2160.write_bytes(b"2" * 10)

        process_entry(entry_1080, movies_root=movies_root, min_size_mb=0)
        process_entry(entry_2160, movies_root=movies_root, min_size_mb=0)

        linked = {p.name for p in movies_root.rglob("*.mkv")}
        assert linked == {
            "Example Movie 2019 1080p BluRay HEVC x265 5.1 GRP.mkv",
            "Example Movie 2019 2160p UHD BluRay HEVC x265 5.1 GRP.mkv",
        }

    def test_small_episode_that_parses_is_still_linked(self, tmp_path):
        """A 360p rip can be well under 50 MB; the size gate must not eat real
        episodes just because they parse cleanly."""
        entry = tmp_path / "downloads" / "Example.Show.S01E01.360p.WEB.H264-GRP"
        entry.mkdir(parents=True)
        video = entry / "example.show.s01e01.360p.web.h264-grp.mkv"
        video.write_bytes(b"0" * 10)  # tiny, but names itself as a real episode
        tv_root = tmp_path / "tv"

        process_entry(entry, tv_root=tv_root, min_size_mb=50)

        assert list(tv_root.rglob("*.mkv")) == [
            tv_root / "Example Show" / "Season 01" / "example.show.s01e01.360p.web.h264-grp.mkv"
        ]

    def test_small_unparseable_file_is_still_skipped(self, tmp_path):
        entry = tmp_path / "downloads" / "1080p.WEB-DL.x264-GRP.mkv"
        entry.parent.mkdir(parents=True)
        entry.write_bytes(b"0" * 10)
        movies_root = tmp_path / "movies"

        process_entry(entry, movies_root=movies_root, min_size_mb=1)

        assert list(movies_root.rglob("*.mkv")) == []


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
