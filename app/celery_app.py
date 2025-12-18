from celery import Celery

from app.config import settings, REDIS_URL

# Use unified settings for Celery configuration
celery = Celery(
    "worker",
    broker=settings.celery_broker_url or REDIS_URL,
    backend=settings.celery_result_backend or REDIS_URL,
    include=["app.tasks.rag_tasks", "app.tasks.notes_tasks"]
)

# Configure Celery settings for notes processing
celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    worker_max_tasks_per_child=10,  # Prevent memory leaks
    worker_prefetch_multiplier=1,  # Fetch one task at a time
    task_acks_late=True,  # Acknowledge after completion
    task_reject_on_worker_lost=True,
    broker_connection_retry_on_startup=True,
    task_time_limit=3600,  # 1 hour hard limit
    task_soft_time_limit=3300,  # 55 minutes soft limit
)
