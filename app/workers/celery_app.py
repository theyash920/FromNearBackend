from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "fromnear_growth_worker",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={"app.workers.tasks.run_growth_workflow": {"queue": "ai_workflows"}},
)
