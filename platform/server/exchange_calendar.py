"""XNYS session checks using the exchange calendar, including early closes."""
from datetime import timezone
from zoneinfo import ZoneInfo

import exchange_calendars


class XNYSCalendar:
    def __init__(self, calendar=None):
        self._calendar = calendar or exchange_calendars.get_calendar("XNYS")

    def session_bounds(self, at):
        if at.tzinfo is None or at.utcoffset() is None:
            raise ValueError("Exchange calendar requires an aware timestamp")
        session_date = at.astimezone(ZoneInfo("America/New_York")).date().isoformat()
        try:
            session = self._calendar.date_to_session(session_date, direction="none")
        except (ValueError, KeyError):
            return None
        opened = self._calendar.session_open(session).to_pydatetime().astimezone(timezone.utc)
        closed = self._calendar.session_close(session).to_pydatetime().astimezone(timezone.utc)
        return opened, closed

    def is_open(self, at):
        bounds = self.session_bounds(at)
        if bounds is None:
            return False
        opened, closed = bounds
        at = at.astimezone(timezone.utc)
        return opened <= at < closed
