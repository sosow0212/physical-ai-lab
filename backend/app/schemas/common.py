"""공통 DTO."""

from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PageOut(BaseModel):
    """목록 응답 공통 봉투."""

    items: list
    total: int
    page: int
    page_size: int
