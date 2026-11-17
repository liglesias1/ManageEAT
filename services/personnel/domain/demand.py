"""Where personnel gets the demand from: the only file of the personnel service that talks to sales (ADR-6).

The schedule compares the staff on shift with the diners per hour, and the diners come from the orders,
which belong to sales. So personnel asks sales' endpoint GET /sales/covers over HTTP, forwarding the
manager's token so sales knows which restaurant is asking. It follows the same three steps as the wages
in the sales service:

1. Live: ask sales, and save its whole answer as the restaurant's snapshot.
2. Snapshot: if sales does not answer within SALES_TIMEOUT_S, answers with an error or answers something
   that is not the agreed shape, use the last answer received, with its date.
3. Unavailable: if there is no snapshot either, the schedule is not shown; payroll and everything else
   personnel owns keep working.
"""
import json
import logging
from datetime import datetime, timezone

import httpx

import config
from domain import repository

logger = logging.getLogger(__name__)

COVERS_PATH = "/sales/covers"


def _checked(payload):
    """The answer if it has the agreed shape ({"covers": [{day, hour, covers}], "open_days": [day]}), else ValueError."""
    covers, open_days = payload["covers"], payload["open_days"]
    if not isinstance(covers, list) or not isinstance(open_days, list):
        raise ValueError("covers and open_days must be lists")
    for row in covers:
        if not {"day", "hour", "covers"} <= set(row):
            raise ValueError(f"a covers row without day, hour or covers: {row}")
    return {"covers": covers, "open_days": open_days}


class Demand:
    """The covers per hour and open days of one restaurant, live from sales or the last ones received."""

    def __init__(self, client, token, conn, restaurant_id):
        self._client = client
        self._headers = {"Authorization": f"Bearer {token}"}
        self._conn = conn
        self._restaurant_id = restaurant_id
        self.source = None          # 'live', 'snapshot' or 'unavailable', once get() has run
        self.as_of = None

    def get(self):
        """{"covers": [...], "open_days": [...]}, or None if sales does not answer and there is no snapshot."""
        try:
            response = self._client.get(COVERS_PATH, headers=self._headers)
            response.raise_for_status()
            data = _checked(response.json())
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
            # HTTPError covers timeouts, refused connections and 4xx/5xx answers
            logger.warning("Sales did not answer as agreed, using the last covers received: %r", error)
            return self._from_snapshot()
        fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        repository.save_demand(self._conn, self._restaurant_id, json.dumps(data), fetched_at)
        self.source = "live"
        return data

    def _from_snapshot(self):
        snapshot = repository.get_demand_snapshot(self._conn, self._restaurant_id)
        if snapshot is None:
            self.source = "unavailable"
            return None
        payload, self.as_of = snapshot
        self.source = "snapshot"
        return json.loads(payload)

    def report(self):
        """What the API tells the UI about where the covers came from."""
        if self.source == "snapshot":
            return {"source": "snapshot", "as_of": self.as_of}
        return {"source": self.source}


def sales_client():
    """One HTTP client per request, with the base URL and timeout from config, always closed afterwards.

    Routes receive it with Depends(sales_client), so the tests can replace sales with a stub.
    """
    with httpx.Client(base_url=config.SALES_URL, timeout=config.SALES_TIMEOUT_S) as client:
        yield client