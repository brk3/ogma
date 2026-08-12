import os

from migrate_leaf_names import index_watch_dir, migrate


def link(src, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    os.link(src, dest)


class TestMigrate:
    def test_renames_hardlinked_file_to_source_name(self, tmp_path):
        watch_dir = tmp_path / "downloads"
        watch_dir.mkdir()
        source = watch_dir / "Show.Name.S01E02.1080p.WEB.x264-GRP.mkv"
        source.write_bytes(b"data")

        tv_root = tmp_path / "tv"
        dest = tv_root / "Show Name" / "Season 01" / "Show Name - S01E02.mkv"
        link(source, dest)

        results = migrate(tv_root, index_watch_dir(watch_dir))

        assert results == (1, 0, 0, 0)
        new_path = tv_root / "Show Name" / "Season 01" / "Show.Name.S01E02.1080p.WEB.x264-GRP.mkv"
        assert new_path.exists()
        assert not dest.exists()
        assert new_path.stat().st_ino == source.stat().st_ino

    def test_leaves_orphaned_file_untouched(self, tmp_path):
        watch_dir = tmp_path / "downloads"
        watch_dir.mkdir()

        tv_root = tmp_path / "tv"
        dest = tv_root / "Show Name" / "Season 01" / "Show Name - S01E02.mkv"
        dest.parent.mkdir(parents=True)
        dest.write_bytes(b"data")

        results = migrate(tv_root, index_watch_dir(watch_dir))

        assert results == (0, 1, 0, 0)
        assert dest.exists()

    def test_leaves_already_correctly_named_file_untouched(self, tmp_path):
        watch_dir = tmp_path / "downloads"
        watch_dir.mkdir()
        source = watch_dir / "Movie.2019.1080p.BluRay-GRP.mkv"
        source.write_bytes(b"data")

        movies_root = tmp_path / "movies"
        dest = movies_root / "Movie (2019)" / "Movie.2019.1080p.BluRay-GRP.mkv"
        link(source, dest)

        results = migrate(movies_root, index_watch_dir(watch_dir))

        assert results == (0, 0, 0, 0)
        assert dest.exists()

    def test_skips_on_target_collision(self, tmp_path):
        watch_dir = tmp_path / "downloads"
        watch_dir.mkdir()
        source = watch_dir / "Movie.2019.1080p.BluRay-GRP.mkv"
        source.write_bytes(b"data")

        movies_root = tmp_path / "movies"
        dest = movies_root / "Movie (2019)" / "Movie (2019).mkv"
        link(source, dest)
        existing = movies_root / "Movie (2019)" / "Movie.2019.1080p.BluRay-GRP.mkv"
        existing.write_bytes(b"other")

        results = migrate(movies_root, index_watch_dir(watch_dir))

        assert results == (0, 1, 0, 1)
        assert dest.exists()
        assert existing.read_bytes() == b"other"

    def test_leaves_hardlink_with_no_watch_dir_match_untouched(self, tmp_path):
        watch_dir = tmp_path / "downloads"
        watch_dir.mkdir()
        elsewhere = tmp_path / "elsewhere.mkv"
        elsewhere.write_bytes(b"data")

        movies_root = tmp_path / "movies"
        dest = movies_root / "Movie (2019)" / "Movie (2019).mkv"
        link(elsewhere, dest)

        results = migrate(movies_root, index_watch_dir(watch_dir))

        assert results == (0, 0, 1, 0)
        assert dest.exists()
