# Base.metadata 접근 시 모델이 모두 로딩되도록 하는 진입점.
import app.db.model_registry  # noqa: F401
from app.db.base_class import Base, utc_now

__all__ = ["Base", "utc_now"]
