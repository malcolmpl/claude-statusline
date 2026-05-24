import sys, os, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import render


class TestGaugeTracer(unittest.TestCase):
    def test_returns_bar_and_pct(self):
        s = render.render_gauge(42)
        self.assertIn("42%", s)
        self.assertIn("▰", s)
        self.assertIn("▱", s)


class TestGaugeLabel(unittest.TestCase):
    def test_label_prefix(self):
        s = render.render_gauge(42, label="session")
        self.assertIn("session: ", s)

    def test_no_label_no_colon(self):
        s = render.render_gauge(42)
        self.assertNotIn(": ", s)


class TestGaugeSuffix(unittest.TestCase):
    def test_suffix_is_dim(self):
        s = render.render_gauge(42, suffix="resets 2h")
        self.assertIn("resets 2h", s)
        # DIM (\033[2m) must appear immediately before the suffix
        self.assertIn("\033[2mresets 2h", s)

    def test_no_suffix_no_dim_tail(self):
        s = render.render_gauge(42)
        self.assertNotIn("resets", s)


class TestGaugeTail(unittest.TestCase):
    def test_tail_uses_bar_color_not_dim(self):
        # pct=50 → green (\033[32m). Tail must be preceded by green, not DIM.
        s = render.render_gauge(50, tail="125k / 200k")
        self.assertIn("125k / 200k", s)
        self.assertIn("\033[32m125k / 200k", s)
        self.assertNotIn("\033[2m125k", s)

    def test_tail_terminates_with_reset(self):
        # Color must not bleed into the following separator.
        s = render.render_gauge(50, tail="125k / 200k")
        self.assertTrue(s.endswith("\033[0m"))


class TestGaugeBlink(unittest.TestCase):
    def test_blinks_at_threshold(self):
        s = render.render_gauge(80)
        self.assertIn("\033[5m", s)

    def test_blinks_above_threshold(self):
        s = render.render_gauge(92, label="weekly", suffix="resets 3d")
        self.assertIn("\033[5m", s)

    def test_no_blink_below_threshold(self):
        s = render.render_gauge(79)
        self.assertNotIn("\033[5m", s)


class TestGaugePalette(unittest.TestCase):
    def test_green_below_60(self):
        self.assertIn("\033[32m", render.render_gauge(50))

    def test_yellow_60_to_70(self):
        self.assertIn("\033[33m", render.render_gauge(65))

    def test_orange_70_to_80(self):
        self.assertIn("\033[38;5;208m", render.render_gauge(75))

    def test_red_80_plus(self):
        self.assertIn("\033[31m", render.render_gauge(85))


if __name__ == "__main__":
    unittest.main()
