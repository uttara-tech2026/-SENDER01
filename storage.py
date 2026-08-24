"""
Minimal JSON-file persistence.

The only state this bot needs to remember is which media items it has
already seen (by Telegram's file_unique_id), so it can silently drop
duplicates. Everything is global -- there's no per-chat/per-user split,
since every sender funnels into the same admin relay.

{
  "seen_unique_ids": [str, ...]
}
"""

import json
import os
import asyncio

import config

_lock = asyncio.Lock()
_data = None


def _default():
    return {"seen_unique_ids": []}


def _load():
    global _data
    if _data is not None:
        return _data
    if os.path.exists(config.DATA_FILE):
        try:
            with open(config.DATA_FILE, "r", encoding="utf-8") as f:
                _data = json.load(f)
        except (json.JSONDecodeError, OSError):
            _data = _default()
    else:
        _data = _default()
    _data.setdefault("seen_unique_ids", [])
    return _data


def _save():
    tmp = config.DATA_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(_data, f, indent=2)
    os.replace(tmp, config.DATA_FILE)


async def check_and_mark(unique_id: str) -> bool:
    """Atomically check whether unique_id has been seen before and, if
    not, record it. Returns True for a brand-new item (caller should
    relay it), False if it's a duplicate (caller should drop it).

    Doing the check-and-mark under a single lock (rather than a separate
    is_duplicate() + mark_seen()) avoids a race where two near-identical
    uploads arriving at the same instant both pass the check before
    either has recorded itself.
    """
    async with _lock:
        data = _load()
        seen = data["seen_unique_ids"]
        if unique_id in seen:
            return False
        seen.append(unique_id)
        # keep this bounded so the JSON file doesn't grow forever
        if len(seen) > 5000:
            data["seen_unique_ids"] = seen[-5000:]
        _save()
        return True
