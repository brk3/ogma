from pathlib import Path

from guessit import guessit

import link_media as lm


class TestSanitize:
    def test_strips_invalid_chars(self):
        assert lm.sanitize('Foo: Bar/Baz?') == "Foo BarBaz"

    def test_collapses_whitespace_and_trailing_dot(self):
        assert lm.sanitize("  Foo   Bar.  ") == "Foo Bar"


class TestGuessMediaType:
    def test_category_tv_wins(self):
        assert lm.guess_media_type({"type": "movie"}, "tv") == "episode"

    def test_category_movies_wins(self):
        assert lm.guess_media_type({"type": "episode"}, "movies") == "movie"

    def test_falls_back_to_guessit_type(self):
        assert lm.guess_media_type({"type": "episode"}, "") == "episode"

    def test_falls_back_to_movie_when_unknown(self):
        assert lm.guess_media_type({}, "") == "movie"


class TestBuildTvDest:
    def test_single_episode(self):
        info = {"title": "Example Show", "season": 15, "episode": 8}
        dest = lm.build_tv_dest(Path("ep.mkv"), info, root=Path("/tv"))
        assert dest == Path("/tv/Example Show/Season 15/ep.mkv")

    def test_multi_episode_folder_placement(self):
        info = {"title": "Show", "season": 1, "episode": [1, 2]}
        dest = lm.build_tv_dest(Path("Show.S01E01E02.mkv"), info, root=Path("/tv"))
        assert dest == Path("/tv/Show/Season 01/Show.S01E01E02.mkv")

    def test_includes_year_in_folder(self):
        info = {"title": "Show", "year": 2020, "season": 1, "episode": 1}
        dest = lm.build_tv_dest(Path("Show.S01E01.mkv"), info, root=Path("/tv"))
        assert dest.parent.parent.name == "Show (2020)"
        assert dest.name == "Show.S01E01.mkv"

    def test_missing_season_returns_none(self):
        info = {"title": "Show", "episode": 1}
        assert lm.build_tv_dest(Path("ep.mkv"), info, root=Path("/tv")) is None

    def test_missing_title_returns_none(self):
        info = {"season": 1, "episode": 1}
        assert lm.build_tv_dest(Path("ep.mkv"), info, root=Path("/tv")) is None


class TestBuildMovieDest:
    def test_with_year(self):
        info = {"title": "Example Movie", "year": 2019}
        dest = lm.build_movie_dest(Path("movie.mkv"), info, root=Path("/movies"))
        assert dest == Path("/movies/Example Movie (2019)/movie.mkv")

    def test_without_year(self):
        info = {"title": "Example Movie"}
        dest = lm.build_movie_dest(Path("movie.mkv"), info, root=Path("/movies"))
        assert dest == Path("/movies/Example Movie/movie.mkv")

    def test_missing_title_returns_none(self):
        assert lm.build_movie_dest(Path("movie.mkv"), {}, root=Path("/movies")) is None


class TestIterVideoFiles:
    def test_filters_extension_and_sample(self, tmp_path):
        episode = tmp_path / "Show.S01E01.mkv"
        episode.write_bytes(b"0" * 10)
        sample = tmp_path / "Show.S01E01.sample.mkv"
        sample.write_bytes(b"0" * 10)
        not_video = tmp_path / "Show.S01E01.nfo"
        not_video.write_bytes(b"0" * 10)

        results = set(lm.iter_video_files(tmp_path, min_size_mb=0))

        assert results == {episode}

    def test_size_filter(self, tmp_path):
        f = tmp_path / "Show.S01E01.mkv"
        f.write_bytes(b"0" * 10)
        assert list(lm.iter_video_files(tmp_path, min_size_mb=1)) == []
        assert list(lm.iter_video_files(tmp_path, min_size_mb=0)) == [f]

    def test_single_file_input(self, tmp_path):
        f = tmp_path / "movie.mkv"
        f.write_bytes(b"0" * 10)
        assert list(lm.iter_video_files(f, min_size_mb=0)) == [f]


