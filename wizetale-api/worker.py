# This file is the new entrypoint for the Celery worker.
# It ensures that the task modules are discovered correctly.

import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

from app.celery_utils import celery_app

# Add the tasks module to the includes
celery_app.conf.include = [
    'app.api.v1.generate',
    'app.services.document_worker',
    'app.services.teacher_presentation_video',
    'app.services.teacher_video_render',
    'app.services.presentation_visuals',
]
