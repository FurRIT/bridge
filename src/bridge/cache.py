"""
Event Cache Handling.
"""

from typing import Sequence
import json
import os.path
import dataclasses


@dataclasses.dataclass(frozen=True)
class CacheEntry:
    """
    An entry in the cache.

    An (Event ID, Content Hash) pairing; where the content hash is a base64
    hash of the object.
    """

    uid: str
    hash: str


def load_cache(path: str) -> Sequence[CacheEntry]:
    """
    Load entries from a Cache file; returns an empty Sequence if the file does
    not exist.
    """
    if not os.path.exists(path):
        return []

    with open(path, "r", encoding="utf-8") as file:
        raw = json.load(file)

    assert isinstance(raw, list)

    entries = []

    for item in raw:
        assert "uid" in item and isinstance(item["uid"], str)
        assert "hash" in item and isinstance(item["hash"], str)

        entry = CacheEntry(item["uid"], item["hash"])
        entries.append(entry)

    return entries


def write_cache(path: str, entries: Sequence[CacheEntry]) -> None:
    """
    Destructively overwrite the Cache file with new entries.
    """

    with open(path, "w", encoding="utf-8") as file:
        json.dump(entries, file)
