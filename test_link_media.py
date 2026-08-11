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
        info = {"title": "King of the Hill", "season": 15, "episode": 8}
        dest = lm.build_tv_dest(Path("ep.mkv"), info, root=Path("/tv"))
        assert dest == Path("/tv/King of the Hill/Season 15/King of the Hill - S15E08.mkv")

    def test_multi_episode(self):
        info = {"title": "Show", "season": 1, "episode": [1, 2]}
        dest = lm.build_tv_dest(Path("ep.mkv"), info, root=Path("/tv"))
        assert dest.name == "Show - S01E01E02.mkv"

    def test_includes_year_and_episode_title(self):
        info = {"title": "Show", "year": 2020, "season": 1, "episode": 1, "episode_title": "Pilot"}
        dest = lm.build_tv_dest(Path("ep.mkv"), info, root=Path("/tv"))
        assert dest.parent.parent.name == "Show (2020)"
        assert dest.name == "Show - S01E01 - Pilot.mkv"

    def test_missing_season_returns_none(self):
        info = {"title": "Show", "episode": 1}
        assert lm.build_tv_dest(Path("ep.mkv"), info, root=Path("/tv")) is None

    def test_missing_title_returns_none(self):
        info = {"season": 1, "episode": 1}
        assert lm.build_tv_dest(Path("ep.mkv"), info, root=Path("/tv")) is None


class TestBuildMovieDest:
    def test_with_year(self):
        info = {"title": "Knives Out", "year": 2019}
        dest = lm.build_movie_dest(Path("movie.mkv"), info, root=Path("/movies"))
        assert dest == Path("/movies/Knives Out (2019)/Knives Out (2019).mkv")

    def test_without_year(self):
        info = {"title": "Knives Out"}
        dest = lm.build_movie_dest(Path("movie.mkv"), info, root=Path("/movies"))
        assert dest == Path("/movies/Knives Out/Knives Out.mkv")

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
        info = guessit("King.of.the.Hill.S15E08.1080p.WEB.H264-CAKES.mkv")
        assert lm.guess_media_type(info, "") == "episode"
        dest = lm.build_tv_dest(Path("x.mkv"), info, root=Path("/tv"))
        assert dest == Path("/tv/King of the Hill/Season 15/King of the Hill - S15E08.mkv")

    def test_radarr_style_movie(self):
        info = guessit("Knives Out 2019 1080p BluRay HEVC x265 5.1 BONE.mkv")
        assert lm.guess_media_type(info, "") == "movie"
        dest = lm.build_movie_dest(Path("x.mkv"), info, root=Path("/movies"))
        assert dest == Path("/movies/Knives Out (2019)/Knives Out (2019).mkv")
