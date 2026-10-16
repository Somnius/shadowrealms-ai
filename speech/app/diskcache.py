"""Disk use and the TTS cache cap (VOICE_TTS_CACHE_GB). Least recently used lines go first:
serving a line touches its file, so mtime is the last use."""
import os


def dir_bytes(root):
    total = 0
    for dp, _dirs, files in os.walk(root):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(dp, f))
            except OSError:
                pass
    return total


def touch(path):
    try:
        os.utime(path, None)
    except OSError:
        pass


def evict_lru(root, cap_bytes):
    """Delete whole entries (key.ogg + key.m4a) oldest first until the cache is under the cap.
    Returns how many entries were removed."""
    entries = {}
    for dp, _dirs, files in os.walk(root):
        for f in files:
            key, ext = os.path.splitext(f)
            if ext not in (".ogg", ".m4a"):
                continue
            p = os.path.join(dp, f)
            try:
                st = os.stat(p)
            except OSError:
                continue
            e = entries.setdefault(os.path.join(dp, key), [0, 0.0])
            e[0] += st.st_size
            if ext == ".ogg":
                e[1] = st.st_mtime
    total = sum(e[0] for e in entries.values())
    removed = 0
    for base, (size, _mt) in sorted(entries.items(), key=lambda kv: kv[1][1]):
        if total <= cap_bytes:
            break
        for ext in (".ogg", ".m4a"):  # ogg first: without it the entry counts as missing
            try:
                os.remove(base + ext)
            except OSError:
                pass
        total -= size
        removed += 1
    return removed
