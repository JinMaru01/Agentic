from pydantic import BaseModel
from typing import Optional

class CredentialInput(BaseModel):
    website: Optional[str] = None
    url: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    category: Optional[str] = None