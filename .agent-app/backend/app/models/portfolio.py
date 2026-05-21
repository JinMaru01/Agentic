from pydantic import BaseModel
from typing import Optional

class PortfolioCreate(BaseModel):
    name: str
    description: Optional[str] = None
    status: Optional[str] = 'active'
    owner_id: int

class PortfolioUpdate(BaseModel):
    name: str
    description: Optional[str] = None
    status: Optional[str] = None
    owner_id: int

class PortfolioResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    status: str
    created_at: str
    updated_at: str
    is_active: bool
