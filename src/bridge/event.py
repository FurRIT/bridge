"""
Event Handling.
"""

from __future__ import annotations
from typing import Any, cast
import enum
import json
import base64
import hashlib
import datetime
import dataclasses

from bridge.site.types import RawEvent


def _get_nonempty_string(src: dict[str, Any], name: str) -> str | None:
    """
    Get a string from the dictionary; check that it is non-empty.
    """
    if (name in src) and (isinstance(src[name], str)) and (len(src[name]) != 0):
        return src[name]

    return None


@enum.unique
class ParticipationStatus(enum.Enum):
    """
    Participation status of an Attendee.
    """

    ACCEPTED = "ACCEPTED"
    TENTATIVE = "TENTATIVE"
    DECLINED = "DECLINED"


@dataclasses.dataclass(frozen=True)
class Attendee:
    """
    An Event Attendee.

    aid:      `.attendee[]._id`
    uid:      `.attendee[].user._id`
    furname:  `.attendee[].user.furryDetails.furName`
    username: `.attendee[].user.furRITUsername`
    status:   `.attendee[].partstat`
    """

    aid: str
    uid: str
    furname: str | None
    username: str | None
    status: ParticipationStatus

    @staticmethod
    def from_raw(raw: dict[str, Any]) -> Attendee:
        """From `.attendees[i]` JSON entry."""
        assert "_id" in raw
        aid = raw["_id"]

        assert "partstat" in raw and isinstance(raw["partstat"], str)
        status = ParticipationStatus(raw["partstat"])

        assert "user" in raw and isinstance(raw["user"], dict)
        raw_user = raw["user"]

        assert "_id" in raw_user and isinstance(raw_user["_id"], str)
        uid = raw_user["_id"]

        username = _get_nonempty_string(raw_user, "furRITUsername")

        assert "furryDetails" in raw_user and isinstance(raw_user["furryDetails"], dict)
        furry_details = raw_user["furryDetails"]

        furname = _get_nonempty_string(furry_details, "furName")

        return Attendee(aid, uid, furname, username, status)


@dataclasses.dataclass(frozen=True)
class Organizer:
    """
    An Event Organizer.

    uid:      `.organizer._id`
    furname:  `.organizer.furryDetails.furName`
    username: `.organizer.furRITUsername`
    """

    uid: str
    furname: str | None
    username: str | None

    @staticmethod
    def from_raw(raw: dict[str, Any]) -> Organizer:
        """From `.organizer` JSON entry."""
        assert "_id" in raw and isinstance(raw["_id"], str)
        uid = raw["_id"]

        assert "furryDetails" in raw and isinstance(raw["furryDetails"], dict)
        furry_details = raw["furryDetails"]

        username = _get_nonempty_string(raw, "furRITUsername")
        furname = _get_nonempty_string(furry_details, "furName")

        return Organizer(uid, furname, username)


@enum.unique
class EventStatus(enum.Enum):
    """
    Event Status.
    """

    TENTATIVE = "TENTATIVE"
    CONFIRMED = "CONFIRMED"
    CANCELED = "CANCELED"


# pylint: disable=too-many-instance-attributes
@dataclasses.dataclass(frozen=True)
class Event:
    """
    An translated subset of a RawEvent.

    uid:         `._id`
    status:      `.status`
    allday:      `.allday`
    organizer:   `.organizer` (see Organizer)
    attendees:   `.attendees` (see Attendee)
    location:    `.location`
    summary:     `.summery`
    description: `.description`
    dtstart:     `.dtstart`
    dtend:       `.dtend`
    """

    uid: str
    status: EventStatus
    allday: bool
    organizer: Organizer
    attendees: list[Attendee]
    summary: str | None
    location: str | None
    description: str | None
    dtstart: datetime.datetime
    dtend: datetime.datetime

    @staticmethod
    def from_raw_event(raw_event: RawEvent) -> Event:
        """
        Construct from a RawEvent.
        """
        uid = raw_event["_id"]
        status = EventStatus(raw_event["status"])
        allday = raw_event["allday"]

        raw_organizer = raw_event["organizer"]
        organizer = Organizer.from_raw(cast(dict[str, Any], raw_organizer))

        attendees = []
        raw_attendees = raw_event["attendees"]

        for raw_attendee in raw_attendees:
            attendee = Attendee.from_raw(cast(dict[str, Any], raw_attendee))
            attendees.append(attendee)

        aliased = cast(dict[str, Any], raw_event)

        summary = _get_nonempty_string(aliased, "summery")
        location = _get_nonempty_string(aliased, "location")
        description = _get_nonempty_string(aliased, "description")

        if summary is not None:
            summary = summary.replace("\r\n", "\n")

        if description is not None:
            description = description.replace("\r\n", "\n")

        raw_dtstart = _get_nonempty_string(aliased, "dtstart")
        raw_dtend = _get_nonempty_string(aliased, "dtend")

        assert raw_dtstart is not None
        assert raw_dtend is not None

        dtstart = datetime.datetime.fromisoformat(raw_dtstart)
        dtend = datetime.datetime.fromisoformat(raw_dtend)

        return Event(
            uid,
            status,
            allday,
            organizer,
            attendees,
            summary,
            location,
            description,
            dtstart,
            dtend,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to a `dict` for serialization."""
        base = dataclasses.asdict(self)

        base["status"] = base["status"].value

        def remap(attendee: dict[str, Any]) -> dict[str, Any]:
            attendee["status"] = attendee["status"].value
            return attendee

        base["attendees"] = list(map(remap, base["attendees"]))

        base["dtstart"] = base["dtstart"].isoformat()
        base["dtend"] = base["dtend"].isoformat()

        return base


def hash_event(event: Event) -> str:
    """
    Hacky workaround to avoid implementing a __hash__ method for an Event.

    Assumption: equivalent Events will produce the same json.dumps output; so
    we hash the json.dumps output to get a unique hash.
    """
    se_dict = event.to_dict()
    se_str = json.dumps(se_dict)

    se_bytes = se_str.encode("utf-8")
    hasher = hashlib.blake2b(se_bytes)

    dig = hasher.digest()
    enc = base64.b64encode(dig)

    return enc.decode("utf-8")
