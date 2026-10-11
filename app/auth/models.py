from pydantic import BaseModel, ConfigDict


class User(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str
    email: str
    name: str
    role: str
    department: str
    manager_id: str | None
    allowed_departments: list[str]
