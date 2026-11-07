"""Read-only adapter to the existing customer database (service settings only)."""
from .errors import ApiError


class CustomerAdapter:
    def __init__(self, repo):
        self.repo = repo

    def get(self, client_id: str) -> dict:
        row = self.repo.one("SELECT service_tier, timezone FROM clients WHERE client_id = ?", (client_id,))
        if row is None:
            raise ApiError(409, "configuration_required", "Customer mapping missing")
        return {"service_tier": row["service_tier"], "timezone": row["timezone"]}
