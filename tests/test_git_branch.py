"""Branch from .git/HEAD without spawning git (#5)."""
import os, subprocess, sys, tempfile, unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import statusline

SHA = "0123456789abcdef0123456789abcdef01234567"


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as f:
        f.write(text)


class TestGitBranch(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(__import__("shutil").rmtree, self.root, True)
        no_spawn = mock.patch.object(subprocess, "Popen", side_effect=AssertionError("git spawned"))
        no_spawn.start()
        self.addCleanup(no_spawn.stop)

    def repo(self, head):
        repo = os.path.join(self.root, "repo")
        write(os.path.join(repo, ".git", "HEAD"), head)
        return repo

    def test_branch_from_head(self):
        self.assertEqual(statusline.get_git_branch(self.repo("ref: refs/heads/master\n")), "master")

    def test_branch_with_slash_and_crlf(self):
        self.assertEqual(statusline.get_git_branch(self.repo("ref: refs/heads/fix/5-x\r\n")), "fix/5-x")

    def test_non_branch_ref_shortened(self):
        self.assertEqual(statusline.get_git_branch(self.repo("ref: refs/remotes/origin/x\n")), "origin/x")

    def test_reftable_placeholder_hidden(self):
        self.assertIsNone(statusline.get_git_branch(self.repo("ref: refs/heads/.invalid\n")))

    def test_subdirectory_walks_up(self):
        sub = os.path.join(self.repo("ref: refs/heads/dev\n"), "a", "b")
        os.makedirs(sub)
        self.assertEqual(statusline.get_git_branch(sub), "dev")

    def test_detached_head_short_sha(self):
        self.assertEqual(statusline.get_git_branch(self.repo(SHA + "\n")), SHA[:7])

    def test_worktree_gitdir_file_absolute(self):
        wt_git = os.path.join(self.repo("ref: refs/heads/master\n"), ".git", "worktrees", "wt")
        write(os.path.join(wt_git, "HEAD"), "ref: refs/heads/feature\n")
        wt = os.path.join(self.root, "wt")
        write(os.path.join(wt, ".git"), f"gitdir: {wt_git.replace(os.sep, '/')}\n")
        self.assertEqual(statusline.get_git_branch(wt), "feature")

    def test_gitdir_file_relative(self):
        # submodule layout: <super>/sub/.git -> ../.git/modules/sub
        sup = self.repo("ref: refs/heads/master\n")
        write(os.path.join(sup, ".git", "modules", "sub", "HEAD"), SHA + "\n")
        write(os.path.join(sup, "sub", ".git"), "gitdir: ../.git/modules/sub\n")
        self.assertEqual(statusline.get_git_branch(os.path.join(sup, "sub")), SHA[:7])

    def test_no_repo(self):
        plain = os.path.join(self.root, "plain")
        os.makedirs(plain)
        self.assertIsNone(statusline.get_git_branch(plain))  # temp dir is outside any repo

    def test_empty_cwd(self):
        self.assertIsNone(statusline.get_git_branch(""))

    def test_garbage_head(self):
        self.assertIsNone(statusline.get_git_branch(self.repo("not a ref\n")))


if __name__ == "__main__":
    unittest.main()
