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


if __name__ == "__main__":
    unittest.main()
