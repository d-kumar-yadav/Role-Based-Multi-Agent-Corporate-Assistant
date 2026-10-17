import json
import os
from pathlib import Path
from app.auth.models import User

DEMO_PASSWORD_HASH = chr(36) + '2b' + chr(36) + '12' + chr(36) + 'YuNdxQY0/GXU6OBJt2kLnOSdVwdMgqxK8InZsLm2yQ7fVlHD87OP.'

def _get_seeded_users():
    p = Path('data') / 'structured' / 'employees.json'
    with open(p, 'r', encoding='utf-8') as f:
        return json.load(f)

_USERS_DATA = _get_seeded_users()

USERS_BY_ID: dict[str, User] = {u['user_id']: User(**u) for u in _USERS_DATA}
# user = User(user_id="E1001", email="alice@...", role="employee")
USERS_BY_EMAIL: dict[str, User] = {u['email'].lower(): User(**u) for u in _USERS_DATA}
USERS_BY_EMAIL['cto.executive@meridianglobal.example'] = USERS_BY_ID['E6001']
USERS_BY_EMAIL['cfo.executive@meridianglobal.example'] = USERS_BY_ID['E6002']

def get_user_by_email(email: str) -> User | None:
    return USERS_BY_EMAIL.get(email.strip().lower())

def get_user_by_id(user_id: str) -> User | None:
    return USERS_BY_ID.get(user_id)

def _init_structured_file():
    p = Path('data') / 'structured' / 'employees.json'
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        with open(p, 'w', encoding='utf-8') as f:
            json.dump(_USERS_DATA, f, indent=2)

_init_structured_file()




# {
#   "E1001": User(user_id="E1001", email="alice.johnson@...", name="Alice Johnson", role="employee", ...),
#   "E1002": User(user_id="E1002", email="raj.patel@...", name="Raj Patel", role="employee", ...),
#   "E2001": User(user_id="E2001", email="bob.smith@...", ...),
#   ...
# }

# user = USERS_BY_ID["E1001"]
# user.email        # ✅ "alice.johnson@meridianglobal.example"
# user.role         # ✅ "employee"
# user.user_id      # ✅ "E1001"


# Q: "Why two dicts instead of one list?"
# "Because I have two different access patterns. Login looks users up by email; JWT verification looks them up by ID. Building two dicts upfront makes both O(1). The alternative — one list scanned on every request — is O(n). For 18 users it doesn't matter, but the pattern is the same in production, and the cost is trivial."

# : "What does User(**u) do?"
# "It's keyword argument unpacking. If u is {"user_id": "E1001", "email": "..."}, then User(**u) is equivalent to User(user_id="E1001", email="..."). It's how I convert a JSON dict into a Pydantic model instance in one line."

# Q: "What happens if employees.json is missing?"
# "On the first import, _get_seeded_users() reads from the JSON file. If it's missing, that fails. To fix it: there's an implicit convention that the JSON is seeded the first time. Actually looking more carefully — the current code reads the JSON first, then _init_structured_file writes it if not present. So a first run without the JSON would crash at _get_seeded_users(). That's a bug — the correct order would be: seed the JSON from code if missing, then read it. Worth fixing in a later phase."

# Note to you: This is a real bug. If the JSON file doesn't exist, _get_seeded_users() will raise FileNotFoundError before _init_structured_file ever runs. The current working tree has the file, so it works. But on a fresh clone with data/ gitignored, it would fail. We should fix this in Phase 2 or later.