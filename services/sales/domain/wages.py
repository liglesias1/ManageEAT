"""Where sales gets its wage costs from: the only file of the sales service that talks to personnel (ADR-2, ADR-6).

profit_and_loss() receives a function labor_cost_for(start, end) and never asks where the number comes
from. Here that function works in three steps, for each period it is asked about:

1. Live: ask personnel's endpoint GET /personnel/labor-cost over HTTP, forwarding the manager's token so
   personnel knows which restaurant is asking. Every answer is also saved as the period's snapshot.
2. Snapshot: if personnel does not answer within PERSONNEL_TIMEOUT_S, answers with an error or answers
   something that is not the agreed shape, use the last cost received for that period, with its date.
3. Unavailable: if there is no snapshot for a period either, the route blanks every figure that depends
   on wages (services.without_wages), so the manager never sees a profit that silently leaves them out.

After the first failure personnel is not asked again in the same request: one profit and loss asks for
several periods (the month, each week, each month of the history), and waiting the timeout for each of
them would hang the page.
"""
import logging
from datetime import datetime, timezone

import httpx

import config
from domain import repository

logger = logging.getLogger(__name__)

LABOR_COST_PATH = "/personnel/labor-cost"


class Wages:
    """Wage costs for one request: live from personnel when it answers, otherwise the last ones received."""

    def __init__(self, client, token, conn, restaurant_id):
        self._client = client
        self._headers = {"Authorization": f"Bearer {token}"}
        self._conn = conn
        self._restaurant_id = restaurant_id
        self._known = {}                 # (start, end) -> cost, so the same period is never asked twice
        self.personnel_answers = True
        self.used_snapshot = False
        self.missing = False             # some period had neither a live answer nor a snapshot
        self.oldest_snapshot = None      # fetched_at of the oldest snapshot used

    def labor_cost_for(self, start, end):
        if (start, end) in self._known:
            return self._known[(start, end)]
        if self.personnel_answers:
            try:
                cost = self._ask_personnel(start, end)
            except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
                # HTTPError covers timeouts, refused connections and 4xx/5xx answers
                logger.warning("Personnel did not answer as agreed, using the last wages received: %r", error)
                self.personnel_answers = False
            else:
                fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
                repository.save_labor_cost(self._conn, self._restaurant_id, start, end, cost, fetched_at)
                self._known[(start, end)] = cost
                return cost
        return self._from_snapshot(start, end)

    def _ask_personnel(self, start, end):
        response = self._client.get(LABOR_COST_PATH, params={"start": start, "end": end}, headers=self._headers)
        response.raise_for_status()
        return float(response.json()["labor_cost"])

    def _from_snapshot(self, start, end):
        snapshot = repository.get_labor_cost_snapshot(self._conn, self._restaurant_id, start, end)
        if snapshot is None:
            self.missing = True
            return 0.0
        cost, fetched_at = snapshot
        self.used_snapshot = True
        self.oldest_snapshot = min(filter(None, [self.oldest_snapshot, fetched_at]))
        self._known[(start, end)] = cost
        return cost

    @property
    def source(self):
        """'live', 'snapshot' (at least one period from a snapshot) or 'unavailable' (at least one period missing)."""
        if self.missing:
            return "unavailable"
        return "snapshot" if self.used_snapshot else "live"

    def report(self):
        """What the API tells the UI about where the wages came from."""
        if self.source == "snapshot":
            return {"source": "snapshot", "as_of": self.oldest_snapshot}
        return {"source": self.source}


def personnel_client():
    """One HTTP client per request, with the base URL and timeout from config, always closed afterwards.

    Routes receive it with Depends(personnel_client), so the tests can replace personnel with a stub.
    """
    with httpx.Client(base_url=config.PERSONNEL_URL, timeout=config.PERSONNEL_TIMEOUT_S) as client:
        yield client