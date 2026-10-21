from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from app.auth.models import User
from app.auth.store import get_user_by_id
from app.auth.tokens import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token)
        user_id: str | None = payload.get("sub")
        if not user_id:
            raise credentials_exception
    except Exception:
        raise credentials_exception

    user = get_user_by_id(user_id)
    if user is None:
        raise credentials_exception
    return user


# [1. User / Client / Swagger UI]
#                │
#                ▼  1. Does NOT have a token yet
#   Reads tokenUrl = "/auth/token"
#                │
#                ▼  2. Sends POST to /auth/token (username + password)
# [2. Backend Login Endpoint: @app.post("/auth/token")]
#                │
#                ├─► Verifies credentials (email + password)
#                └─► Generates signed JWT token
#                │
#                ▼  3. Returns: {"access_token": "eyJhbGciOi...", "token_type": "bearer"}
# [1. User / Client]
#                │
#                ▼  4. Saves the token
#                │
#                ▼  5. Calls Protected Route: POST /query   from frontend
#                      Header: "Authorization: Bearer eyJhbGciOi..."
#                │
# [3. FastAPI Backend: oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")]
#                │
#                ├─► Reads "Authorization" header
#                ├─► Extracts token string: "eyJhbGciOi..."
#                │
#                ▼  6. Passes token to get_current_user()
# [4. get_current_user(token)]
#                │
#                ├─► Decodes JWT, validates signature, extracts user_id & role
#                └─► Injects `user` object into your endpoint
#                │
#                ▼
# [5. Endpoint handle_query() runs with verified user!]





# In FastAPI, oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token") is a security helper class that does two main things:

# Header Extraction: When a protected endpoint receives a request, oauth2_scheme automatically looks inside the incoming HTTP request's Authorization header, strips out the word 'Bearer ', and returns just the token string. If the header is missing or malformed, it automatically returns a 401 Unauthorized before reaching our business logic.
# Swagger UI Integration: The tokenUrl parameter tells FastAPI's Swagger UI documentation where to send credentials when a developer clicks the 'Authorize' button in the interactive docs. It does not make an HTTP call to /auth/token on every request; it is purely documentation metadata for Swagger.