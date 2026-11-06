"""Bounded-runtime safeguards (#3): stdin deadline + whole-run watchdog.

Subprocess-based: each test spawns the real script and kills it in cleanup.
"""
import json, os, subprocess, sys, time, unittest

SCRIPTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts")
SCRIPT = os.path.join(SCRIPTS, "statusline.py")
sys.path.insert(0, SCRIPTS)
import statusline

MARGIN_S = 2.5  # interpreter startup + scheduling slack


class TestDeadline(unittest.TestCase):
    def spawn(self, args):
        p = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
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
