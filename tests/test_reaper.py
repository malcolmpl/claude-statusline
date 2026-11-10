"""Reaper of suspended, orphaned statusline processes (#5).

Leftovers are reproduced with CREATE_SUSPENDED children whose command line
names a unique fake script path, so the user's live statusline is never hit.
Every child is killed in cleanup.
"""
import os, shutil, subprocess, sys, tempfile, time, unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import reaper

CREATE_SUSPENDED = 0x4
WIN = sys.platform == "win32"


class TestMatches(unittest.TestCase):
    KEY = "C:/Users/u/.claude/plugins/marketplaces/m/scripts/statusline.py"

    def test_forward_slash_config(self):
        self.assertTrue(reaper.matches(f"python3  {self.KEY}", self.KEY))

    def test_backslash_quoted_case(self):
        cmd = r'C:\py\python.exe "c:\users\U\.claude\plugins\marketplaces\m\scripts\statusline.py"'
        self.assertTrue(reaper.matches(cmd, self.KEY))

    def test_other_script(self):
        self.assertFalse(reaper.matches("python C:/x/scripts/statusline.py", self.KEY))
        self.assertFalse(reaper.matches(f"python {self.KEY[:-3]}_old.py", self.KEY))
        self.assertFalse(reaper.matches("python -c pass", self.KEY))
        self.assertFalse(reaper.matches(None, self.KEY))


class TestClaim(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)

    def test_one_claim_per_window(self):
        self.assertTrue(reaper.claim(self.dir, now=1000.0, interval=300))
        self.assertFalse(reaper.claim(self.dir, now=1100.0, interval=300))
        self.assertTrue(reaper.claim(self.dir, now=1300.0, interval=300))

    def test_old_stamps_removed(self):
        reaper.claim(self.dir, now=1000.0, interval=300)
        reaper.claim(self.dir, now=1300.0, interval=300)
        self.assertEqual(os.listdir(self.dir), ["reap-4.stamp"])

    def test_no_second_claim_across_window_boundary(self):
        self.assertTrue(reaper.claim(self.dir, now=1290.0, interval=300))
        self.assertFalse(reaper.claim(self.dir, now=1310.0, interval=300))
        self.assertTrue(reaper.claim(self.dir, now=1590.0, interval=300))

    def test_late_run_on_older_window_loses(self):
        self.assertTrue(reaper.claim(self.dir, now=1300.0, interval=300))
        self.assertFalse(reaper.claim(self.dir, now=1299.0, interval=300))
        self.assertEqual(os.listdir(self.dir), ["reap-4.stamp"])

    def test_missing_dir_created(self):
        self.assertTrue(reaper.claim(os.path.join(self.dir, "a", "b"), now=1.0, interval=300))


@unittest.skipUnless(WIN, "reaper is Windows-only")
class TestReap(unittest.TestCase):
    def setUp(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        self.key = os.path.join(d, "scripts", "statusline.py")  # never exists; child never runs

    def suspended(self, *args):
        p = subprocess.Popen([sys.executable, *args], creationflags=CREATE_SUSPENDED)
        self.addCleanup(self.kill, p)
        return p

    @staticmethod
    def kill(p):
        if p.poll() is None:
            p.kill()
        p.wait()

    def test_suspended_leftover_reaped(self):
        p = self.suspended(self.key)
        self.assertIn(p.pid, reaper.reap(self.key, max_age_s=0))
        p.wait(timeout=5)

    def test_young_process_kept(self):
        p = self.suspended(self.key)
        self.assertNotIn(p.pid, reaper.reap(self.key, max_age_s=60))
        self.assertIsNone(p.poll())

    def test_other_path_kept(self):
        other = self.suspended(self.key + "x")
        plain = self.suspended("-c", "pass")
        killed = reaper.reap(self.key, max_age_s=0)
        self.assertNotIn(other.pid, killed)
        self.assertNotIn(plain.pid, killed)
        self.assertIsNone(other.poll())
        self.assertIsNone(plain.poll())

    def test_age_measured(self):
        p = self.suspended(self.key)
        time.sleep(1.2)
        self.assertIn(p.pid, reaper.reap(self.key, max_age_s=1))


class TestRun(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)

    def test_throttled_second_run_skips(self):
        calls = []
        reap = lambda *a, **k: calls.append(a) or []
        reaper.run("k", self.dir, now=1000.0, reap_fn=reap, platform="win32")
        reaper.run("k", self.dir, now=1001.0, reap_fn=reap, platform="win32")
        self.assertEqual(len(calls), 1)

    def test_non_windows_skips(self):
        calls = []
        reaper.run("k", self.dir, now=1000.0, reap_fn=lambda *a, **k: calls.append(a), platform="linux")
        self.assertEqual(calls, [])
        self.assertEqual(os.listdir(self.dir), [])

    def test_errors_swallowed(self):
        def boom(*a, **k):
            raise OSError("x")
        reaper.run("k", self.dir, now=1000.0, reap_fn=boom, platform="win32")


if __name__ == "__main__":
    unittest.main()
