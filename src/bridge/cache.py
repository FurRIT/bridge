"""
Event Cache Handling.
"""

from typing import Sequence, NamedTuple
import json
import os.path
import itertools
import dataclasses

from bridge.event import Event, hash_event


@dataclasses.dataclass(frozen=True)
class CacheEntry:
    """
    An entry in the cache.

    An (Event ID, Content Hash) pairing; where the content hash is a base64
    hash of the object.
    """

    uid: str
    hash: str
    rev_id: int


def load_cache(path: str) -> Sequence[CacheEntry]:
    """
    Load entries from a Cache file; returns an empty Sequence if the file does
    not exist.
    """
    if not os.path.isfile(path):
        return []

    with open(path, "r", encoding="utf-8") as file:
        raw = json.load(file)

    assert isinstance(raw, list)

    entries = []

    for item in raw:
        assert "uid" in item and isinstance(item["uid"], str)
        assert "hash" in item and isinstance(item["hash"], str)
        assert "rev_id" in item and isinstance(item["rev_id"], int)

        uid: str = item["uid"]
        hash: str = item["hash"]
        rev_id: int = item["rev_id"]

        entry = CacheEntry(uid, hash, rev_id)
        entries.append(entry)

    return entries


def write_cache(path: str, entries: Sequence[CacheEntry]) -> None:
    """
    Destructively overwrite the Cache file with new entries.
    """

    se = list(map(dataclasses.asdict, entries))

    with open(path, "w", encoding="utf-8") as file:
        json.dump(se, file)


class _PartialCacheEntry(NamedTuple):
    """
    Partial Cache Entry; for indexing by uid.
    """

    hash: str
    rev_id: int


class EventSort(NamedTuple):
    """
    Classification of Events in the cache.
    """

    new: Sequence[int]
    updated: Sequence[int]
    unchanged: Sequence[int]
    hashes: Sequence[str]
    entries: Sequence[CacheEntry]


def load_sort_events(path: str, events: Sequence[Event]) -> EventSort:
    """
    Load Entries and Classify Events.
    """

    entries = load_cache(path)
    hashes = list(map(hash_event, events))

    def entry_to_uid_to_partial(entry: CacheEntry) -> tuple[str, _PartialCacheEntry]:
        return (entry.uid, _PartialCacheEntry(entry.hash, entry.rev_id))

    uid_to_partial: dict[str, _PartialCacheEntry] = dict(
        map(
            entry_to_uid_to_partial,
            entries,
        )
    )

    new = []
    updated = []
    unchanged = []

    for i, event in enumerate(events):
        if event.uid not in uid_to_partial:
            new.append(i)
            continue

        ahash = hashes[i]
        entry = uid_to_partial[event.uid]
        if entry.hash != ahash:
            updated.append(i)
            continue

        unchanged.append(i)

    return EventSort(new, updated, unchanged, hashes, entries)


def update_cache(
    path: str, events: Sequence[Event], sort: EventSort | None = None
) -> None:
    """
    Overwrite the existing cache with new Event(s).
    """
    if sort is None:
        sort = load_sort_events(path, events)

    new_and_updated_uids = map(
        lambda i: events[i].uid, itertools.chain(sort.new, sort.updated)
    )
    uid_to_entry: dict[str, CacheEntry] = dict(
        map(lambda entry: (entry.uid, entry), sort.entries)
    )

    carry_over = filter(
        lambda entry: entry.uid not in new_and_updated_uids, sort.entries
    )

    next_cache: list[CacheEntry] = []
    next_cache.extend(carry_over)

    for i in sort.new:
        entry = CacheEntry(events[i].uid, sort.hashes[i], 0)
        next_cache.append(entry)

    for i in sort.updated:
        old = uid_to_entry[events[i].uid]
        entry = CacheEntry(events[i].uid, sort.hashes[i], old.rev_id + 1)

        next_cache.append(entry)

    write_cache(path, next_cache)
