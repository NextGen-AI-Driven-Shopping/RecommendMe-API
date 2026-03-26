"""Cache cleanup utilities executed before backend startup."""

from app.core.cache_cleaner.cleaner import clear_all_caches

__all__ = ["clear_all_caches"]
