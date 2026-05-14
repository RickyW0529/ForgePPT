from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class PreferenceItem(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=64)
    category: str = Field(..., pattern=r"^(color_scheme|font_style|layout_style|tone)$")
    description: str = Field(..., min_length=1, max_length=500)
    embedding_source: str = Field(..., description="Original text used to generate embedding")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source_node: Optional[str] = Field(default=None)
    metadata: Optional[dict] = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def _sync_embedding_source(self):
        if self.embedding_source != self.description:
            self.embedding_source = self.description
        return self
