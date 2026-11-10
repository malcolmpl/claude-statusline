# A later run reaps statusline processes left suspended by a killed launcher

On Windows, each statusline run reaches Python through launchers (MSYS `bash`, a `python3` shim) that create their child suspended and resume it a moment later. Claude Code cancels a superseded run by killing only the top of the chain. A kill inside the create-resume gap leaves a `python*.exe` that never runs a line of Python: 1 thread, suspended, parent dead, forever (#5). After every run, `scripts/reaper.py` does a throttled sweep that kills such leftovers.

## Why

- The stuck process never executes Python, so the stdin deadline and watchdog (#3) cannot fire, and it cannot write a PID file. The process list is the only place to find it.
- `setup.md` now writes the real interpreter (`sys.executable`) instead of `python3`, which removes the shim layer. The `bash` layer belongs to Claude Code and cannot be removed, so a reaper is still needed.
- Match rule: image `python*.exe`, a command line ending with this script's absolute path (case-, slash- and quote-insensitive), and an age of at least `REAP_AGE_S` (60 s). The watchdog bounds a healthy run to 5 s, so anything older is stuck by definition. Other python processes and younger runs are never touched.
- Throttle: one exclusive-create stamp per `INTERVAL_S` (300 s) window in the state dir, holding the claim time. Exactly one run across all sessions wins a window, and only if the previous claim is at least `INTERVAL_S` old.
- It stays stdlib-only ([ADR-0003](./0003-stdin-only-no-external-deps.md)): the Win32 calls go through `ctypes` (Toolhelp snapshot, `NtQueryInformationProcess` class 60 for the command line, `GetProcessTimes`, `TerminateProcess`). No PowerShell, `wmic` or helper process is spawned.

## Consequences

- The sweep runs after the statusline is printed and flushed. It costs about 20 ms, once per window.
- Leftovers are removed up to `INTERVAL_S` after they pass `REAP_AGE_S`, and only while some session keeps running the statusline.
- The sweep is Windows-only; other platforms skip it before touching the stamp file.
- The branch is now read from `.git/HEAD`, following `gitdir:` for worktrees and submodules, instead of spawning `git` twice. Runs are shorter, so fewer get cancelled mid-spawn. On detached HEAD the short SHA is always 7 characters, where `git rev-parse --short` may print more in very large repos.
