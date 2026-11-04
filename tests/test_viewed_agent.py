import json
import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import render
import statusline
import transcript
import viewed_agent

FIX = os.path.join(os.path.dirname(__file__), "fixtures")
SUB = os.path.join(FIX, "subagent_explore.jsonl")
SID = "sess-1"


def write_state(state_dir, session_id=SID, **fields):
    path = os.path.join(state_dir, f"viewed-agent-{session_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(fields, f)
    return path


class TestModelName(unittest.TestCase):
    def test_family_major_minor(self):
        self.assertEqual(viewed_agent.model_name("claude-sonnet-5-5"), "Sonnet 5.5")
        self.assertEqual(viewed_agent.model_name("claude-haiku-4-5"), "Haiku 4.5")

    def test_date_suffix_dropped(self):
        self.assertEqual(viewed_agent.model_name("claude-haiku-4-5-20251001"), "Haiku 4.5")

    def test_date_never_read_as_minor(self):
        self.assertEqual(viewed_agent.model_name("claude-sonnet-4-20250514"), "claude-sonnet-4-20250514")

    def test_raw_id_otherwise(self):
        self.assertEqual(viewed_agent.model_name("claude-opus-5"), "claude-opus-5")
        self.assertEqual(viewed_agent.model_name("claude-3-5-sonnet-20241022"), "claude-3-5-sonnet-20241022")
        self.assertEqual(viewed_agent.model_name("gpt-x"), "gpt-x")

    def test_none(self):
        self.assertIsNone(viewed_agent.model_name(None))


class TestContextWindow(unittest.TestCase):
    def test_known(self):
        self.assertEqual(viewed_agent.context_window("claude-sonnet-5-5"), 1_000_000)
        self.assertEqual(viewed_agent.context_window("claude-haiku-4-5"), 200_000)

    def test_known_with_date_suffix(self):
        self.assertEqual(viewed_agent.context_window("claude-haiku-4-5-20251001"), 200_000)

    def test_unknown(self):
        self.assertIsNone(viewed_agent.context_window("claude-foo-9-9"))
        self.assertIsNone(viewed_agent.context_window(None))


class TestStateDir(unittest.TestCase):
    def test_env_override(self):
        self.assertEqual(viewed_agent.state_dir({"CLAUDE_STATUSLINE_STATE_DIR": "/x"}), "/x")

    def test_default_under_home(self):
        d = viewed_agent.state_dir({})
        self.assertTrue(d.endswith(os.path.join(".claude", "claude-statusline")))


class TestReadState(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_subagent(self):
        write_state(self.dir, agentId="a1", transcriptPath=SUB, agentType="Explore",
                    model="sonnet", effort="low")
        a = viewed_agent.read_state(SID, self.dir)
        self.assertEqual(a.agent_id, "a1")
        self.assertEqual(a.transcript_path, SUB)
        self.assertEqual(a.agent_type, "Explore")
        self.assertEqual(a.effort, "low")

    def test_main_empty_agent_id(self):
        write_state(self.dir, agentId="", transcriptPath="")
        self.assertIsNone(viewed_agent.read_state(SID, self.dir))

    def test_missing_file(self):
        self.assertIsNone(viewed_agent.read_state(SID, self.dir))

    def test_no_session_id(self):
        self.assertIsNone(viewed_agent.read_state(None, self.dir))

    def test_unreadable(self):
        with open(os.path.join(self.dir, f"viewed-agent-{SID}.json"), "w") as f:
            f.write("{not json")
        self.assertIsNone(viewed_agent.read_state(SID, self.dir))

    def test_not_an_object(self):
        with open(os.path.join(self.dir, f"viewed-agent-{SID}.json"), "w") as f:
            f.write("[1, 2]")
        self.assertIsNone(viewed_agent.read_state(SID, self.dir))

    def test_stale_transcript_gone(self):
        # Stale = the state names a subagent whose transcript no longer exists.
        write_state(self.dir, agentId="a1", transcriptPath=os.path.join(self.dir, "gone.jsonl"))
        self.assertIsNone(viewed_agent.read_state(SID, self.dir))

    def test_old_state_still_shown(self):
        # Age alone is not stale: the mod writes only on a view switch, so a
        # long-viewed (or finished) subagent keeps an old file.
        p = write_state(self.dir, agentId="a1", transcriptPath=SUB)
        old = time.time() - 30 * 86400
        os.utime(p, (old, old))
        self.assertIsNotNone(viewed_agent.read_state(SID, self.dir))

    def test_numeric_effort_stringified(self):
        write_state(self.dir, agentId="a1", transcriptPath=SUB, effort=32000)
        self.assertEqual(viewed_agent.read_state(SID, self.dir).effort, "32000")

    def test_other_session_ignored(self):
        write_state(self.dir, session_id="other", agentId="a1", transcriptPath=SUB)
        self.assertIsNone(viewed_agent.read_state(SID, self.dir))


class TestTurnsCtxFields(unittest.TestCase):
    def test_last_turn_has_input_and_model(self):
        t = transcript.latest(SUB).last_turn
        self.assertEqual(t.input_tokens, 3)
        self.assertEqual(t.model, "claude-sonnet-5-5")
        self.assertEqual(t.cc, 0)

    def test_cc_turn_is_last_with_cc(self):
        self.assertEqual(transcript.latest(SUB).cc_turn.cc, 1200)


class TestSubagentSegments(unittest.TestCase):
    def agent(self, **kw):
        base = dict(agent_id="a1", transcript_path=SUB, agent_type="Explore", model=None, effort=None)
        base.update(kw)
        return viewed_agent.ViewedAgent(**base)

    def test_model_prefix_and_effort_from_record(self):
        seg = statusline.subagent_segments(self.agent(effort="low"))
        self.assertEqual(seg.model, render.render_model("Sonnet 5.5", "medium", prefix="↳Explore"))

    def test_effort_from_meta_when_record_has_none(self):
        a = self.agent(transcript_path=os.path.join(FIX, "subagent_no_effort.jsonl"), effort="low")
        seg = statusline.subagent_segments(a)
        self.assertIn("Haiku 4.5 low", seg.model)

    def test_effort_omitted_never_stdin(self):
        a = self.agent(transcript_path=os.path.join(FIX, "subagent_no_effort.jsonl"))
        seg = statusline.subagent_segments(a)
        self.assertEqual(seg.model, render.render_model("Haiku 4.5", None, prefix="↳Explore"))

    def test_ctx_last_turn_total(self):
        # last Turn: input 3 + cache_read 24000 + cache_creation 0 (cc=0 Turn counts)
        seg = statusline.subagent_segments(self.agent())
        self.assertEqual(seg.ctx, render.render_gauge(24003 / 1_000_000 * 100, label="ctx",
                                                      tail=statusline.ctx_tail(24003, 1_000_000)))

    def test_ctx_unknown_window_count_only(self):
        a = self.agent(transcript_path=os.path.join(FIX, "subagent_unknown_model.jsonl"))
        seg = statusline.subagent_segments(a)
        self.assertEqual(seg.ctx, render.render_count("12,310", label="ctx"))
        self.assertNotIn("%", seg.ctx)
        self.assertNotIn("▱", seg.ctx)
        self.assertIn("Foo 9.9", seg.model)

    def test_cc_uses_heuristic_kind(self):
        seg = statusline.subagent_segments(self.agent(transcript_path=os.path.join(FIX, "transcript_ttl.jsonl")))
        self.assertIn("(TTL!)", seg.cc)

    def test_cc_plain(self):
        seg = statusline.subagent_segments(self.agent())
        self.assertEqual(seg.cc, render.render_cc_segment(1200, transcript.Kind.FIRST_TURN))

    def test_no_turns_yet(self):
        a = self.agent(transcript_path=os.path.join(FIX, "transcript_empty.jsonl"), model="sonnet")
        seg = statusline.subagent_segments(a)
        self.assertIn("↳Explore", seg.model)
        self.assertIn("sonnet", seg.model)
        self.assertIsNone(seg.cc)


class TestViewSegments(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name
        self.data = {"session_id": SID, "model": {"display_name": "Opus 5.5"},
                     "effort": {"level": "xhigh"},
                     "transcript_path": os.path.join(FIX, "transcript_normal.jsonl"),
                     "context_window": {"context_window_size": 200000,
                                        "current_usage": {"input_tokens": 10}}}

    def tearDown(self):
        self._tmp.cleanup()

    def test_subagent_in_view(self):
        write_state(self.dir, agentId="a1", transcriptPath=SUB, agentType="Explore")
        seg = statusline.view_segments(self.data, self.dir)
        self.assertIn("↳Explore Sonnet 5.5 medium", seg.model)
        self.assertNotIn("xhigh", seg.model)

    def test_main_transcript_not_parsed_while_subagent_in_view(self):
        write_state(self.dir, agentId="a1", transcriptPath=SUB, agentType="Explore")
        seen = []
        orig = statusline.latest
        statusline.latest = lambda p: seen.append(p) or orig(p)
        try:
            statusline.view_segments(self.data, self.dir)
        finally:
            statusline.latest = orig
        self.assertEqual(seen, [SUB])

    def test_main_when_no_state(self):
        seg = statusline.view_segments(self.data, self.dir)
        self.assertNotIn("↳", seg.model)
        self.assertIn("Opus 5.5", seg.model)

    def test_main_when_state_says_main(self):
        write_state(self.dir, agentId="", transcriptPath="")
        self.assertNotIn("↳", statusline.view_segments(self.data, self.dir).model)


class TestRender(unittest.TestCase):
    def test_model_prefix(self):
        self.assertEqual(render.render_model("Sonnet 5.5", "low", prefix="↳Explore"),
                         f"{render.DIM}↳Explore Sonnet 5.5 low{render.RESET}")

    def test_count(self):
        self.assertEqual(render.render_count("1,234", label="ctx"),
                         f"{render.DIM}ctx:{render.RESET} 1,234")


if __name__ == "__main__":
    unittest.main()
