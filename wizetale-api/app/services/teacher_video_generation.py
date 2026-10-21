"""Topic, knowledge lookup, and grade-targeted script generation for teacher videos."""

import logging

from app.domain.models import GenerationRequest
from app.domain.teacher import VideoResourceContent
from app.services.knowledge_service import knowledge_service as default_knowledge_service
from app.services.pipeline.script_service import script_generation_service

logger = logging.getLogger(__name__)


def grade_to_lookup_band(school_grade: str) -> str:
    """Map a school grade to the closest approved-knowledge search age band."""
    if school_grade == 'K' or int(school_grade) <= 6:
        return '10-12'
    if int(school_grade) <= 9:
        return '13-15'
    return '16-18'


class InvalidTeacherVideoTopic(ValueError):
    """The existing topic validator rejected a teacher's selected topic."""


class TeacherVideoGenerationService:
    def __init__(self, *, script_service=None, knowledge_service=None):
        self.script_service = script_service or script_generation_service
        self.knowledge_service = knowledge_service or default_knowledge_service

    def generate(
        self,
        lesson: dict,
        *,
        target_duration_sec: int,
        voice: str,
        user_id: str,
    ) -> VideoResourceContent:
        school_grade = str(lesson['grade'])
        request = GenerationRequest(
            subject=lesson['subject'],
            topic=lesson['topic'],
            language=lesson['language'],
            voice=voice,
            user_id=user_id,
            grade_band=grade_to_lookup_band(school_grade),
            school_grade=school_grade,
            target_duration_sec=target_duration_sec,
        )
        validated_topic = self.script_service.validate_topic(request)
        if not validated_topic.valid:
            raise InvalidTeacherVideoTopic(
                validated_topic.rejection_reason or 'Choose a suitable learning topic.'
            )

        knowledge_context = ''
        try:
            knowledge = self.knowledge_service.retrieve(
                request.topic, request.subject, request.grade_band,
            )
            knowledge_context = knowledge.prompt_context
        except Exception as error:
            logger.warning(
                'Reviewed knowledge lookup failed for teacher video topic (%s).',
                type(error).__name__,
            )

        script = self.script_service.generate_script(
            request=request,
            validated_topic=validated_topic,
            knowledge_context=knowledge_context,
        )
        return VideoResourceContent(
            script=script,
            target_duration_sec=target_duration_sec,
            voice=voice,
        )


teacher_video_generation_service = TeacherVideoGenerationService()
