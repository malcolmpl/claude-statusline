import sys, os, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import statusline
from transcript import Kind


class TestRenderCc(unittest.TestCase):
    def test_small_gray(self):
        s = statusline.render_cc_segment(500, Kind.NORMAL)
        self.assertIn("cc:500", s)
        self.assertIn("\033[2m", s)

    def test_mid_yellow(self):
        s = statusline.render_cc_segment(7400, Kind.NORMAL)
        self.assertIn("cc:7.4k", s)
        self.assertIn("\033[33m", s)
        self.assertNotIn("⚠", s)

    def test_high_red_warn(self):
        s = statusline.render_cc_segment(15000, Kind.DATA_LOAD)
        self.assertIn("cc:15k", s)
        self.assertIn("\033[31m", s)
        self.assertIn("\033[1m", s)
        self.assertIn("⚠", s)

    def test_panic_inverse(self):
        s = statusline.render_cc_segment(74000, Kind.DATA_LOAD)
        self.assertIn("cc:74k", s)
        self.assertIn("\033[31m", s)
        self.assertIn("\033[7m", s)
        self.assertIn("‼", s)

    def test_first_turn_dim_no_label_no_icon(self):
        s = statusline.render_cc_segment(27000, Kind.FIRST_TURN)
        self.assertIn("cc:27k", s)
        self.assertNotIn("(init)", s)
        self.assertNotIn("TTL", s)
        self.assertIn("\033[2m", s)
        self.assertNotIn("\033[33m", s)
        self.assertNotIn("\033[31m", s)
        self.assertNotIn("⚠", s)
        self.assertNotIn("‼", s)


class TestRenderCcTtl(unittest.TestCase):
    def test_ttl_label_shown(self):
        s = statusline.render_cc_segment(74000, Kind.TTL_REFRESH)
        self.assertIn("(TTL!)", s)
        self.assertIn("\033[31m", s)
        self.assertNotIn("⚠", s)
        self.assertNotIn("‼", s)

    def test_no_ttl_default(self):
        s = statusline.render_cc_segment(7400, Kind.NORMAL)
        self.assertNotIn("TTL", s)


if __name__ == "__main__":
    unittest.main()
