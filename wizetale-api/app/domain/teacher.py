"""Validated teacher lesson context and editable, printable resource content."""
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.domain.models import VideoScript

Subject = Literal['language_arts', 'math', 'science', 'history_social_studies', 'geography']
ResourceKind = Literal['objectives', 'lesson_plan', 'quiz', 'test_paper', 'flashcards', 'worksheet', 'exit_ticket', 'homework', 'presentation', 'video']


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class LessonInput(StrictModel):
    subject: Subject
    grade: str = Field(pattern=r'^(K|[1-9]|1[0-2])$')
    topic: str = Field(min_length=1, max_length=200)
    language: Literal['en-US', 'ru-RU', 'kk-KZ'] = 'en-US'
    objectives: str = Field(default='', max_length=3000)
    source_material: str = Field(default='', max_length=20000)

    @field_validator('topic')
    @classmethod
    def normalize_topic(cls, value):
        return ' '.join(value.split())


class LessonUpdate(StrictModel):
    lesson: LessonInput
    revision: int = Field(ge=1)


class Section(StrictModel):
    heading: str = Field(min_length=1, max_length=300)
    body: str = Field(min_length=1, max_length=6000)


class Question(StrictModel):
    prompt: str = Field(min_length=1, max_length=2000)
    choices: list[str] = Field(default_factory=list, max_length=6)
    points: int = Field(default=1, ge=1, le=100)

    @field_validator('choices')
    @classmethod
    def valid_choices(cls, choices):
        if len(choices) == 1 or any(not choice.strip() or len(choice) > 1000 for choice in choices):
            raise ValueError('Choices must be empty or contain at least two nonempty options')
        return choices


class Answer(StrictModel):
    question_number: int = Field(ge=1, le=100)
    answer: str = Field(min_length=1, max_length=3000)
    explanation: str = Field(default='', max_length=3000)


class Flashcard(StrictModel):
    front: str = Field(min_length=1, max_length=1500)
    back: str = Field(min_length=1, max_length=2000)


class SlideVisual(StrictModel):
    status: Literal['pending', 'processing', 'ready', 'failed']
    kind: Literal['image', 'diagram']
    alt_text: str = Field(max_length=1000)
    caption: str = Field(max_length=1000)
    image_url: str | None = None


class PresentationSlide(StrictModel):
    visual: SlideVisual | None = None
    title: str = Field(min_length=1, max_length=200)
    key_points: list[str] = Field(min_length=1, max_length=6)
    speaker_notes: str = Field(min_length=1, max_length=3000)

    @field_validator('key_points')
    @classmethod
    def nonempty_key_points(cls, values):
        if any(not value.strip() or len(value) > 1000 for value in values):
            raise ValueError('Presentation points must be nonempty and concise')
        return values


class ResourceContent(StrictModel):
    title: str = Field(min_length=1, max_length=300)
    instructions: str = Field(default='', max_length=4000)
    objectives: list[str] = Field(default_factory=list, max_length=20)
    sections: list[Section] = Field(default_factory=list, max_length=30)
    questions: list[Question] = Field(default_factory=list, max_length=100)
    flashcards: list[Flashcard] = Field(default_factory=list, max_length=100)
    slides: list[PresentationSlide] = Field(default_factory=list, max_length=24)
    teacher_notes: list[Section] = Field(default_factory=list, max_length=30)
    answer_key: list[Answer] = Field(default_factory=list, max_length=100)
    duration_minutes: int = Field(default=45, ge=1, le=240)

    @field_validator('objectives')
    @classmethod
    def nonempty_objectives(cls, values):
        if any(not value.strip() or len(value) > 1500 for value in values):
            raise ValueError('Objectives must be nonempty and concise')
        return values


class VideoResourceContent(StrictModel):
    script: VideoScript
    target_duration_sec: Literal[180, 240, 300] = 180
    voice: Literal['female', 'male'] = 'female'


class ResourceGenerate(StrictModel):
    kind: ResourceKind
    request_id: UUID
    target_duration_sec: Literal[180, 240, 300] = 180
    voice: Literal['female', 'male'] = 'female'


class ResourceUpdate(StrictModel):
    content: ResourceContent | VideoResourceContent
    revision: int = Field(ge=1)


PRESETS = {
    'objectives': '3–5 measurable learning objectives.',
    'lesson_plan': 'A 45-minute lesson with objectives, timed teaching phases, materials, differentiation, and assessment. Put teacher guidance in teacher_notes.',
    'quiz': 'Exactly 10 age-appropriate questions, with a separate answer_key and explanations. Use a mix of multiple choice and short answer.',
    'test_paper': 'A test totaling exactly 20 points. Include a separate answer_key and scoring rubric in teacher_notes.',
    'flashcards': 'Exactly 12 front/back flashcards covering essential ideas.',
    'worksheet': 'One printable page of student instructions and activities, with separate solutions and teacher guidance.',
    'exit_ticket': 'Exactly 3 brief questions that check understanding, with a separate answer_key.',
    'homework': 'Exactly 5 manageable practice tasks, with a separate answer_key.',
    'presentation': 'Exactly 8 ordered slides with a clear opening and concise closing. Each slide has a focused title, 1–4 key points, and natural speaker notes in the selected language. Explain the slide rather than reading bullet points verbatim.',
}


def validate_content(kind: ResourceKind, content: ResourceContent | VideoResourceContent, *, generated=False) -> ResourceContent | VideoResourceContent:
    """Enforce useful content and matching keys; presets only bind fresh generation."""
    if kind == 'video':
        if not isinstance(content, VideoResourceContent):
            raise ValueError('A video resource needs a video script')
        return content
    if isinstance(content, VideoResourceContent):
        raise ValueError('Video script content can only be used for a video resource')

    questions = content.questions
    if questions:
        expected = set(range(1, len(questions) + 1))
        keys = [answer.question_number for answer in content.answer_key]
        if len(keys) != len(expected) or set(keys) != expected:
            raise ValueError('Every question needs exactly one matching answer key')
    elif content.answer_key:
        raise ValueError('An answer key requires questions')
    if kind in {'quiz', 'test_paper', 'exit_ticket', 'homework'} and not questions:
        raise ValueError('This resource needs questions')
    if kind == 'objectives' and not content.objectives:
        raise ValueError('Add at least one objective')
    if kind in {'lesson_plan', 'worksheet'} and not content.sections:
        raise ValueError('This resource needs lesson or activity sections')
    if kind == 'flashcards' and not content.flashcards:
        raise ValueError('Add at least one flashcard')
    if kind == 'presentation' and len(content.slides) != 8:
        raise ValueError('A presentation needs exactly 8 slides')
    if generated:
        counts = {'quiz': 10, 'exit_ticket': 3, 'homework': 5}
        if kind in counts and len(questions) != counts[kind]:
            raise ValueError('Generated question count does not match the preset')
        if kind == 'test_paper' and not content.teacher_notes:
            raise ValueError('Generated test needs a scoring rubric')
        if kind == 'test_paper' and sum(q.points for q in questions) != 20:
            raise ValueError('Generated test must total 20 points')
        if kind == 'flashcards' and len(content.flashcards) != 12:
            raise ValueError('Generate 12 flashcards')
        if kind == 'presentation' and len(content.slides) != 8:
            raise ValueError('Generate 8 presentation slides')
        if kind == 'objectives' and not 3 <= len(content.objectives) <= 5:
            raise ValueError('Generate 3–5 objectives')
        if kind == 'lesson_plan' and content.duration_minutes != 45:
            raise ValueError('Generated lesson plan must cover 45 minutes')
    return content
