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


if __name__ == "__main__":
    unittest.main()
