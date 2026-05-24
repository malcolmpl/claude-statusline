import sys, os, subprocess, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import cache_stats

FIX = os.path.join(os.path.dirname(__file__), "fixtures")
SCRIPT = os.path.join(os.path.dirname(__file__), "..", "scripts", "cache_stats.py")


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


class TestInitWindow(unittest.TestCase):
    def test_all_assistants_of_first_turn_are_init(self):
        r = cache_stats.analyze(os.path.join(FIX, "transcript_first_turn_with_tools.jsonl"))
        s = cache_stats.summarize(r)
        kinds = [t["kind"] for t in r["turns"]]
        self.assertEqual(kinds, ["init", "init"])
        self.assertEqual(s["init_total"], 25000 + 18000)

    def test_clear_resets_init_window(self):
        r = cache_stats.analyze(os.path.join(FIX, "transcript_clear_resets.jsonl"))
        s = cache_stats.summarize(r)
        kinds = [t["kind"] for t in r["turns"]]
        self.assertEqual(kinds, ["init", "normal", "init"])
        self.assertEqual(s["init_total"], 25000 + 30000)


class TestCli(unittest.TestCase):
    def test_missing_arg_exits_nonzero_with_usage(self):
        r = subprocess.run([sys.executable, SCRIPT], capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("usage", r.stderr.lower())

    def test_explicit_path_renders_to_stdout(self):
        fixture = os.path.join(FIX, "transcript_normal.jsonl")
        r = subprocess.run([sys.executable, SCRIPT, fixture], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)
        self.assertIn("Summary", r.stdout)
        self.assertIn("Total cc", r.stdout)


