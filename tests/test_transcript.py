import sys, os, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import transcript
from transcript import Kind

FIX = os.path.join(os.path.dirname(__file__), "fixtures")


class TestFmtK(unittest.TestCase):
    def test_under_1k(self):
        self.assertEqual(transcript.fmt_k(500), "500")

    def test_thousands_one_decimal(self):
        self.assertEqual(transcript.fmt_k(1200), "1.2k")
        self.assertEqual(transcript.fmt_k(7400), "7.4k")

    def test_ten_thousand_no_decimal(self):
        self.assertEqual(transcript.fmt_k(15000), "15k")

    def test_zero(self):
        self.assertEqual(transcript.fmt_k(0), "0")


class TestIsRealPrompt(unittest.TestCase):
    def test_plain_string_is_real(self):
        self.assertTrue(transcript._is_real_prompt({"type": "user", "message": {"content": "hi"}}))

    def test_caveat_not_real(self):
        self.assertFalse(transcript._is_real_prompt(
            {"type": "user", "message": {"content": "<local-command-caveat>foo"}}))

    def test_command_name_not_real(self):
        self.assertFalse(transcript._is_real_prompt(
            {"type": "user", "message": {"content": "<command-name>/clear</command-name>"}}))

    def test_system_reminder_not_real(self):
        self.assertFalse(transcript._is_real_prompt(
            {"type": "user", "message": {"content": "<system-reminder>x</system-reminder>"}}))

    def test_tool_result_list_not_real(self):
        self.assertFalse(transcript._is_real_prompt(
            {"type": "user", "message": {"content": [{"type": "tool_result", "content": "x"}]}}))

    def test_non_user_type_not_real(self):
        self.assertFalse(transcript._is_real_prompt({"type": "assistant", "message": {}}))


class TestLastCcTurn(unittest.TestCase):
    def test_normal(self):
        t = transcript.last_cc_turn(os.path.join(FIX, "transcript_normal.jsonl"))
        self.assertIsNotNone(t)
        self.assertEqual(t.cc, 7400)
        self.assertNotEqual(t.kind, Kind.FIRST_TURN)

    def test_init_only(self):
        t = transcript.last_cc_turn(os.path.join(FIX, "transcript_init.jsonl"))
        self.assertIsNotNone(t)
        self.assertEqual(t.cc, 27000)
        self.assertEqual(t.kind, Kind.FIRST_TURN)

    def test_empty_no_assistant(self):
        self.assertIsNone(transcript.last_cc_turn(os.path.join(FIX, "transcript_empty.jsonl")))

    def test_missing_file(self):
        self.assertIsNone(transcript.last_cc_turn(os.path.join(FIX, "does_not_exist.jsonl")))

    def test_none_path(self):
        self.assertIsNone(transcript.last_cc_turn(None))

    def test_high_cc(self):
        t = transcript.last_cc_turn(os.path.join(FIX, "transcript_high.jsonl"))
        self.assertEqual(t.cc, 74000)
        self.assertEqual(t.kind, Kind.DATA_LOAD)

    def test_corrupted_tail_skipped(self):
        t = transcript.last_cc_turn(os.path.join(FIX, "transcript_corrupted.jsonl"))
        self.assertIsNotNone(t)
        self.assertEqual(t.cc, 3000)


class TestClassify(unittest.TestCase):
    def test_ttl_match(self):
        self.assertEqual(transcript._classify(cc=29000, prev_cache_read=25000, window_prompt_pos=3), Kind.TTL_REFRESH)

    def test_below_ratio_not_ttl(self):
        self.assertNotEqual(transcript._classify(cc=10000, prev_cache_read=50000, window_prompt_pos=2), Kind.TTL_REFRESH)

    def test_low_prev_not_ttl(self):
        self.assertNotEqual(transcript._classify(cc=4500, prev_cache_read=4000, window_prompt_pos=2), Kind.TTL_REFRESH)

    def test_zero_prev_first_turn(self):
        # cc=27k at pos=1 with prev=0 → FIRST_TURN (TTL guard fails)
        self.assertEqual(transcript._classify(cc=27000, prev_cache_read=0, window_prompt_pos=1), Kind.FIRST_TURN)

    def test_ttl_beats_first_turn(self):
        # ADR-0004: TTL fires independently inside the first turn.
        self.assertEqual(transcript._classify(cc=30000, prev_cache_read=25000, window_prompt_pos=1), Kind.TTL_REFRESH)

    def test_data_load(self):
        self.assertEqual(transcript._classify(cc=15000, prev_cache_read=100, window_prompt_pos=2), Kind.DATA_LOAD)

    def test_normal_small(self):
        self.assertEqual(transcript._classify(cc=500, prev_cache_read=0, window_prompt_pos=2), Kind.NORMAL)


class TestFirstTurnWindow(unittest.TestCase):
    def test_tool_result_keeps_first_turn(self):
        t = transcript.last_cc_turn(os.path.join(FIX, "transcript_first_turn_with_tools.jsonl"))
        self.assertIsNotNone(t)
        self.assertEqual(t.cc, 18000)
        self.assertEqual(t.kind, Kind.FIRST_TURN)

    def test_clear_resets_window(self):
        # After /clear the next turn has pos=1 again. With prev_cr=25k carried over,
        # cc=30k crosses TTL ratio — ADR-0004 says TTL wins.
        t = transcript.last_cc_turn(os.path.join(FIX, "transcript_clear_resets.jsonl"))
        self.assertIsNotNone(t)
        self.assertEqual(t.cc, 30000)
        self.assertEqual(t.kind, Kind.TTL_REFRESH)

    def test_caveat_does_not_count_as_prompt(self):
        t = transcript.last_cc_turn(os.path.join(FIX, "transcript_caveat_first.jsonl"))
        self.assertIsNotNone(t)
        self.assertEqual(t.kind, Kind.FIRST_TURN)


class TestDuplicateRecords(unittest.TestCase):
    """Claude Code splits one assistant API call across multiple JSONL records
    (one per content block), all sharing the same message.id and repeating the
    same usage. The walker must count each Turn once."""

    def test_one_turn_per_message_id(self):
        ts = list(transcript.turns(os.path.join(FIX, "transcript_dup_records.jsonl")))
        self.assertEqual(len(ts), 1)

    def test_tool_name_from_last_record(self):
        # Fixture has [thinking, tool_use:Read] under one msg.id. Emitting the
        # first record would give tool_name=None; we want the tool_use block.
        ts = list(transcript.turns(os.path.join(FIX, "transcript_dup_records.jsonl")))
        self.assertEqual(ts[0].tool_name, "Read")

    def test_no_false_ttl_from_duplicate_records(self):
        # Without dedup, record 2 sees prev_cr=22639 from record 1 and trips
        # the 0.8 ratio (21733/22639 = 0.96). Dedup must prevent that.
        ts = list(transcript.turns(os.path.join(FIX, "transcript_dup_records.jsonl")))
        self.assertNotEqual(ts[0].kind, Kind.TTL_REFRESH)


if __name__ == "__main__":
    unittest.main()
