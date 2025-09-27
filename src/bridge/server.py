"""
Server Handlers.
"""

from typing import TypeAlias, TypedDict, Literal, cast

import aiohttp
import aiohttp.web

from bridge.types import AppContext
from bridge.site.auth import try_load_do_auth

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


@routes.post("/event/{id}/rsvp")
async def post_event_rsvp(request: aiohttp.web.Request):
    """
    Accept and forward an RSVP.
    """
    ctx = cast(AppContext, request.app["ctx"])
    await ctx.cache_lock.acquire()

    await try_load_do_auth(
        ctx.config.site.host,
        ctx.config.authcache,
        ctx.config.site.username,
        ctx.config.site.password,
        context=ctx.persist.context,
        page=ctx.persist.page,
    )
    await ctx.persist.context.storage_state(path=ctx.config.authcache)

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

    ctx.cache_lock.release()
    await session.close()

    if ok:
        return aiohttp.web.Response(status=200)
    return aiohttp.web.Response(status=500)
