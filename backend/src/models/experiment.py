from typing import Optional
from sqlalchemy import ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column
from ..config.database import Base
class Experiment(Base):
    __tablename__ = "experiments"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id"))
    hypothesis: Mapped[str]
    metric: Mapped[str] = mapped_column(default="revenue")
    alpha: Mapped[float] = mapped_column(default=.05)
    cuped: Mapped[bool] = mapped_column(default=True)
    # 登记时固定的前置收入切分边界；空值表示旧实验沿用未分层原方法。
    strata_bounds: Mapped[Optional[list]] = mapped_column(JSON(none_as_null=True), nullable=True, default=None)
    owner: Mapped[str]
