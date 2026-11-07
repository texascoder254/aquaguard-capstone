"""Authorization policy mirroring policy/aquaguard.rego.

Inputs come only from the verified token and server-loaded resource ownership.
"""
from .errors import ApiError

CUSTOMER_ACTIONS = {"readings:read", "messages:write", "cases:open", "feedback:write", "transcript:read"}
AGENT_ACTIONS = {"readings:read", "cases:read", "cases:reply", "transcript:read"}


class Policy:
    def __init__(self):
        self.available = True  # flipped in tests to prove fail-closed behaviour

    def allow(self, principal: dict, action: str, resource: dict) -> bool:
        if not self.available:
            raise ApiError(503, "policy_unavailable", "Authorization service unavailable")
        role = principal["role"]
        if role == "simulator":
            return action == "readings:write" and resource.get("simulator_user_id") == principal["user_id"]
        if role == "customer":
            return action in CUSTOMER_ACTIONS and resource.get("client_id") == principal["client_id"]
        if role == "agent":
            return action in AGENT_ACTIONS and resource.get("client_id") in principal.get("scopes", [])
        return False

    def require(self, principal: dict, action: str, resource: dict, hide: bool = True) -> None:
        """Raise 404 (hide existence) or 403 when the action is denied."""
        if not self.allow(principal, action, resource):
            if hide:
                raise ApiError(404, "not_found", "Resource not found")
            raise ApiError(403, "forbidden", "Role not permitted")
