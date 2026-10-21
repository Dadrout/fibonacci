from celery import Celery
from app.core.config import settings

def create_celery_app() -> Celery:
    """
    Create and configure a Celery application instance.
    
    Reads broker and backend URLs from the application settings.
    """
    # Using one Redis DB for the broker and another for the backend
    broker_url = settings.REDIS_URL
    result_backend = broker_url.replace('/0', '/1') # Use DB 1 for results

    celery_app = Celery(
        "worker",
        broker=settings.CELERY_BROKER_URL,
        backend=settings.CELERY_RESULT_BACKEND,
        include=['app.api.v1.generate', 'app.services.document_worker', 'app.services.teacher_presentation_video', 'app.services.teacher_video_render', 'app.services.presentation_visuals', 'app.services.brain.pipeline', 'app.services.brain.plans']
    )
    celery_app.conf.update(
        task_track_started=True,
        # Generation can run for minutes, so only acknowledge after it finishes.
        # If the executing worker process is lost, put the task back on the queue.
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1,
    )
    return celery_app

celery_app = create_celery_app() 
