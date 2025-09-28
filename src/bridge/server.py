"""
Server Handlers.
"""

from typing import TypeAlias, TypedDict, Literal, cast
import base64
import asyncio
import logging

import aiohttp
import aiohttp.web

from bridge.event import Event, hash_event
from bridge.types import AppContext
from bridge.cache import load_cache, load_sort_events, update_cache
from bridge.client import push_event_to_clients
from bridge.site.auth import try_load_do_auth
from bridge.site.event import i_extract_event

routes = aiohttp.web.RouteTableDef()

RsvpRequestStatus: TypeAlias = Literal[0] | Literal[1] | Literal[2]


class RawRsvpRequest(TypedDict):
    """
    Raw RSVP Request.
    """

    telegram_id: int
    telegram_username: str
    telegram_name: str
    status: RsvpRequestStatus


LegacyPartstat: TypeAlias = (
    Literal["ACCEPTED"] | Literal["TENTATIVE"] | Literal["DECLINED"]
)


class LegacyRsvpRequest(TypedDict):
    """
    Legacy API RSVP Request.
    """

    partstat: LegacyPartstat
    telegramId: int
    telegramUsername: str
    telegramName: str


_REQUEST_STATUS_TO_PARTSTAT: dict[RsvpRequestStatus, LegacyPartstat] = {
    0: "ACCEPTED",
    1: "TENTATIVE",
    2: "DECLINED",
}


async def _update_clients(ctx: AppContext, eid: str) -> None:
    """
    Background Task to update clients with new event information.
    """
    logging.info("bgupd event id=%s | authentication", eid)

    async with ctx.play_lock:
        await try_load_do_auth(
            ctx.config.site.host,
            ctx.config.authcache,
            ctx.config.site.username,
            ctx.config.site.password,
            context=ctx.persist.context,
            page=ctx.persist.page,
        )
        await ctx.persist.context.storage_state(path=ctx.config.authcache)

        logging.info("bgupd event id=%s | extraction", eid)
        raw_event_r = await i_extract_event(
            ctx.persist.context, ctx.config.site.host, eid
        )

    if raw_event_r is None:
        logging.info("bgupd event id=%s | extraction failed!", eid)
        return

    event = Event.from_raw_event(raw_event_r["data"])

    async with ctx.cache_lock:
        sort = load_sort_events(ctx.config.cache, [event])
        duplicate = len(sort.updated) == 0

        update_cache(ctx.config.cache, [event])

    if not duplicate:
        logging.info("bgupd event id=%s | pushing", eid)
        await push_event_to_clients(ctx.config, event)


@routes.post("/event/{id}/rsvp")
async def post_event_rsvp(request: aiohttp.web.Request):
    """
    Accept and forward an RSVP.
    """
    ctx = cast(AppContext, request.app["ctx"])

    body = await request.json()
    raw = cast(RawRsvpRequest, body)

    eid = request.match_info["id"]

    url = f"https://{ctx.config.site.host}/events/partstat/{eid}"
    legacy: LegacyRsvpRequest = {
        "partstat": _REQUEST_STATUS_TO_PARTSTAT[raw["status"]],
        "telegramId": raw["telegram_id"],
        "telegramUsername": raw["telegram_username"],
        "telegramName": raw["telegram_name"],
    }

    session = aiohttp.ClientSession()

    ok = False
    async with session.post(url, json=legacy) as response:
        ok = response.ok

    # XXX(mwp): create a background task to fetch the updated event and push it
    # to clients
    asyncio.create_task(_update_clients(ctx, eid))
    await session.close()

    if ok:
        return aiohttp.web.Response(status=200)
    return aiohttp.web.Response(status=500)
