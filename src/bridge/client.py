"""
Client Handling Utilities.
"""

from typing import Any
import aiohttp
import logging

from bridge.event import Event
from bridge.config import Config


_EXPECTED_PUSH_RESPONSES = frozenset([200, 201])


async def _push_event_to_client(
    session: aiohttp.ClientSession,
    name: str,
    host: str,
    port: int,
    uid: str,
    event: dict[Any, Any],
) -> None:
    """
    Push an Event to a Client.
    """
    url = f"http://{host}:{port}/event"
    headers = {"Content-Type": "application/json"}

    try:
        async with session.post(url, json=event, headers=headers) as response:
            hoisted = response
    except aiohttp.ClientConnectionError:
        logging.error("could not connect to client %s", name)
        return

    if hoisted.status not in _EXPECTED_PUSH_RESPONSES:
        logging.error(
            "received unexpected response status=%s from client %s",
            hoisted.status,
            name,
        )
        return

    if hoisted.status == 200:
        logging.info("client %s created new event id=%s", name, uid)
    else:
        logging.info("client %s updated event id=%s", name, uid)


async def push_event_to_clients(config: Config, event: Event) -> None:
    """
    Push an Event to all Clients.
    """

    se = event.to_dict()
    session = aiohttp.ClientSession()

    for client in config.clients:
        await _push_event_to_client(
            session,
            client.name,
            client.host,
            client.port,
            event.uid,
            se,
        )

    await session.close()
