from health import Health


class FakeObserver:
    def __init__(self, alive=True):
        self._alive = alive

    def is_alive(self):
        return self._alive


class TestLiveness:
    def test_live_while_the_watcher_thread_is_alive(self):
        health = Health()
        health.track(FakeObserver(alive=True))
        assert health.live() == (True, "ok")

    def test_dead_watcher_thread_fails_liveness(self):
        health = Health()
        observer = FakeObserver(alive=True)
        health.track(observer)

        observer._alive = False

        ok, detail = health.live()
        assert not ok
        assert "not alive" in detail

    def test_stale_main_loop_fails_liveness(self):
        health = Health(stale_after=0)
        health.track(FakeObserver(alive=True))
        ok, detail = health.live()
        assert not ok
        assert "checked in" in detail

    def test_beat_refreshes_staleness(self):
        health = Health(stale_after=60)
        health.track(FakeObserver(alive=True))
        health.beat()
        assert health.live()[0]


class TestReadiness:
    def test_not_ready_until_the_initial_scan_finishes(self):
        health = Health()
        health.track(FakeObserver(alive=True))

        ok, detail = health.ready()
        assert not ok
        assert "initial scan" in detail

        health.mark_ready()
        assert health.ready() == (True, "ok")

    def test_ready_implies_live(self):
        health = Health()
        observer = FakeObserver(alive=True)
        health.track(observer)
        health.mark_ready()

        observer._alive = False

        assert not health.ready()[0]
