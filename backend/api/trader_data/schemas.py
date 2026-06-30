from typing import Any

from pydantic import BaseModel


class ImportPreviewRequest(BaseModel):
    data: dict[str, Any]


class ImportExecuteRequest(BaseModel):
    data: dict[str, Any]
    confirmed: bool = False
