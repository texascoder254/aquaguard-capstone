"""Guards against drift between policy/aquaguard.rego and the in-process mirror (TD-2)."""
import re
from pathlib import Path

from app.policy import AGENT_ACTIONS, CUSTOMER_ACTIONS

REGO = (Path(__file__).resolve().parents[1] / "policy" / "aquaguard.rego").read_text()


def rego_actions(role: str) -> set[str]:
    for block in REGO.split("allow if {")[1:]:
        if f'input.principal.role == "{role}"' in block:
            m = re.search(r"input\.action in \{([^}]*)\}", block)
            return set(re.findall(r'"([^"]+)"', m.group(1))) if m else set()
    return set()


def test_customer_actions_match_rego():
    assert rego_actions("customer") == CUSTOMER_ACTIONS


def test_agent_actions_match_rego():
    assert rego_actions("agent") == AGENT_ACTIONS
