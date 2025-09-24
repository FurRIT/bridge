"""
Type Definitions.

Type definitions that exist on the boundary of the site and this application.
Mostly descriptions of deserialized types returned by the API.
"""

from typing import TypedDict, Literal


class RawUserFurryDetails(TypedDict):
    """
    Generic.
    """

    furName: str


class RawUser(TypedDict):
    """
    Generic.
    """

    furryDetails: RawUserFurryDetails
    furRITUsername: str
    _id: str


class RawAttendeeUser(TypedDict):
    """
    `.attendees[].user`
    """

    furryDetails: RawUserFurryDetails
    _id: str


class RawAttendee(TypedDict):
    """
    `.attendees[]`
    """

    _id: str
    user: RawAttendeeUser
    partstat: str


class RawTelegramMessage(TypedDict):
    """
    `.telegramMessages[]`
    """

    chatId: int
    messageId: int


class RawEvent(TypedDict):
    """
    Root-Level Event.

    rrule: Event repition rule; nulled out to avoid annotation.
    exrule: Exception to repitition rule; nulled out to avoid annotation.
    status: ...
    allday: ...
    rdate: Has to do with repitition; nulled out to avoid annotation.
    exdate: Has to do with exceptions; nulled out to avoid annotation.
    categories: Basic Event tags.
    _id: Unique Event Identifier.
    organizer: Event Organizer.
    attendees: List of partial User data and response type.
    created: ISO Encoded time string of Event creation.
    dtstamp: The same as created (?)
    alarm: Has to do with reminders; nulled out to avoid annotation.
    telegramMessages: Store of already-sent TG messages.
    summery: Short summary of Event.
    description: Longer description of Event.
    location: Short location of Event.
    dtstart: ISO Encoded Event start time.
    dtend: ISO Encoded Event end time.
    """

    rrule: None
    exrule: None
    status: Literal["TENTATIVE"] | Literal["CONFIRMED"] | Literal["CANCELED"]
    allday: bool
    rdate: list[None]
    exdate: list[None]
    categories: list[str]
    _id: str
    organizer: RawUser
    attendees: list[RawAttendee]
    created: str
    dtstamp: str
    alarm: list[None]
    telegramMessages: list[RawTelegramMessage]
    summery: str
    description: str
    location: str
    dtstart: str
    dtend: str


class GetEventResponse(TypedDict):
    """
    Response to GET /events/id/{eventid}
    """
    success: bool
    data: RawEvent
    requestorHasUpdatePrivs: bool
    csrfToken: str
