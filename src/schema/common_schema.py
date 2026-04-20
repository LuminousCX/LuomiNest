"""通用响应与分页参数校验模型。"""

from __future__ import annotations

from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """统一 API 响应格式。

    Attributes:
        code: 错误码，0 表示成功。
        message: 响应消息。
        data: 响应数据。
    """

    code: int = Field(default=0, description="错误码，0 表示成功")
    message: str = Field(default="success", description="响应消息")
    data: Optional[T] = Field(default=None, description="响应数据")

    @classmethod
    def success(cls, data: T = None, message: str = "success") -> ApiResponse[T]:
        """构建成功响应。"""
        return cls(code=0, message=message, data=data)

    @classmethod
    def error(cls, code: int = -1, message: str = "error", data: T = None) -> ApiResponse[T]:
        """构建错误响应。"""
        return cls(code=code, message=message, data=data)


class PaginationRequest(BaseModel):
    """分页请求参数。"""

    page: int = Field(default=1, ge=1, description="页码，从 1 开始")
    page_size: int = Field(default=20, ge=1, le=100, description="每页数量")


class PaginationResponse(BaseModel, Generic[T]):
    """分页响应数据。"""

    total: int = Field(default=0, ge=0, description="总记录数")
    page: int = Field(default=1, ge=1, description="当前页码")
    page_size: int = Field(default=20, ge=1, description="每页数量")
    items: list[T] = Field(default_factory=list, description="数据列表")

    @property
    def total_pages(self) -> int:
        """总页数。"""
        if self.page_size <= 0:
            return 0
        return (self.total + self.page_size - 1) // self.page_size
