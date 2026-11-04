import sys, os, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import transcript
from transcript import Kind, ClassifiedTurn

FIX = os.path.join(os.path.dirname(__file__), "fixtures")

# transcript_miss.jsonl: m1 response 10:00:05; prompt 10:00:10; m2 records 10:00:40..10:00:45.5
M1_AT = 1793786405
PROMPT_AT = 1793786410
M2_MID = 1793786430


def pc(at, causes):
    return {"last_miss_at": at, "last_miss_cause": {"causes": causes} if causes is not None else None}


class TestLatest(unittest.TestCase):
    def test_effort_from_last_assistant_record_even_cc_zero(self):
        lt = transcript.latest(os.path.join(FIX, "transcript_effort.jsonl"))
        self.assertEqual(lt.effort, "high")
        self.assertEqual(lt.cc_turn.cc, 25000)

    def test_effort_absent(self):
        lt = transcript.latest(os.path.join(FIX, "transcript_no_effort.jsonl"))
        self.assertIsNone(lt.effort)

    def test_missing_file(self):
        lt = transcript.latest(None)
        self.assertIsNone(lt.cc_turn)
        self.assertIsNone(lt.effort)

    def test_turn_window_starts_at_preceding_record(self):
        t = transcript.last_cc_turn(os.path.join(FIX, "transcript_miss.jsonl"))
        self.assertEqual(t.request_timestamp, "2026-11-04T10:00:10.000Z")
        self.assertEqual(t.timestamp, "2026-11-04T10:00:45.500Z")


class TestMissLabel(unittest.TestCase):
    def setUp(self):
        self.turn = transcript.last_cc_turn(os.path.join(FIX, "transcript_miss.jsonl"))

    def test_ttl(self):
        self.assertEqual(transcript.miss_label(pc(M2_MID, ["ttl_expired_5m"]), self.turn), "TTL!")
        self.assertEqual(transcript.miss_label(pc(M2_MID, ["ttl_expired_1h"]), self.turn), "TTL!")

    def test_rebuild(self):
        self.assertEqual(transcript.miss_label(pc(M2_MID, ["tools_changed"]), self.turn), "rebuild!")
        self.assertEqual(transcript.miss_label(pc(M2_MID, ["system_prompt_changed"]), self.turn), "rebuild!")

    def test_server(self):
        self.assertEqual(transcript.miss_label(pc(M2_MID, ["likely_server_side"]), self.turn), "srv?")

    def test_ttl_wins_over_rebuild(self):
        self.assertEqual(transcript.miss_label(pc(M2_MID, ["tools_changed", "ttl_expired_5m"]), self.turn), "TTL!")

    def test_match_at_request_time_and_after_last_record(self):
        self.assertEqual(transcript.miss_label(pc(PROMPT_AT, ["tools_changed"]), self.turn), "rebuild!")
        self.assertEqual(transcript.miss_label(pc(1793786447, ["tools_changed"]), self.turn), "rebuild!")

    def test_no_match_on_earlier_turn_persisted_cause(self):
        self.assertIsNone(transcript.miss_label(pc(M1_AT, ["tools_changed"]), self.turn))

    def test_no_match_far_future(self):
        self.assertIsNone(transcript.miss_label(pc(1793786500, ["tools_changed"]), self.turn))

    def test_unknown_cause_or_null(self):
        self.assertIsNone(transcript.miss_label(pc(M2_MID, ["something_new"]), self.turn))
        self.assertIsNone(transcript.miss_label(pc(M2_MID, None), self.turn))

    def test_absent_or_no_miss(self):
        self.assertIsNone(transcript.miss_label(None, self.turn))
        self.assertIsNone(transcript.miss_label({"last_miss_at": None}, self.turn))
        self.assertIsNone(transcript.miss_label(pc(M2_MID, ["tools_changed"]), None))


def mk(kind, pos=2, cc=3000):
    return ClassifiedTurn(cc=cc, cache_read=0, window_prompt_pos=pos, tool_name=None,
                          timestamp=None, kind=kind)


class TestMainSessionKind(unittest.TestCase):
    def test_ttl_demoted_to_normal(self):
        self.assertEqual(transcript.main_session_kind(mk(Kind.TTL_REFRESH)), Kind.NORMAL)

    def test_ttl_demoted_to_first_turn(self):
        self.assertEqual(transcript.main_session_kind(mk(Kind.TTL_REFRESH, pos=1)), Kind.FIRST_TURN)

    def test_ttl_demoted_to_data_load(self):
        self.assertEqual(transcript.main_session_kind(mk(Kind.TTL_REFRESH, cc=20000)), Kind.DATA_LOAD)

    def test_other_kinds_unchanged(self):
        self.assertEqual(transcript.main_session_kind(mk(Kind.FIRST_TURN, pos=1)), Kind.FIRST_TURN)


if __name__ == "__main__":
    unittest.main()
