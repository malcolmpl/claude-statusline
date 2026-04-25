import sys, os, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import cache_stats

FIX = os.path.join(os.path.dirname(__file__), "fixtures")


class TestAnalyze(unittest.TestCase):
    def test_normal_turns(self):
        r = cache_stats.analyze(os.path.join(FIX, "transcript_normal.jsonl"))
        self.assertEqual(len(r["turns"]), 3)
        self.assertEqual(r["turns"][0]["cc"], 25000)
        self.assertEqual(r["turns"][0]["cache_read"], 0)
        self.assertEqual(r["turns"][2]["cc"], 7400)

    def test_total_cc(self):
        r = cache_stats.analyze(os.path.join(FIX, "transcript_normal.jsonl"))
        self.assertEqual(r["total_cc"], 25000 + 1200 + 7400)

    def test_missing_file(self):
        r = cache_stats.analyze("/nope.jsonl")
        self.assertEqual(r["turns"], [])

    def test_none_path(self):
        r = cache_stats.analyze(None)
        self.assertEqual(r["turns"], [])
