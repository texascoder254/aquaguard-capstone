"""Seeds demo clients, users, and tanks for the alpha increment."""
from .security import hash_password

CLIENT_A = "11111111-1111-4111-8111-111111111111"
CLIENT_B = "22222222-2222-4222-8222-222222222222"
TANK_REEF = "aaaaaaaa-0000-4000-8000-000000000001"
TANK_PLANTED = "aaaaaaaa-0000-4000-8000-000000000002"
TANK_OTHER = "bbbbbbbb-0000-4000-8000-000000000003"
TANK_UNCONFIGURED = "aaaaaaaa-0000-4000-8000-000000000004"

USERS = [
    ("u-cust-a", "maya", "reef-demo-1", "customer", CLIENT_A),
    ("u-cust-b", "omar", "planted-demo-2", "customer", CLIENT_B),
    ("u-sim-a", "sim-a", "sensor-demo-3", "simulator", CLIENT_A),
    ("u-agent", "agent-lee", "agent-demo-4", "agent", None),
]
DEMO_PASSWORDS = {u[1]: u[2] for u in USERS}


def seed(repo) -> None:
    if repo.one("SELECT 1 FROM clients LIMIT 1"):
        return
    with repo.transaction() as db:
        db.execute("INSERT INTO clients VALUES (?,?,?,?)", (CLIENT_A, "Harbor Aquatics", "premium", "America/New_York"))
        db.execute("INSERT INTO clients VALUES (?,?,?,?)", (CLIENT_B, "Greenleaf Tanks", "standard", "America/Chicago"))
        for user_id, name, password, role, client in USERS:
            db.execute("INSERT INTO users VALUES (?,?,?,?,?)", (user_id, name, hash_password(password), role, client))
        db.execute("INSERT INTO agent_scopes VALUES (?,?)", ("u-agent", CLIENT_A))
        tanks = [
            (TANK_REEF, CLIENT_A, "Reef 120L", 24.0, 27.0, 7.8, 8.4, 85.0, 100.0, "u-sim-a"),
            (TANK_PLANTED, CLIENT_A, "Planted 60L", 22.0, 26.0, 6.5, 7.5, 80.0, 100.0, "u-sim-a"),
            (TANK_OTHER, CLIENT_B, "Community 200L", 23.0, 27.0, 6.8, 7.8, 80.0, 100.0, None),
            (TANK_UNCONFIGURED, CLIENT_A, "Quarantine 20L", None, None, None, None, None, None, "u-sim-a"),
        ]
        db.executemany("INSERT INTO tanks VALUES (?,?,?,?,?,?,?,?,?,?)", tanks)
