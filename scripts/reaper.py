"""Reap statusline processes left suspended by a launcher killed mid-spawn (#5, ADR-0010).

On Windows, MSYS `bash` and the scoop shim create their child suspended and
resume it a moment later. When Claude Code kills the launcher in between, the
child never runs Python and stays suspended forever. It cannot clean itself
up, so a later run does it: once per throttle window, kill `python*.exe`
processes whose command line names this script and that are older than the
reap age. The watchdog bounds a healthy run to 5 s, so anything older than
REAP_AGE_S is stuck by definition.

Windows-only; stdlib only (ctypes, ADR-0003).
"""
import os
import sys
import time

REAP_AGE_S = 60
INTERVAL_S = 300
STAMP_PREFIX = "reap-"


def _norm(s):
    return s.replace("\\", "/").replace('"', "").lower()


def matches(cmdline, script_path):
    """True when cmdline names script_path (slash, quote and case-insensitive)."""
    if not cmdline:
        return False
    cmd = _norm(cmdline).rstrip()
    key = _norm(script_path)
    return cmd.endswith(" " + key) or cmd == key


def claim(state_dir, now=None, interval=INTERVAL_S):
    """Claim a reap: at most one winner per `interval`, across sessions.

    `reap-<int(now // interval)>.stamp` is created exclusively (one winner per
    window) and holds the claim time. The previous claim must be at least
    `interval` old, so two windows cannot reap seconds apart. A late run still
    on an older window loses once a newer stamp exists; only older stamps are
    deleted.
    """
    now = time.time() if now is None else now
    window = int(now // interval)
    os.makedirs(state_dir, exist_ok=True)
    stamps = {}
    for name in os.listdir(state_dir):
        num = name[len(STAMP_PREFIX):-len(".stamp")]
        if name.startswith(STAMP_PREFIX) and name.endswith(".stamp") and num.isdigit():
            stamps[int(num)] = name
    if any(w >= window for w in stamps):
        return False
    if stamps:
        try:
            with open(os.path.join(state_dir, stamps[max(stamps)]), encoding="ascii") as f:
                last = float(f.read())
        except (OSError, ValueError):
            last = None  # unreadable older stamp: fall back to the window rule
        if last is not None and now - last < interval:
            return False
    try:
        path = os.path.join(state_dir, f"{STAMP_PREFIX}{window}.stamp")
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    with os.fdopen(fd, "w", encoding="ascii") as f:
        f.write(repr(now))
    for name in stamps.values():
        try:
            os.remove(os.path.join(state_dir, name))
        except OSError:
            pass
    return True


def reap(script_path, max_age_s=None):
    """Kill python processes running script_path older than max_age_s. Returns killed PIDs."""
    max_age_s = REAP_AGE_S if max_age_s is None else max_age_s
    import ctypes
    from ctypes import wintypes as w

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    ntdll = ctypes.WinDLL("ntdll")

    TH32CS_SNAPPROCESS = 0x2
    PROCESS_TERMINATE = 0x1
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    ProcessCommandLineInformation = 60
    INVALID_HANDLE = ctypes.c_void_p(-1).value

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [("dwSize", w.DWORD), ("cntUsage", w.DWORD), ("th32ProcessID", w.DWORD),
                    ("th32DefaultHeapID", ctypes.c_void_p), ("th32ModuleID", w.DWORD),
                    ("cntThreads", w.DWORD), ("th32ParentProcessID", w.DWORD),
                    ("pcPriClassBase", ctypes.c_long), ("dwFlags", w.DWORD),
                    ("szExeFile", ctypes.c_wchar * 260)]

    class UNICODE_STRING(ctypes.Structure):
        _fields_ = [("Length", ctypes.c_ushort), ("MaximumLength", ctypes.c_ushort),
                    ("Buffer", ctypes.c_void_p)]

    k32.CreateToolhelp32Snapshot.restype = ctypes.c_void_p
    k32.CreateToolhelp32Snapshot.argtypes = [w.DWORD, w.DWORD]
    k32.Process32FirstW.argtypes = [ctypes.c_void_p, ctypes.POINTER(PROCESSENTRY32W)]
    k32.Process32NextW.argtypes = [ctypes.c_void_p, ctypes.POINTER(PROCESSENTRY32W)]
    k32.OpenProcess.restype = ctypes.c_void_p
    k32.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
    k32.CloseHandle.argtypes = [ctypes.c_void_p]
    k32.TerminateProcess.argtypes = [ctypes.c_void_p, w.UINT]
    k32.GetProcessTimes.argtypes = [ctypes.c_void_p] + [ctypes.POINTER(w.FILETIME)] * 4
    k32.GetSystemTimeAsFileTime.argtypes = [ctypes.POINTER(w.FILETIME)]
    ntdll.NtQueryInformationProcess.restype = ctypes.c_long
    ntdll.NtQueryInformationProcess.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_void_p,
                                                ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong)]

    def ft(f):
        return (f.dwHighDateTime << 32) | f.dwLowDateTime  # 100 ns ticks

    def cmdline(h):
        size = ctypes.c_ulong(0)
        ntdll.NtQueryInformationProcess(h, ProcessCommandLineInformation, None, 0, ctypes.byref(size))
        if not size.value:
            return None
        buf = ctypes.create_string_buffer(size.value)
        if ntdll.NtQueryInformationProcess(h, ProcessCommandLineInformation, buf, size,
                                           ctypes.byref(size)) != 0:
            return None
        us = UNICODE_STRING.from_buffer(buf)
        return ctypes.wstring_at(us.Buffer, us.Length // 2) if us.Buffer else None

    def age_s(h, now_ticks):
        created, t1, t2, t3 = w.FILETIME(), w.FILETIME(), w.FILETIME(), w.FILETIME()
        if not k32.GetProcessTimes(h, ctypes.byref(created), ctypes.byref(t1),
                                   ctypes.byref(t2), ctypes.byref(t3)):
            return None
        return (now_ticks - ft(created)) / 1e7

    candidates = []
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if not snap or snap == INVALID_HANDLE:
        return []
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(entry)
        ok = k32.Process32FirstW(snap, ctypes.byref(entry))
        while ok:
            name = entry.szExeFile.lower()
            if name.startswith("python") and name.endswith(".exe"):
                candidates.append(entry.th32ProcessID)
            ok = k32.Process32NextW(snap, ctypes.byref(entry))
    finally:
        k32.CloseHandle(snap)

    now = w.FILETIME()
    k32.GetSystemTimeAsFileTime(ctypes.byref(now))
    now_ticks = ft(now)
    me = os.getpid()
    killed = []
    for pid in candidates:
        if pid == me:
            continue
        h = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_TERMINATE, False, pid)
        if not h:
            continue
        try:
            age = age_s(h, now_ticks)
            if age is None or age < max_age_s or not matches(cmdline(h), script_path):
                continue
            if k32.TerminateProcess(h, 1):
                killed.append(pid)
        finally:
            k32.CloseHandle(h)
    return killed


def run(script_path, state_dir, now=None, reap_fn=None, platform=None):
    """Throttled reap; never raises. Call after the statusline is printed."""
    if (platform or sys.platform) != "win32":
        return
    try:
        if claim(state_dir, now):
            (reap_fn or reap)(script_path)
    except Exception:
        pass
