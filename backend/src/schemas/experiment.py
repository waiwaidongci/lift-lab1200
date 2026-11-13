from typing import Optional
from pydantic import BaseModel, Field, field_validator


class ExperimentInput(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    dataset_id: int
    hypothesis: str = Field(min_length=8, max_length=1000)
    alpha: float = Field(default=.05, gt=0, lt=.5)
    cuped: bool = True
    # 前置收入分层切点，在登记时固定；省略表示沿用未分层原方法。
    strata_bounds: Optional[list[float]] = Field(default=None, max_length=10)

    @field_validator("strata_bounds", mode="before")
    @classmethod
    def valid_bounds(cls, value):
        if value is None:
            return None
        if not isinstance(value, list):
            raise ValueError("分层区间必须是数值列表")
        for item in value:
            if isinstance(item, bool) or not isinstance(item, (int, float)):
                raise ValueError("分层边界必须是有限数值（布尔值不接受）")
        return value