class TestLinkFile:
    def test_hardlinks_and_creates_parent_dirs(self, tmp_path):
        src = tmp_path / "src.mkv"
        src.write_bytes(b"data")
        dest = tmp_path / "nested" / "dir" / "dest.mkv"

        lm.link_file(src, dest)

        assert dest.exists()
        assert src.stat().st_ino == dest.stat().st_ino

    def test_skips_if_dest_exists(self, tmp_path):
        src = tmp_path / "src.mkv"
        src.write_bytes(b"data")
        dest = tmp_path / "dest.mkv"
        dest.write_bytes(b"existing")

        lm.link_file(src, dest)

        assert dest.read_bytes() == b"existing"

    def test_reprocessing_already_linked_file_is_a_noop(self, tmp_path):
        src = tmp_path / "src.mkv"
        src.write_bytes(b"data")
        dest = tmp_path / "dest.mkv"
        lm.link_file(src, dest)

        lm.link_file(src, dest, info={"screen_size": "2160p"})

        assert sorted(tmp_path.glob("*.mkv")) == [dest, src]

    def test_disambiguates_with_quality_tag_on_collision(self, tmp_path):
        src = tmp_path / "src.mkv"
        src.write_bytes(b"new")
        dest = tmp_path / "dest.mkv"
        dest.write_bytes(b"existing")

        lm.link_file(src, dest, info={"screen_size": "2160p"})

        assert dest.read_bytes() == b"existing"
        alt = tmp_path / "dest - 2160p.mkv"
        assert alt.stat().st_ino == src.stat().st_ino

    def test_falls_back_to_source_tag_when_no_screen_size(self, tmp_path):
        src = tmp_path / "src.mkv"
        src.write_bytes(b"new")
        dest = tmp_path / "dest.mkv"
        dest.write_bytes(b"existing")

        lm.link_file(src, dest, info={"source": "BluRay"})

        alt = tmp_path / "dest - BluRay.mkv"
        assert alt.stat().st_ino == src.stat().st_ino

    def test_skips_when_disambiguated_dest_also_collides(self, tmp_path):
        src = tmp_path / "src.mkv"
        src.write_bytes(b"new")
        dest = tmp_path / "dest.mkv"
        dest.write_bytes(b"existing")
        alt = tmp_path / "dest - 2160p.mkv"
        alt.write_bytes(b"also existing")

        lm.link_file(src, dest, info={"screen_size": "2160p"})

        assert dest.read_bytes() == b"existing"
        assert alt.read_bytes() == b"also existing"

    def test_falls_back_to_copy_when_hardlink_fails(self, tmp_path, monkeypatch):
        src = tmp_path / "src.mkv"
        src.write_bytes(b"data")
        dest = tmp_path / "dest.mkv"

        def raise_oserror(*args, **kwargs):
            raise OSError("cross-device link")

        monkeypatch.setattr(lm.os, "link", raise_oserror)
        lm.link_file(src, dest)

        assert dest.read_bytes() == b"data"


class TestRealWorldFilenames:
    """Regression tests for common release-naming conventions."""

    def test_sonarr_style_episode(self):
        name = "Example.Show.S15E08.1080p.WEB.H264-GRP.mkv"
        info = guessit(name)
        assert lm.guess_media_type(info, "") == "episode"
        dest = lm.build_tv_dest(Path(name), info, root=Path("/tv"))
        assert dest == Path(f"/tv/Example Show/Season 15/{name}")

    def test_radarr_style_movie(self):
        name = "Example Movie 2019 1080p BluRay HEVC x265 5.1 GRP.mkv"
        info = guessit(name)
        assert lm.guess_media_type(info, "") == "movie"
        dest = lm.build_movie_dest(Path(name), info, root=Path("/movies"))
        assert dest == Path(f"/movies/Example Movie (2019)/{name}")

    def test_two_quality_grabs_of_same_episode_keep_distinct_names(self):
        """The 4k-vs-1080p collision suffix in link_file() is a fallback, not the
        primary mechanism: distinct release names already avoid the collision."""
        info_1080p = guessit("Example.Show.S15E08.1080p.WEB.H264-GRP.mkv")
        info_2160p = guessit("Example.Show.S15E08.2160p.WEB.H264-GRP.mkv")
        dest_1080p = lm.build_tv_dest(
            Path("Example.Show.S15E08.1080p.WEB.H264-GRP.mkv"), info_1080p, root=Path("/tv")
        )
        dest_2160p = lm.build_tv_dest(
            Path("Example.Show.S15E08.2160p.WEB.H264-GRP.mkv"), info_2160p, root=Path("/tv")
        )
        assert dest_1080p.parent == dest_2160p.parent
        assert dest_1080p != dest_2160p
