"""Bounded-runtime safeguards (#3): stdin deadline + whole-run watchdog.

Subprocess-based: each test spawns the real script and kills it in cleanup.
"""
import json, os, shutil, subprocess, sys, tempfile, time, unittest

SCRIPTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts")
SCRIPT = os.path.join(SCRIPTS, "statusline.py")
sys.path.insert(0, SCRIPTS)
import statusline

MARGIN_S = 2.5  # interpreter startup + scheduling slack


class TestDeadline(unittest.TestCase):
    def setUp(self):
        self.state = tempfile.mkdtemp()  # reaper stamps stay out of ~/.claude
        self.addCleanup(shutil.rmtree, self.state, True)

    def spawn(self, args):
        env = dict(os.environ, CLAUDE_STATUSLINE_STATE_DIR=self.state)
        p = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        self.addCleanup(self.reap, p)
        return p

    @staticmethod
    def reap(p):
        if p.poll() is None:
            p.kill()
        p.communicate()

    def run_with(self, stdin_bytes):
        p = self.spawn([sys.executable, SCRIPT])
        out, _ = p.communicate(stdin_bytes, timeout=10)
        return p.returncode, out.decode("utf-8", "replace")

    def test_unclosed_stdin_exits_silently_within_deadline(self):
        p = self.spawn([sys.executable, SCRIPT])  # stdin pipe left open
        start = time.monotonic()
        p.wait(timeout=statusline.STDIN_TIMEOUT_S + MARGIN_S)
        self.assertLess(time.monotonic() - start, statusline.STDIN_TIMEOUT_S + MARGIN_S)
        self.assertEqual(p.stdout.read(), b"")

    def test_valid_payload_renders(self):
        payload = {"workspace": {"current_dir": "X:/deadline-probe"}, "model": {"display_name": "Opus"}}
        code, out = self.run_with(json.dumps(payload).encode())
        self.assertEqual(code, 0)
        self.assertIn("X:/deadline-probe", out)

    def test_empty_stdin_renders_fallback(self):
        code, out = self.run_with(b"")
        self.assertEqual(code, 0)
        self.assertIn("?", out)

    @unittest.skipUnless(sys.platform == "win32", "reaper is Windows-only")
    def test_run_reaps_suspended_leftover_after_output(self):
        fake = os.path.join(self.state, "scripts", "statusline.py")
        orphan = subprocess.Popen([sys.executable, fake], creationflags=0x4)  # CREATE_SUSPENDED
        self.addCleanup(lambda: (orphan.poll() is None and orphan.kill(), orphan.wait()))
        code = (
            f"import sys; sys.path.insert(0, {SCRIPTS!r}); import statusline as s, reaper; "
            f"reaper.REAP_AGE_S = 0; s.__file__ = {fake!r}; s.main()"
        )
        out, _ = self.spawn([sys.executable, "-c", code]).communicate(b"{}", timeout=10)
        self.assertIn(b"?", out)
        orphan.wait(timeout=5)
        self.assertTrue(any(n.startswith("reap-") for n in os.listdir(self.state)))

    def test_watchdog_fires_on_hang_after_stdin(self):
        watchdog = 0.5
        code = (
            f"import sys, time; sys.path.insert(0, {SCRIPTS!r}); import statusline as s; "
            f"s.WATCHDOG_S = {watchdog}; s.get_git_branch = lambda cwd: time.sleep(60); s.main()"
        )
        p = self.spawn([sys.executable, "-c", code])
        start = time.monotonic()
        out, _ = p.communicate(b"{}", timeout=watchdog + MARGIN_S)
        self.assertLess(time.monotonic() - start, watchdog + MARGIN_S)
        self.assertEqual(out, b"")


if __name__ == "__main__":
    unittest.main()
