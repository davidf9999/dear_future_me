from typing import Optional

from pydantic import BaseModel


class UserData(BaseModel):
    name: Optional[str] = None
    preferences: Optional[str] = None
    # ... other general user context fields
