"""Public persistence gateway."""

from src.store._gateway import Store
from src.store._models import DeleteBookResultModel

__all__ = ["DeleteBookResultModel", "Store"]
