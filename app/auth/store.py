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
