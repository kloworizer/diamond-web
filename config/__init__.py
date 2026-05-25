# Make Celery app available as part of this Django project.
from .celery import app as celery_app  # noqa: F401

__all__ = ('celery_app',)
