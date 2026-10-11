import os
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from app.auth.models import User

JWT_SECRET = os.environ.get('JWT_SECRET')
if not JWT_SECRET:
    raise RuntimeError('JWT_SECRET environment variable is missing')

JWT_ALGORITHM = os.environ.get('JWT_ALGORITHM', 'HS256')
JWT_EXPIRE_MINUTES = int(os.environ.get('JWT_EXPIRE_MINUTES', '480'))


def create_access_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=JWT_EXPIRE_MINUTES)
    claims = {
        'sub': user.user_id,
        'email': user.email,
        'role': user.role,
        'department': user.department,
        'exp': expire,
    }
    return jwt.encode(claims, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError as e:
        raise ValueError(f'Invalid or expired token: {e}') from e
