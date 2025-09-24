"""
Event Scraping/Fetching Utilities.
"""

from typing import TypedDict, cast
import re
import sys
import json
import playwright.async_api

_ONCLICK_PATTERN = re.compile(
    r"window\.location\.assign\('\/events\/id\/([a-zA-Z0-9]+)'\);",
)


async def i_extract_event_ids(page: playwright.async_api.Page, host: str) -> list[str]:
    """
    Interact to extract Event identifiers.
    """

    await page.goto(f"https://{host}/events")

    cdiv = page.locator("#content")
    cards = cdiv.locator(".cursor_pointer")

    uids = []
    ncards = await cards.count()

    for i in range(ncards):
        card = cards.nth(i)

        attr = await card.get_attribute("onclick")
        if attr is None:
            continue

        match = _ONCLICK_PATTERN.match(attr)
        if match is None:
            continue

        uid = match[1]
        uids.append(uid)

    return uids


class UserFurryDetails(TypedDict):
    """
    Generic.
    """

    furName: str


class User(TypedDict):
    """
    Generic.
    """

    furryDetails: UserFurryDetails
    furRITUsername: str
    _id: str


class AttendeeUser(TypedDict):
    """
    `.attendees[].user`
    """

    furryDetails: UserFurryDetails
    _id: str


class Attendee(TypedDict):
    """
    `.attendees[]`
    """

    _id: str
    user: AttendeeUser
    partstat: str


class Event(TypedDict):
    # repeat rule
    rrule: None
    # exception rule
    exrule: None
    status: str
    allday: bool
    rdate: list[None]
    exdate: list[None]
    categories: list[str]
    _id: str
    organizer: User
    attendees: list[Attendee]
    created: str
    dtstamp: str
    alarm: list[None]
    telegramMessages: list[None]
    summery: str
    description: str
    location: str
    dtstart: str
    dtend: str


class GetEventResponse(TypedDict):
    success: bool
    data: Event
    requestorHasUpdatePrivs: bool
    csrfToken: str


async def i_extract_event(
    context: playwright.async_api.BrowserContext, host: str, uid: str
) -> None:
    """
    Extract Event information.
    """

    response = await context.request.get(
        f"https://{host}/events/id/{uid}", headers={"Accept": "application/json"}
    )
    if not response.ok:
        return None

    body = await response.json()
    json.dump(body, sys.stdout)
    # typed = cast(GetEventResponse, body)
    # print(typed["data"])
