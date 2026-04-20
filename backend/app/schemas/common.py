from pydantic import BaseModel
from typing import Any


class ApiResponse(BaseModel):
    error: dict[str, str] | None = None
    data: Any = None


class PaginatedResponse(BaseModel):
    items: list[Any]
    total: int
    page: int = 1
    page_size: int = 20
