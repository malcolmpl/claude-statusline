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


class TestSummary(unittest.TestCase):
    def test_ttl_classified(self):
        r = cache_stats.analyze(os.path.join(FIX, "transcript_ttl.jsonl"))
        s = cache_stats.summarize(r)
        self.assertEqual(s["ttl_count"], 1)
        self.assertEqual(s["init_total"], 25000)
        self.assertEqual(s["ttl_total"], 29000)

    def test_no_ttl_in_normal(self):
        r = cache_stats.analyze(os.path.join(FIX, "transcript_normal.jsonl"))
        s = cache_stats.summarize(r)
        self.assertEqual(s["ttl_count"], 0)

    def test_top3_spikes(self):
        r = cache_stats.analyze(os.path.join(FIX, "transcript_normal.jsonl"))
        s = cache_stats.summarize(r)
        self.assertEqual(len(s["top_spikes"]), 3)
        self.assertEqual(s["top_spikes"][0]["cc"], 25000)


class TestRender(unittest.TestCase):
    def test_render_contains_headers(self):
        r = cache_stats.analyze(os.path.join(FIX, "transcript_ttl.jsonl"))
        s = cache_stats.summarize(r)
        out = cache_stats.render(r, s)
        self.assertIn("Turn", out)
        self.assertIn("cc", out)
        self.assertIn("Summary", out)

    def test_render_marks_ttl(self):
        r = cache_stats.analyze(os.path.join(FIX, "transcript_ttl.jsonl"))
        s = cache_stats.summarize(r)
        out = cache_stats.render(r, s)
        self.assertIn("TTL!", out)

    def test_render_marks_init(self):
        r = cache_stats.analyze(os.path.join(FIX, "transcript_ttl.jsonl"))
        s = cache_stats.summarize(r)
        out = cache_stats.render(r, s)
        self.assertIn("init", out)
