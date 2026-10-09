"""Single-use, short-lived WebSocket tickets.

Browser WebSockets cannot set Authorization headers; clients buy a ticket
over authenticated REST and redeem it exactly once on connect. Tickets never
contain secrets and are never logged.
"""

import secrets
import time
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Ticket:
    id: str
    expires_at: float


@dataclass
class WsTicketStore:
    ttl_seconds: float
    max_outstanding: int = 64
    _tickets: dict[str, Ticket] = field(default_factory=lambda: dict[str, Ticket]())

    def issue(self) -> Ticket:
        now = time.monotonic()
        self._expire(now)
        if len(self._tickets) >= self.max_outstanding:
            # Bounded: oldest tickets expire quickly; refuse floods.
            raise PermissionError("Too many outstanding WebSocket tickets")
        ticket = Ticket(id=secrets.token_urlsafe(32), expires_at=now + self.ttl_seconds)
        self._tickets[ticket.id] = ticket
        return ticket

    def redeem(self, ticket_id: str) -> bool:
        now = time.monotonic()
        self._expire(now)
        ticket = self._tickets.pop(ticket_id, None)
        return ticket is not None and ticket.expires_at > now

    def _expire(self, now: float) -> None:
        expired = [key for key, ticket in self._tickets.items() if ticket.expires_at <= now]
        for key in expired:
            del self._tickets[key]
