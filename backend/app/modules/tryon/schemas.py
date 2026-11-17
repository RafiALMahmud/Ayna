from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class TryOnOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    product_id: str
    provider: str
    framing: str
    status: str
    progress: int
    diagnostics: dict
    error_code: str | None
    result_url: str | None = None
    created_at: datetime
    expires_at: datetime
    deleted_at: datetime | None
    mode: Literal["diagnostic", "generated_preview"] = "diagnostic"
    disclosure: str = (
        "Generated appearance previews are synthetic and do not verify sizing or physical fit."
    )
