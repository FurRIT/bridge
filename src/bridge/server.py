"""
Server Handlers.
"""

from typing import TypeAlias, TypedDict, Literal, cast
import json

import aiohttp
import aiohttp.web

from bridge.types import AppContext

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

    body = await request.json()
    raw = cast(RawRsvpRequest, body)

    legacy: LegacyRsvpRequest = {
        "partstat": _REQUEST_STATUS_TO_PARTSTAT[raw["status"]],
        "telegramId": raw["telegram_id"],
        "telegramUsername": raw["telegram_username"],
        "telegramName": raw["telegram_name"],
    }

    se_str = json.dumps(legacy)
    se_bytes = se_str.encode("utf-8")

    session = aiohttp.ClientSession()
    eid = request.match_info["id"]

    url = f"http://{ctx.site_host}/partstat/{eid}"
    headers = {"Content-Type": "application/json"}

    async with session.post(url, data=se_bytes, headers=headers) as response:
        ctx.cache_lock.release()

        if response.ok:
            return aiohttp.web.Response(status=200)
        return aiohttp.web.Response(status=500)
