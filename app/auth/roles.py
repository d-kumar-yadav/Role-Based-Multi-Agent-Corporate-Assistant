# Mock database of user roles
USER_DB = {
    "hr": "hr",
    "finance": "finance",
    "it": "it"
}

def get_user_role(user_id: str) -> str:
    """
    Returns the role for a given user_id. Defaults to 'guest' if not found.
    """
    return USER_DB.get(user_id.lower(), "guest")
