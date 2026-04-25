import sys, os, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import statusline


class TestFmtK(unittest.TestCase):
    def test_under_1k(self):
        self.assertEqual(statusline.fmt_k(500), "500")

    def test_thousands_one_decimal(self):
        self.assertEqual(statusline.fmt_k(1200), "1.2k")
        self.assertEqual(statusline.fmt_k(7400), "7.4k")

    def test_ten_thousand_no_decimal(self):
        self.assertEqual(statusline.fmt_k(15000), "15k")
        self.assertEqual(statusline.fmt_k(74321), "74k")

    def test_zero(self):
        self.assertEqual(statusline.fmt_k(0), "0")


FIX = os.path.join(os.path.dirname(__file__), "fixtures")


class TestReadLastCc(unittest.TestCase):
    def test_normal(self):
        r = statusline.read_last_cc(os.path.join(FIX, "transcript_normal.jsonl"))
        self.assertTrue(r["found"])
        self.assertEqual(r["cc"], 7400)
        self.assertFalse(r["is_first_turn"])

    def test_init_only(self):
        r = statusline.read_last_cc(os.path.join(FIX, "transcript_init.jsonl"))
        self.assertTrue(r["found"])
        self.assertEqual(r["cc"], 27000)
        self.assertTrue(r["is_first_turn"])

    def test_empty_no_assistant(self):
        r = statusline.read_last_cc(os.path.join(FIX, "transcript_empty.jsonl"))
        self.assertFalse(r["found"])

    def test_missing_file(self):
        r = statusline.read_last_cc(os.path.join(FIX, "does_not_exist.jsonl"))
        self.assertFalse(r["found"])

    def test_none_path(self):
        r = statusline.read_last_cc(None)
        self.assertFalse(r["found"])


class TestRenderCc(unittest.TestCase):
    def test_small_gray(self):
        s = statusline.render_cc_segment(500, False)
        self.assertIn("cc:500", s)
        self.assertIn("\033[2m", s)

    def test_mid_yellow(self):
        s = statusline.render_cc_segment(7400, False)
        self.assertIn("cc:7.4k", s)
        self.assertIn("\033[33m", s)
        self.assertNotIn("⚠", s)

    def test_high_red_warn(self):
        s = statusline.render_cc_segment(15000, False)
        self.assertIn("cc:15k", s)
        self.assertIn("\033[31m", s)
        self.assertIn("\033[1m", s)
        self.assertIn("⚠", s)

    def test_panic_inverse(self):
        s = statusline.render_cc_segment(74000, False)
        self.assertIn("cc:74k", s)
        self.assertIn("\033[31m", s)
        self.assertIn("\033[7m", s)
        self.assertIn("‼", s)

    def test_init_forces_yellow(self):
        s = statusline.render_cc_segment(27000, True)
        self.assertIn("cc:27k", s)
        self.assertIn("(init)", s)
        self.assertIn("\033[33m", s)
        self.assertNotIn("⚠", s)
        self.assertNotIn("‼", s)


class TestEdgeCases(unittest.TestCase):
    def test_high_cc(self):
        r = statusline.read_last_cc(os.path.join(FIX, "transcript_high.jsonl"))
        self.assertEqual(r["cc"], 74000)
        self.assertFalse(r["is_first_turn"])

    def test_corrupted_tail_skipped(self):
        r = statusline.read_last_cc(os.path.join(FIX, "transcript_corrupted.jsonl"))
        self.assertTrue(r["found"])
        self.assertEqual(r["cc"], 3000)


if __name__ == "__main__":
    unittest.main()
