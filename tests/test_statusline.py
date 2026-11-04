import sys, os, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import statusline
import render
import transcript

FIX = os.path.join(os.path.dirname(__file__), "fixtures")


class TestCtx(unittest.TestCase):
    def test_tail_small_window_shows_max(self):
        self.assertEqual(statusline.ctx_tail(98432, 200000), "98,432 / 200,000")

    def test_tail_1m_window_used_only(self):
        self.assertEqual(statusline.ctx_tail(98432, 1000000), "98,432")
        self.assertEqual(statusline.ctx_tail(98432, 2000000), "98,432")

    def test_total_includes_cache_creation(self):
        cu = {"input_tokens": 10, "cache_read_input_tokens": 1000, "cache_creation_input_tokens": 500}
        self.assertEqual(statusline.ctx_used(cu), 1510)

    def test_total_missing_fields(self):
        self.assertEqual(statusline.ctx_used({"input_tokens": None}), 0)


class TestEffort(unittest.TestCase):
    def test_transcript_wins(self):
        self.assertEqual(statusline.pick_effort("high", {"effort": {"level": "low"}}), "high")

    def test_stdin_fallback(self):
        self.assertEqual(statusline.pick_effort(None, {"effort": {"level": "low"}}), "low")

    def test_neither(self):
        self.assertIsNone(statusline.pick_effort(None, {}))

    def test_model_segment_with_effort(self):
        self.assertEqual(render.render_model("Opus 5.5", "high"), f"{render.DIM}Opus 5.5 high{render.RESET}")

    def test_model_segment_without_effort(self):
        self.assertEqual(render.render_model("Opus 5.5", None), f"{render.DIM}Opus 5.5{render.RESET}")


class TestMainCc(unittest.TestCase):
    def test_heuristic_ttl_not_shown_without_prompt_cache(self):
        s = statusline.main_cc_segment(transcript.last_cc_turn(os.path.join(FIX, "transcript_ttl.jsonl")), None)
        self.assertNotIn("TTL", s)

    def test_cause_label_shown_on_match(self):
        s = statusline.main_cc_segment(transcript.last_cc_turn(os.path.join(FIX, "transcript_miss.jsonl")),
                                       {"last_miss_at": 1793786430, "last_miss_cause": {"causes": ["tools_changed"]}})
        self.assertIn("(rebuild!)", s)
        self.assertIn(render.RED, s)

    def test_no_turn(self):
        self.assertIsNone(statusline.main_cc_segment(None, None))

    def test_cause_label_hidden_on_no_match(self):
        s = statusline.main_cc_segment(transcript.last_cc_turn(os.path.join(FIX, "transcript_miss.jsonl")),
                                       {"last_miss_at": 1793786405, "last_miss_cause": {"causes": ["tools_changed"]}})
        self.assertNotIn("rebuild", s)


if __name__ == "__main__":
    unittest.main()
