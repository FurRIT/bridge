"""
Event Scraping/Fetching Utilities.
"""

from typing import cast
import re

import playwright.async_api

from bridge.site.types import GetEventResponse

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


async def i_extract_event(
    context: playwright.async_api.BrowserContext, host: str, uid: str
) -> GetEventResponse | None:
    """
    Extract Event information.
    """

    response = await context.request.get(
        f"https://{host}/events/id/{uid}", headers={"Accept": "application/json"}
    )
    if not response.ok:
        return None

    body = await response.json()
    typed = cast(GetEventResponse, body)

    return typed
