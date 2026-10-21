"""Token-guarded background ingestion; never log document contents."""
import logging
from time import monotonic
from celery.exceptions import SoftTimeLimitExceeded
from app.celery_utils import celery_app
from app.services.document_repository import document_repository
from app.services.document_text import extract_document,chunk_sections

logger=logging.getLogger(__name__)


def process_document(did,uid,task_id,repository=document_repository):
    started=monotonic()
    row=repository.document(did,uid)
    if not row or row['status']!='processing' or str(row['task_id'])!=str(task_id) or repository.is_user_deleting(uid): return False
    try:
        chunks=chunk_sections(extract_document(repository.download(row),row['kind']))
        published=repository.publish(did,uid,task_id,chunks)
        logger.info('teacher_document id=%s status=%s passages=%d latency_ms=%d',did,'ready' if published else 'cancelled',len(chunks),int((monotonic()-started)*1000))
        return published
    except Exception as error:
        message=str(error) if isinstance(error,ValueError) else 'Document processing failed. Retry or upload another document.'
        repository.change(did,uid,{'status':'failed','error_message':message},status='processing',task_id=task_id)
        logger.warning('teacher_document id=%s status=failed error_type=%s',did,type(error).__name__)
        return False


@celery_app.task(name='teacher.process_document',soft_time_limit=60,time_limit=75)
def ingest_document(did,uid,task_id):
    return process_document(did,uid,task_id)
