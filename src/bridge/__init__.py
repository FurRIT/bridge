"""
Bridge to legacy server.
"""

from typing import Sequence, NamedTuple
import sys
import json
import base64
import os.path
import hashlib
import logging
import asyncio
import argparse
import textwrap
import dataclasses

import aiohttp
import playwright.async_api

from bridge.config import ConfigParseError, Config, try_load_config
from bridge.cache import CacheEntry, load_cache, write_cache
from bridge.event import Event
from bridge.site.auth import try_load_do_auth
from bridge.site.event import i_extract_event_ids, i_extract_event

logging.basicConfig(level=logging.INFO)


@dataclasses.dataclass(frozen=True)
class AppContext:
    """
    App Synchronization Context.
    """

    cache_lock: asyncio.Lock = dataclasses.field(default_factory=asyncio.Lock)


async def fetch_events(config: Config) -> Sequence[Event]:
    """
    Fetch Events from `site.host`.
    """
    play = await playwright.async_api.async_playwright().start()
    browser = await play.firefox.launch(headless=True)

    logging.info("performing authentication with %s", config.site.host)
    context, page = await try_load_do_auth(
        browser,
        config.site.host,
        config.authcache,
        config.site.username,
        config.site.password,
    )

    logging.info("querying %s for event ids", config.site.host)

    raw_uids = await i_extract_event_ids(page, config.site.host)
    uids = frozenset(raw_uids)

    events = []
    for uid in uids:
        logging.info("querying details of event id=%s", uid)
        get_event_resp = await i_extract_event(context, config.site.host, uid)

        if get_event_resp is None:
            logging.warning("encountered error querying details of event id=%s", uid)
            continue

        event = Event.from_raw_event(get_event_resp["data"])
        events.append(event)

    await page.close()

    await context.storage_state(path=config.authcache)
    await context.close()

    await browser.close()
    await play.stop()

    return events


def _hash_event(event: Event) -> bytes:
    """
    Hacky workaround to avoid implementing a __hash__ method for an Event.

    Assumption: equivalent Events will produce the same json.dumps output; so
    we hash the json.dumps output to get a unique hash.
    """
    se_dict = event.to_dict()
    se_str = json.dumps(se_dict)

    se_bytes = se_str.encode("utf-8")
    hasher = hashlib.blake2b(se_bytes)

    return hasher.digest()


_EXPECTED_PUSH_RESPONSES = frozenset([200, 201])


async def push_event(config: Config, event: Event, rev_id: int) -> None:
    """
    Push an Event to all Clients.
    """

    se_dict = event.to_dict()

    # XXX(mwp): augment the raw event information with revision metadata
    se_dict["rev_id"] = rev_id

    se_str = json.dumps(se_dict)

    se_bytes = se_str.encode("utf-8")
    session = aiohttp.ClientSession()

    for client in config.clients:
        url = f"http://{client.host}:{client.port}/event"
        headers = {"Content-Type": "application/json"}

        hoisted: aiohttp.ClientResponse | None = None

        try:
            async with session.post(url, data=se_bytes, headers=headers) as response:
                hoisted = response
        except aiohttp.ClientConnectionError:
            logging.error("could not connect to client %s", client.name)
            continue

        if hoisted.status not in _EXPECTED_PUSH_RESPONSES:
            logging.error(
                "received unexpected response status=%s from client %s",
                hoisted.status,
                client.name,
            )
            continue

        if hoisted.status == 200:
            logging.info("client %s created new event id=%s", client.name, event.uid)
        else:
            logging.info("client %s updated event id=%s", client.name, event.uid)

    await session.close()


class _PartialCacheEntry(NamedTuple):
    """
    Partial Cache Entry; for indexing by uid.
    """

    hash: str
    rev_id: int


async def fetch_push_events(ctx: AppContext, config: Config) -> None:
    """
    Run fetch_events then push_event for each one.

    Updates the Cache with seen events.
    """

    await ctx.cache_lock.acquire()

    events = await fetch_events(config)
    hashes: list[str] = list(
        map(
            lambda bytes: bytes.decode("utf-8"),
            map(base64.b64encode, map(_hash_event, events)),
        )
    )

    entries = load_cache(config.cache)
    entry_uid_to_partial: dict[str, _PartialCacheEntry] = dict(
        map(
            lambda entry: (
                entry.uid,
                _PartialCacheEntry(entry.hash, entry.rev_id),
            ),
            entries,
        )
    )

    to_push: list[int] = []

    for i, event in enumerate(events):
        if event.uid in entry_uid_to_partial:
            entry_hash = entry_uid_to_partial[event.uid].hash

            if entry_hash == hashes[i]:
                continue

        to_push.append(i)

    for idx in to_push:
        event = events[idx]

        # XXX(mwp): if this event has been cached before, and it's in
        # to_push then it represents the next revision of the cached event
        if event.uid in entry_uid_to_partial:
            rev_id = entry_uid_to_partial[event.uid].rev_id + 1
        else:
            rev_id = 0

        logging.info("pushing event id=%s to clients", event.uid)
        await push_event(config, event, rev_id)

    updated_event_uids = frozenset(
        map(lambda event: event.uid, map(lambda i: events[i], to_push))
    )

    def _derive_entry(i: int) -> CacheEntry:
        """
        Derive a CacheEntry from an Event.

        If the Event is new create a new CacheEntry with rev_id = 0;
        Otherwise, make an entry with a incremented rev_id.
        """
        event = events[i]
        ehash = hashes[i]

        if event.uid not in entry_uid_to_partial:
            return CacheEntry(event.uid, ehash, 0)

        existing = entry_uid_to_partial[event.uid]
        return CacheEntry(event.uid, ehash, existing.rev_id + 1)

    n_entries: list[CacheEntry] = []
    n_entries.extend(filter(lambda entry: entry.uid not in updated_event_uids, entries))
    n_entries.extend(map(_derive_entry, to_push))

    write_cache(config.cache, n_entries)
    ctx.cache_lock.release()


async def run(config: Config) -> None:
    """
    Run Application.
    """
    ctx = AppContext()

    try:
        while True:
            await fetch_push_events(ctx, config)

            logging.info("awaiting next poll...")
            await asyncio.sleep(config.frequency)
    except KeyboardInterrupt:
        pass


def _error(msg: str) -> None:
    print(
        "\n".join(textwrap.wrap(f"error: {msg}", subsequent_indent="       ")),
        file=sys.stderr,
    )
    sys.exit(1)


def main() -> None:
    """
    Parse Arguments & Run Main.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c",
        "--config",
        default="config.toml",
        help="path to config (default %(default)s)",
    )
    args = parser.parse_args()

    if not os.path.isfile(args.config):
        _error(f"config file {args.config} does not exist or is not a file")

    try:
        config = try_load_config(args.config)
    except ConfigParseError as error:
        _error(f"error: occured during config parsing; {error.reason}")

    asyncio.run(run(config))
